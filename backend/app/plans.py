"""
Start a session in plain words: "Dinner at Olive Garden on Main St, back by 11"
becomes a destination ("Olive Garden on Main St") and a return time (11:00 PM).

An AI reads the text: Claude (AI_PROVIDER=claude, with ANTHROPIC_API_KEY set)
or a free model on this computer through Ollama (AI_PROVIDER=ollama). Without
one, or if it is slow or fails, a simple built-in reader is used, so this
never blocks starting a session. Nothing is started here: the app fills in
the Start Session form and you confirm it.
"""

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, time, timedelta, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import anthropic
import httpx

from app.config import get_settings

log = logging.getLogger(__name__)

# Same limits as the Start Session screen.
EARLIEST = timedelta(minutes=5)
LATEST = timedelta(hours=24)
TIME_FIELDS = ("back_by_time", "minutes_from_now", "day")


@dataclass
class Plan:
    destination: str | None
    return_by: datetime | None
    # Why there's no time, in words for the app (None when all went well).
    problem: str | None
    source: str  # "ai" or "basic"


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
    return_by, problem = _return_time(fields, now)
    destination = (fields.get("destination") or "").strip()[:120] or None
    return Plan(destination, return_by, problem, source)


def _zone(name: str | None, now: datetime) -> tzinfo:
    try:
        return ZoneInfo(name) if name else now.tzinfo  # type: ignore[return-value]
    except (ZoneInfoNotFoundError, ValueError):
        return now.tzinfo  # type: ignore[return-value]


def _return_time(fields: dict, now: datetime) -> tuple[datetime | None, str | None]:
    """Turn the fields read from the text into a time between 5 min and 24 h ahead."""
    minutes = fields.get("minutes_from_now")
    clock = fields.get("back_by_time")
    if isinstance(minutes, int | float) and minutes > 0:
        when = now + timedelta(minutes=minutes)
    elif isinstance(clock, str) and re.fullmatch(r"\d{1,2}:\d{2}", clock):
        hour, minute = (int(part) for part in clock.split(":"))
        if hour > 23 or minute > 59:
            return None, "Couldn't tell what time you'll be back."
        when = datetime.combine(now.date(), time(hour, minute), now.tzinfo)
        if fields.get("day") == "tomorrow":
            when += timedelta(days=1)
        elif when <= now:  # a time that has passed today means tomorrow
            when += timedelta(days=1)
    else:
        return None, "Add when you'll be back, e.g. “back by 11 pm”."

    when = when.replace(second=0, microsecond=0)
    if when - now < EARLIEST:
        return None, "That's less than 5 minutes from now."
    if when - now > LATEST:
        return None, "Pick a time within the next 24 hours."
    return when, None


# ----- AI -----

SYSTEM = """You read short plans typed into a personal safety app before someone heads out. \
Extract where they are going and when they expect to be back.

- destination: the place, as the person would name it to a friend ("Olive Garden on Main St", \
"Sam's house", "the gym"). Leave out the activity and the time. null if no place is given.
- back_by_time: the return time as 24-hour "HH:MM" local time, or null. Read "back by 11" or \
"home around 11" as the next 11 o'clock that makes sense from the current local time and the \
activity (late dinners mean PM). "noon" is 12:00, "midnight" is 00:00.
- day: "tomorrow" only if they say tomorrow or the time is clearly the next day; otherwise "today".
- minutes_from_now: for relative times, the total minutes from now until they are back home, \
or null. Add up every part of the plan that happens one after another: "lunch for an hour, \
then back in 30 minutes" is 90; "movie for 2 hours and 20 min to drive home" is 140. A \
too-early time makes the app alert their friends while they're still out, so when unsure, \
count the longer reading. Use either back_by_time or minutes_from_now, not both.

Never invent a time or place that isn't in the text."""

SCHEMA = {
    "type": "object",
    "properties": {
        "destination": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "back_by_time": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "day": {"type": "string", "enum": ["today", "tomorrow"]},
        "minutes_from_now": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
    },
    "required": ["destination", "back_by_time", "day", "minutes_from_now"],
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
    return _fields(answer)


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
    return _from_parts(parts, text, now) if parts else None


_DURATION_WORDS = re.compile(r"\b(hours?|hrs?|minutes?|mins?)\b", re.I)
_CLOCK_WORDS = re.compile(r"\b(noon|midnight|quarter|half past)\b", re.I)


def _from_parts(parts: dict, text: str, now: datetime) -> dict:
    """The model's copied-out parts, turned into the same fields Claude gives.

    Small models sometimes make up a time, so a duration only counts if the
    plan mentions hours or minutes, and a clock time only if its hour is written.
    """
    destination = parts.get("destination")
    fields: dict = {
        "destination": destination if isinstance(destination, str) else None,
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
        fields["back_by_time"] = _clock(clock.group(1), clock.group(2), clock.group(3), now)
    return fields


# ----- Built-in reader (no AI) -----

_RELATIVE = re.compile(
    r"\b(?:for|in|takes?|another|plus)\s+(an?|half an|\d+(?:\.\d+)?)\s*"
    r"(hours?|hrs?|h|minutes?|mins?|m)\b(\s+and\s+a\s+half)?",
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
    r"(.+?)(?=\s*[,.;!]|\s+(?:and\s+)?(?:back|home|by|until|till|til|for|around|in\s+\d|"
    r"tonight|tomorrow|today|then)\b|$)",
    re.I,
)


def read_basic(text: str, now: datetime) -> dict:
    """A simple reader for common phrasings, used when Claude isn't available."""
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
            amount, unit = match.group(1).lower(), match.group(2).lower()
            number = {"a": 1.0, "an": 1.0, "half an": 0.5}.get(amount) or float(amount)
            if match.group(3):  # "an hour and a half"
                number += 0.5
            total += number * (60 if unit.startswith("h") else 1)
        fields["minutes_from_now"] = round(total)

    clock = _CLOCK.search(text)
    if clock and not relative:
        fields["back_by_time"] = _clock(
            clock.group(1) or clock.group(4),
            clock.group(2) or clock.group(5),
            clock.group(3) or clock.group(6),
            now,
        )
    elif not relative:
        word = re.search(r"\b(noon|midnight)\b", text, re.I)
        if word:
            fields["back_by_time"] = _WORDS[word.group(1).lower()]

    place = _PLACE.search(text)
    if place:
        fields["destination"] = place.group(1).strip()
    return fields


def _clock(
    hour_text: str, minute_text: str | None, suffix: str | None, now: datetime
) -> str | None:
    """'7', '30', 'pm' -> '19:30'. With no am/pm, whichever comes next. None if not a time."""
    hour, minute = int(hour_text), int(minute_text or 0)
    suffix = (suffix or "").lower().replace(".", "")
    if suffix == "pm" and hour < 12:
        hour += 12
    elif suffix == "am" and hour == 12:
        hour = 0
    elif not suffix and hour <= 12:
        hour = _nearest_hour(hour, minute, now)
    if hour > 23 or minute > 59:
        return None
    return f"{hour:02d}:{minute:02d}"


def _nearest_hour(hour: int, minute: int, now: datetime) -> int:
    """'11' with no am/pm: whichever of 11:00 and 23:00 comes next (at least 5 min away)."""
    for candidate in (hour % 12, hour % 12 + 12):
        at = now.replace(hour=candidate, minute=minute, second=0, microsecond=0)
        if at - now >= EARLIEST:
            return candidate
    return hour % 12
