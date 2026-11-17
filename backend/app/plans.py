"""
Start a session in plain words: "Dinner at Olive Garden on Main St, back by 11"
becomes a destination ("Olive Garden on Main St") and a return time (11:00 PM).

An AI reads the text: Claude (AI_PROVIDER=claude, with ANTHROPIC_API_KEY set)
or a free model on this computer through Ollama (AI_PROVIDER=ollama). Without
one, or if it is slow or fails, a simple built-in reader is used, so this
never blocks starting a session. Nothing is started here: the app fills in
the Start Session form and you confirm it.

When a time could be either AM or PM ("back by 11" at 10:30 AM), it isn't
guessed: the app shows both and you pick. A time that's too early alerts the
Circle while you're still out, so a wrong guess is the mistake to avoid.

To see how well each reader does: python scripts/score_plans.py --reader ...
"""

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import anthropic
import httpx

from app.config import get_settings

log = logging.getLogger(__name__)

# Same limits as the Start Session screen.
EARLIEST = timedelta(minutes=5)
LATEST = timedelta(hours=24)
# "Back by 11" with no am/pm: an 11 o'clock more than this far away is
# unlikely to be the one meant, so only the nearer one is used.
LIKELY = timedelta(hours=13)
TIME_FIELDS = ("back_by_time", "other_time", "minutes_from_now", "day")


@dataclass
class Plan:
    destination: str | None
    return_by: datetime | None
    # Why there's no time, in words for the app (None when all went well).
    problem: str | None
    source: str  # "ai" or "basic"
    # Two possible times ("11:00 AM or 11:00 PM?") for you to pick from.
    choices: list[datetime] = field(default_factory=list)


def read_plan(text: str, now: datetime, time_zone: str | None = None) -> Plan:
    """`now` is the phone's local time (with its UTC offset)."""
    now = now.astimezone(_zone(time_zone, now))
    fields = ask_ai(text, now)
    source = "ai"
    basic = read_basic(text, now)
    if fields is None:
        fields = basic
        source = "basic"
    elif not fields.get("minutes_from_now") and not fields.get("back_by_time"):
        # The AI missed the time but the built-in reader found one ("around noon").
        fields = {**fields, **{key: basic.get(key) for key in TIME_FIELDS}}
    return_by, problem, choices = _return_time(fields, now)
    destination = _clean_place(fields.get("destination")) or _clean_place(basic["destination"])
    return Plan(destination, return_by, problem, source, choices)


def _zone(name: str | None, now: datetime) -> tzinfo:
    try:
        return ZoneInfo(name) if name else now.tzinfo  # type: ignore[return-value]
    except (ZoneInfoNotFoundError, ValueError):
        return now.tzinfo  # type: ignore[return-value]


def _return_time(fields: dict, now: datetime) -> tuple[datetime | None, str | None, list[datetime]]:
    """The return time (or two to pick from), between 5 min and 24 h ahead."""
    minutes = fields.get("minutes_from_now")
    if isinstance(minutes, int | float) and minutes > 0:
        found = [now + timedelta(minutes=minutes)]
    else:
        clocks = [fields.get("back_by_time"), fields.get("other_time")]
        found = [when for clock in clocks if (when := _when(clock, fields, now))]
        if not found:
            return None, "Add when you'll be back, e.g. “back by 11 pm”.", []

    found = [when.replace(second=0, microsecond=0) for when in found]
    usable = sorted(when for when in found if EARLIEST <= when - now <= LATEST)
    if len(usable) == 2:
        first, second = (_say(when, now) for when in usable)
        return None, f"Did you mean {first} or {second}?", usable
    if usable:
        return usable[0], None, []
    if found[0] - now < EARLIEST:
        return None, "That's less than 5 minutes from now.", []
    return None, "Pick a time within the next 24 hours.", []


def _when(clock, fields: dict, now: datetime) -> datetime | None:
    """'23:00' as the next such time (tomorrow if it has passed or they said so)."""
    if not isinstance(clock, str) or not re.fullmatch(r"\d{1,2}:\d{2}", clock):
        return None
    hour, minute = (int(part) for part in clock.split(":"))
    if hour > 23 or minute > 59:
        return None
    when = datetime.combine(now.date(), time(hour, minute), now.tzinfo)
    if fields.get("day") == "tomorrow" or when <= now:
        when += timedelta(days=1)
    return when


def _say(when: datetime, now: datetime) -> str:
    """'11:00 PM', or 'tomorrow 8:00 AM'."""
    day = "tomorrow " if when.date() > now.date() else ""
    return day + when.strftime("%I:%M %p").lstrip("0")


def _clean_place(place) -> str | None:
    """'Dinner at Olive Garden on Main St' -> 'Olive Garden on Main St'."""
    if not isinstance(place, str):
        return None
    place = place.strip().strip("\"'“”.,;!").strip()
    # Leave out the activity before the place ("Dinner at", "Heading to").
    activity = re.match(r"(?:\S+\s+){0,3}?\S+\s+(?:at|to|@)\s+(?!\d)(.+)$", place, re.I)
    if activity:
        place = activity.group(1)
    place = re.sub(r"^(?:to|at|@)\s+", "", place, flags=re.I)
    # ...and the time after it (", home by 11", " and back"), but not a name
    # like "The Home Depot".
    place = re.sub(
        r"(?:\s*[,;]\s*|\s+)(?:and\s+)?(?:be\s+)?(?:(?:back|home)(?:\s+(?:by|at|around|in|for|until|"
        r"till|til|tonight|tomorrow)\b.*)?|(?:then|until|till|til|by|for)\b.*)$",
        "",
        place,
        flags=re.I,
    )
    place = place.strip(" ,.;!")
    return place[:120] or None


# ----- AI -----

SYSTEM = """You read short plans typed into a personal safety app before someone heads out. \
Extract where they are going and when they expect to be back.

- destination: the place, as the person would name it to a friend ("Olive Garden on Main St", \
"Sam's house", "the gym"). Leave out the activity and the time. null if no place is given.
- back_by_time: the return time as 24-hour "HH:MM" local time, or null. Read "back by 11" or \
"home around 11" as the next 11 o'clock that makes sense from the current local time and the \
activity (late dinners mean PM). "noon" is 12:00, "midnight" is 00:00.
- am_pm_unclear: true only if they gave a clock time without am/pm and neither the time of \
day nor the activity makes clear which one they mean (e.g. "coffee, back by 11" at 10:30 AM). \
The app then asks them.
- day: "tomorrow" only if they say tomorrow or the time is clearly the next day; otherwise "today".
- minutes_from_now: for relative times, the total minutes from now until they are back home, \
or null. Add up every part of the plan that happens one after another: "lunch for an hour, \
then back in 30 minutes" is 90; "movie for 2 hours and 20 min to drive home" is 140. A \
too-early time makes the app alert their friends while they're still out, so when unsure, \
count the longer reading ("2-3 hours" is 180). Use either back_by_time or minutes_from_now, \
not both.

Never invent a time or place that isn't in the text."""

SCHEMA = {
    "type": "object",
    "properties": {
        "destination": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "back_by_time": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "am_pm_unclear": {"type": "boolean"},
        "day": {"type": "string", "enum": ["today", "tomorrow"]},
        "minutes_from_now": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
    },
    "required": ["destination", "back_by_time", "am_pm_unclear", "day", "minutes_from_now"],
    "additionalProperties": False,
}


def ask_ai(text: str, now: datetime) -> dict | None:
    """The fields the chosen AI reads from the text, or None to use the built-in reader."""
    provider = get_settings().ai_provider.strip().lower()
    if provider == "claude":
        return ask_claude(text, now)
    if provider == "ollama":
        return ask_ollama(text, now)
    return None


def _question(text: str, now: datetime) -> str:
    return f"Current local time: {now:%A %Y-%m-%d %H:%M}\n\nPlan: <plan>{text}</plan>"


def _fields(answer: str) -> dict | None:
    try:
        fields = json.loads(answer)
    except json.JSONDecodeError:
        return None
    return fields if isinstance(fields, dict) else None


def ask_claude(text: str, now: datetime) -> dict | None:
    """The fields Claude reads from the text, or None (no key, slow, or failed)."""
    settings = get_settings()
    if not settings.anthropic_api_key:
        return None
    client = anthropic.Anthropic(
        api_key=settings.anthropic_api_key,
        timeout=settings.ai_timeout_seconds,
        max_retries=1,
    )
    try:
        response = client.beta.messages.create(
            model=settings.ai_model,
            max_tokens=2000,
            system=SYSTEM,
            messages=[{"role": "user", "content": _question(text, now)}],
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
            # If the model declines, the API retries on its recommended fallback.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    except anthropic.APIError as error:
        log.warning("Claude couldn't read the plan (%s); using the basic reader", error)
        return None
    if response.stop_reason != "end_turn":
        log.warning("Claude stopped with %s; using the basic reader", response.stop_reason)
        return None
    answer = next((block.text for block in response.content if block.type == "text"), "")
    fields = _fields(answer)
    if fields and fields.get("am_pm_unclear") is True:
        fields["other_time"] = _other_half(fields.get("back_by_time"))
    return fields


def _other_half(clock) -> str | None:
    """'23:00' -> '11:00'."""
    if not isinstance(clock, str) or not re.fullmatch(r"\d{1,2}:\d{2}", clock):
        return None
    hour, minute = (int(part) for part in clock.split(":"))
    return f"{(hour + 12) % 24:02d}:{minute:02d}" if hour <= 23 else None


# Small models on a laptop copy words out well but get sums and am/pm wrong,
# so they only copy the parts out; the adding up and am/pm are done here.
OLLAMA_SYSTEM = """Copy the parts of a short plan someone typed before heading out, as JSON.

- destination: the place they are going, in their words ("Joe's Pizza", "the park"). \
No activity, no time. null if no place.
- back_by: the clock time they will be back by, as "H:MM", adding "am" or "pm" only if \
they wrote it. "quarter to" a time is 15 minutes before it, "noon" is "12:00pm", \
"midnight" is "12:00am". null if the plan has no clock time.
- durations: each length of time written in the plan ("for an hour", "in 20 min"), \
converted to minutes, in order. [] if the plan has none.
- tomorrow: true only if they say tomorrow.

Only copy what is written in the plan. Never invent a time or a duration."""

OLLAMA_SCHEMA = {
    "type": "object",
    "properties": {
        "destination": {"type": ["string", "null"]},
        "back_by": {"type": ["string", "null"]},
        "durations": {"type": "array", "items": {"type": "integer"}},
        "tomorrow": {"type": "boolean"},
    },
    "required": ["destination", "back_by", "durations", "tomorrow"],
}


def ask_ollama(text: str, now: datetime) -> dict | None:
    """The fields a model in Ollama reads from the text, or None (not running, slow, or failed)."""
    settings = get_settings()
    try:
        response = httpx.post(
            f"{settings.ollama_url.rstrip('/')}/api/chat",
            json={
                "model": settings.ollama_model,
                "messages": [
                    {"role": "system", "content": OLLAMA_SYSTEM},
                    {"role": "user", "content": f"<plan>{text}</plan>"},
                ],
                "stream": False,
                # Ollama keeps the answer to this JSON shape.
                "format": OLLAMA_SCHEMA,
                "options": {"temperature": 0},
                # Keep the model loaded between plans; loading it takes a while.
                "keep_alive": "30m",
            },
            timeout=settings.ollama_timeout_seconds,
        )
        response.raise_for_status()
        parts = _fields(response.json()["message"]["content"])
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as error:
        log.warning("Ollama couldn't read the plan (%s); using the basic reader", error)
        return None
    if not parts:
        return None
    fields = _from_parts(parts, _plain(text), now)
    # Scored on evals/plan_cases.py, the built-in reader gets times right more
    # often than a small model, so its time wins; the model fills in the rest.
    basic = read_basic(text, now)
    if basic.get("minutes_from_now") or basic.get("back_by_time"):
        fields.update({key: basic.get(key) for key in TIME_FIELDS})
    return fields


def warm_up_ollama() -> None:
    """Load the Ollama model now, so the first plan isn't slow. Never raises."""
    settings = get_settings()
    try:
        httpx.post(
            f"{settings.ollama_url.rstrip('/')}/api/generate",
            json={"model": settings.ollama_model, "keep_alive": "30m"},
            timeout=120,
        )
    except httpx.HTTPError as error:
        log.warning("Couldn't load the Ollama model (%s); is Ollama running?", error)


_DURATION_WORDS = re.compile(r"\b(hours?|hrs?|minutes?|mins?)\b", re.I)
_CLOCK_WORDS = re.compile(r"\b(noon|midnight)\b", re.I)


def _from_parts(parts: dict, text: str, now: datetime) -> dict:
    """The model's copied-out parts, turned into the same fields Claude gives.

    Small models sometimes make things up, so a duration only counts if the
    plan mentions hours or minutes, a clock time only if its hour is written,
    am/pm only if written, and a place only if it's in the plan.
    `text` is the plan in plain form (see _plain).
    """
    destination = _clean_place(parts.get("destination"))
    if destination and destination.lower().removeprefix("the ") not in text.lower():
        destination = None
    fields: dict = {
        "destination": destination,
        "back_by_time": None,
        "day": "tomorrow" if parts.get("tomorrow") is True else "today",
    }
    durations = parts.get("durations")
    if isinstance(durations, list) and _DURATION_WORDS.search(text):
        total = sum(d for d in durations if isinstance(d, int | float) and d > 0)
        if total:
            fields["minutes_from_now"] = round(total)
            return fields
    clock = re.fullmatch(
        r"\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)?\s*",
        str(parts.get("back_by") or ""),
        re.I,
    )
    if clock and (
        str(int(clock.group(1))) in re.findall(r"\d+", text) or _CLOCK_WORDS.search(text)
    ):
        suffix = clock.group(3)
        if suffix and not re.search(rf"\d\s*{re.escape(suffix)}", text, re.I):
            suffix = None  # the model added am/pm that the plan doesn't say
        fields["back_by_time"], fields["other_time"] = _clock(
            clock.group(1), clock.group(2), suffix, now, text, fields["day"] == "tomorrow"
        )
    return fields


# ----- Built-in reader (no AI) -----

_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "fifteen": 15,
    "twenty": 20, "thirty": 30, "forty": 40, "forty-five": 45, "ninety": 90,
}  # fmt: skip
_UNIT = r"(?:hours?|hrs?|minutes?|mins?)"


def _plain(text: str) -> str:
    """Rewrite common ways of saying a time into digits, so the patterns below read them."""
    text = re.sub(r"~\s*", "around ", text)
    text = re.sub(r"\s@\s", " at ", text)
    text = re.sub(r"\b(?:2nite|tonite)\b", "tonight", text, flags=re.I)
    text = re.sub(r"\bbk\b", "back", text, flags=re.I)
    # "11.30" is 11:30 (but "1.25 hours" is a length).
    text = re.sub(rf"\b(\d{{1,2}})\.([0-5]\d)\b(?!\s*{_UNIT}\b)", r"\1:\2", text, flags=re.I)
    text = re.sub(r"\b(\d{1,2}(?::\d{2})?)\s*-?ish\b", r"\1", text, flags=re.I)
    text = re.sub(r"\b(\d{1,2})\s*o'?clock\b", r"\1", text, flags=re.I)

    def before(match: re.Match) -> str:  # "quarter to 11" -> "10:45"
        hour = int(match.group(1)) - 1
        return f"{hour or 12}:45"

    text = re.sub(
        r"\b(?:a\s+)?quarter\s+(?:to|till|til|of)\s+(\d{1,2})\b", before, text, flags=re.I
    )
    text = re.sub(r"\b(?:a\s+)?quarter\s+(?:past|after)\s+(\d{1,2})\b", r"\1:15", text, flags=re.I)
    text = re.sub(r"\bhalf\s+past\s+(\d{1,2})\b", r"\1:30", text, flags=re.I)
    # Lengths: the longer reading of a range is the safer one ("2-3 hours" is 3).
    words = "|".join(sorted(_NUMBER_WORDS, key=len, reverse=True))
    text = re.sub(
        rf"\b({words})(?=\s+{_UNIT}\b)",
        lambda m: str(_NUMBER_WORDS[m.group(1).lower()]),
        text,
        flags=re.I,
    )
    text = re.sub(r"\ban?\s+hour\s+or\s+two\b", "2 hours", text, flags=re.I)
    text = re.sub(rf"\b(?:a\s+)?couple(?:\s+of)?(?=\s+{_UNIT}\b)", "2", text, flags=re.I)
    text = re.sub(rf"\b(?:a\s+)?few(?=\s+{_UNIT}\b)", "3", text, flags=re.I)
    text = re.sub(
        rf"\b\d+(?:\.\d+)?\s*(?:-|to|or)\s*(\d+(?:\.\d+)?)(?=\s*{_UNIT}\b)", r"\1", text, flags=re.I
    )
    return text


_RELATIVE = re.compile(
    r"\b(?:(?:for|in|takes?|another|plus|about|around|like|maybe|roughly)\s+)*"
    # "an hour" needs the space, so the "a" and "m" of "8 am" isn't "a minute".
    r"(?:(an?|half an)\s+|(\d+(?:\.\d+)?)\s*)(hours?|hrs?|h|minutes?|mins?|m)\b"
    r"(\s+and\s+a\s+half)?",
    re.I,
)
_CLOCK = re.compile(
    r"\b(?:(?:back|home)\s+(?:by|at|around)|by|until|till|til|around|at)\s+"
    r"(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)?(?!\w)"
    r"|\b(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)(?!\w)",
    re.I,
)
_WORDS = {"noon": "12:00", "midnight": "00:00"}
_PLACE = re.compile(
    r"\b(?:to|at)\s+(?!\d|noon\b|midnight\b)(?:(?-i:the)\s+)?"
    r"(.+?)(?=\s*[,.;!]|\s+(?:and\s+)?(?:be\s+)?(?:back|home|by|until|till|til|for|around|in\s+\d|"
    r"tonight|tomorrow|today|then)\b|$)",
    re.I,
)


def read_basic(text: str, now: datetime) -> dict:
    """A simple reader for common phrasings, used when the AI isn't available."""
    text = _plain(text)
    fields: dict = {"destination": None, "back_by_time": None, "day": "today"}
    if re.search(r"\btomorrow\b", text, re.I):
        fields["day"] = "tomorrow"

    # Every duration counts, one after another: "lunch for an hour and back in
    # 30 minutes after" is 90 minutes. Adding them up errs late, which is safer
    # than alerting the Circle while you're still on your way.
    durations = list(_RELATIVE.finditer(text))
    relative = bool(durations)
    if durations:
        total = 0.0
        for match in durations:
            word, digits, unit = match.group(1), match.group(2), match.group(3).lower()
            number = {"a": 1.0, "an": 1.0, "half an": 0.5}[word.lower()] if word else float(digits)
            if match.group(4):  # "an hour and a half"
                number += 0.5
            total += number * (60 if unit.startswith("h") else 1)
        fields["minutes_from_now"] = round(total)

    clock = _CLOCK.search(text)
    if clock and not relative:
        fields["back_by_time"], fields["other_time"] = _clock(
            clock.group(1) or clock.group(4),
            clock.group(2) or clock.group(5),
            clock.group(3) or clock.group(6),
            now,
            text,
            fields["day"] == "tomorrow",
        )
    elif not relative:
        word = re.search(r"\b(noon|midnight)\b", text, re.I)
        if word:
            fields["back_by_time"] = _WORDS[word.group(1).lower()]

    place = _PLACE.search(text)
    if place:
        fields["destination"] = place.group(1).strip()
    return fields


# Words that say whether a time with no am/pm is at night or during the day.
_NIGHT = re.compile(
    r"\b(dinner|supper|tonight|evening|night|bar|club|party|drinks|movie|concert|late)\b", re.I
)
_DAY = re.compile(r"\b(breakfast|brunch|lunch|morning|afternoon)\b", re.I)


def _clock(
    hour_text: str,
    minute_text: str | None,
    suffix: str | None,
    now: datetime,
    text: str = "",
    tomorrow: bool = False,
) -> tuple[str | None, str | None]:
    """'7', '30', 'pm' -> ('19:30', None).

    With no am/pm, the second time is the other half of the day when both are
    likely ('11' at 10:30 AM -> '11:00' or '23:00'), else None. (None, None)
    if it isn't a time.
    """
    hour, minute = int(hour_text), int(minute_text or 0)
    if hour > 23 or minute > 59:
        return None, None
    suffix = (suffix or "").lower().replace(".", "")
    if suffix == "pm" and hour < 12:
        return f"{hour + 12:02d}:{minute:02d}", None
    if suffix == "am" and hour == 12:
        return f"00:{minute:02d}", None
    if suffix or hour > 12:
        return f"{hour:02d}:{minute:02d}", None
    chosen, other = _half_of_day(hour % 12, minute, now, text, tomorrow)
    other_text = f"{other:02d}:{minute:02d}" if other is not None else None
    return f"{chosen:02d}:{minute:02d}", other_text


def _half_of_day(
    hour: int, minute: int, now: datetime, text: str, tomorrow: bool
) -> tuple[int, int | None]:
    """'11' (hour 0-11) with no am/pm -> (hour to use, other hour to offer or None)."""
    night, day = _NIGHT.search(text), _DAY.search(text)
    if night and not day:  # "dinner, back by 11" -> 11 PM; "party, back by 1" -> 1 AM
        return (hour if hour <= 4 else hour + 12), None
    if day and not night:  # "brunch, back by 1" -> 1 PM; "breakfast, back by 9" -> 9 AM
        return (hour + 12 if 1 <= hour <= 6 else hour or 12), None
    if tomorrow:  # both may fit tomorrow; the 24-hour limit decides
        return hour, hour + 12

    def ahead(candidate: int) -> timedelta:
        at = now.replace(hour=candidate, minute=minute, second=0, microsecond=0)
        if at - now < EARLIEST:
            at += timedelta(days=1)
        return at - now

    nearest, other = sorted((hour, hour + 12), key=ahead)
    return nearest, (other if ahead(other) <= LIKELY else None)
