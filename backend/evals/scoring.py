"""Grading a reader's answer against a case in plan_cases.py."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app import plans

ZONE = "America/New_York"
DAY = datetime(2026, 10, 27, tzinfo=ZoneInfo(ZONE))

# A time earlier than the person meant alerts their Circle while they're
# still out; a made-up time may be early too.
DANGEROUS = {"early", "made up"}


def read_case(now_text: str, text: str) -> tuple[datetime, plans.Plan | None]:
    """Read one case's plan at its time of day. The plan is None if reading crashed."""
    hour, minute = (int(part) for part in now_text.split(":"))
    now = DAY.replace(hour=hour, minute=minute)
    try:
        return now, plans.read_plan(text, now, ZONE)
    except Exception:  # a crash is a miss too; keep scoring the rest
        return now, None


def at(now: datetime, expected: str) -> datetime:
    """'23:00' today or '+00:30' tomorrow, as a time."""
    tomorrow = expected.startswith("+")
    hour, minute = (int(part) for part in expected.lstrip("+").split(":"))
    return now.replace(hour=hour, minute=minute) + timedelta(days=1 if tomorrow else 0)


def same_place(got: str | None, expected: str | None) -> bool:
    def tidy(place: str | None) -> str | None:
        if place is None:
            return None
        place = place.strip().strip(".,!").lower()
        return place.removeprefix("the ").strip() or None

    return expected == "*" or tidy(got) == tidy(expected)


def grade_time(plan: plans.Plan | None, now: datetime, expected) -> str:
    """'right', 'asked' / 'late' (safe misses), 'early' / 'made up' (dangerous), or 'crashed'."""
    if plan is None:
        return "crashed"
    choices = sorted(plan.choices)
    if expected is None:
        return "right" if plan.return_by is None and not choices else "made up"
    if isinstance(expected, tuple):
        wanted = sorted(at(now, e) for e in expected)
        if choices == wanted:
            return "right"
        if plan.return_by is None:
            return "asked"
        return "late" if plan.return_by >= wanted[-1] else "early"
    wanted_at = at(now, expected)
    if plan.return_by == wanted_at:
        return "right"
    if plan.return_by is None:
        # Offering the right time as one of two choices is a safe miss.
        return "asked"
    return "late" if plan.return_by > wanted_at else "early"
