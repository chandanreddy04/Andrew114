"""
Start a session in plain words: "Dinner at Olive Garden on Main St, back by 11"
becomes a destination ("Olive Garden on Main St") and a return time (11:00 PM).

Claude reads the text when ANTHROPIC_API_KEY is set. Without a key, or if
Claude is slow or fails, a simple built-in reader is used, so this never
blocks starting a session. Nothing is started here: the app fills in the
Start Session form and you confirm it.
"""

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, time, timedelta, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import anthropic

from app.config import get_settings

log = logging.getLogger(__name__)

# Same limits as the Start Session screen.
EARLIEST = timedelta(minutes=5)
LATEST = timedelta(hours=24)


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
    fields = ask_claude(text, now)
    source = "ai"
    if fields is None:
        fields = read_basic(text, now)
        source = "basic"
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


# ----- Claude -----

SYSTEM = """You read short plans typed into a personal safety app before someone heads out. \
Extract where they are going and when they expect to be back.

- destination: the place, as the person would name it to a friend ("Olive Garden on Main St", \
"Sam's house", "the gym"). Leave out the activity and the time. null if no place is given.
- back_by_time: the return time as 24-hour "HH:MM" local time, or null. Read "back by 11" or \
"home around 11" as the next 11 o'clock that makes sense from the current local time and the \
activity (late dinners mean PM). "noon" is 12:00, "midnight" is 00:00.
- day: "tomorrow" only if they say tomorrow or the time is clearly the next day; otherwise "today".
- minutes_from_now: for relative times ("for 2 hours", "back in 45 min"), the number of minutes; \
otherwise null. Use either back_by_time or minutes_from_now, not both.

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
            messages=[
                {
                    "role": "user",
                    "content": f"Current local time: {now:%A %Y-%m-%d %H:%M}\n\n"
                    f"Plan: <plan>{text}</plan>",
                }
            ],
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
    try:
        fields = json.loads(answer)
    except json.JSONDecodeError:
        return None
    return fields if isinstance(fields, dict) else None


# ----- Built-in reader (no AI) -----

_RELATIVE = re.compile(
    r"\b(?:for|in)\s+(an?|half an|\d+(?:\.\d+)?)\s*(hours?|hrs?|h|minutes?|mins?|m)\b", re.I
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

    relative = _RELATIVE.search(text)
    if relative:
        amount, unit = relative.group(1).lower(), relative.group(2).lower()
        number = {"a": 1.0, "an": 1.0, "half an": 0.5}.get(amount) or float(amount)
        fields["minutes_from_now"] = round(number * (60 if unit.startswith("h") else 1))

    clock = _CLOCK.search(text)
    if clock and not relative:
        hour = int(clock.group(1) or clock.group(4))
        minute = int(clock.group(2) or clock.group(5) or 0)
        suffix = (clock.group(3) or clock.group(6) or "").lower().replace(".", "")
        if suffix == "pm" and hour < 12:
            hour += 12
        elif suffix == "am" and hour == 12:
            hour = 0
        elif not suffix and hour <= 12:
            hour = _nearest_hour(hour, minute, now)
        if hour <= 23 and minute <= 59:
            fields["back_by_time"] = f"{hour:02d}:{minute:02d}"
    elif not relative:
        word = re.search(r"\b(noon|midnight)\b", text, re.I)
        if word:
            fields["back_by_time"] = _WORDS[word.group(1).lower()]

    place = _PLACE.search(text)
    if place:
        fields["destination"] = place.group(1).strip()
    return fields


def _nearest_hour(hour: int, minute: int, now: datetime) -> int:
    """'11' with no am/pm: whichever of 11:00 and 23:00 comes next (at least 5 min away)."""
    for candidate in (hour % 12, hour % 12 + 12):
        at = now.replace(hour=candidate, minute=minute, second=0, microsecond=0)
        if at - now >= EARLIEST:
            return candidate
    return hour % 12
