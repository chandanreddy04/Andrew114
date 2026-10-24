"""
The safety logic: noticing missed check-ins and texting your Circle.

Runs on the Celery worker (see app/tasks.py), so it keeps working even if
your phone dies. Safe to run any number of times at once: each text is
"claimed" (marked as sent, in one atomic database update) before sending, so
nobody is ever texted twice.
"""

import re
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app import sms
from app.cache import clear_history_cache
from app.config import get_settings
from app.models import CheckIn, Contact, SosEvent, User, utcnow

SENDING = "Sending…"
UNKNOWN_NAME = "Someone who listed you as a trusted contact"


def display_name(db: Session, user_id: uuid.UUID) -> str:
    user = db.get(User, user_id)
    return (user.display_name if user else None) or UNKNOWN_NAME


def circle_of(db: Session, user_id: uuid.UUID) -> list[tuple[str, str]]:
    rows = db.execute(
        select(Contact.name, Contact.phone)
        .where(Contact.user_id == user_id)
        .order_by(Contact.created_at)
    )
    return [(name, phone) for name, phone in rows]


def format_time(when: datetime, time_zone: str | None) -> str:
    """ "9:30 PM EDT" in the person's own time zone (falls back to UTC)."""
    try:
        zone = ZoneInfo(time_zone) if time_zone else ZoneInfo("UTC")
    except (ZoneInfoNotFoundError, ValueError):
        zone = ZoneInfo("UTC")
    local = when.astimezone(zone)
    hour = local.hour % 12 or 12
    return f"{hour}:{local.minute:02d} {'AM' if local.hour < 12 else 'PM'} {local.tzname()}"


def data_kept_until(ended: datetime) -> datetime:
    """When a session's data is deleted: N days (7) after it ended."""
    return ended + timedelta(days=get_settings().session_data_days)


def details_link(share_token: str | None) -> str | None:
    """The Circle's page with destination, outfit photo and location."""
    base = get_settings().public_base_url.rstrip("/")
    return f"{base}/s/{share_token}" if base and share_token else None


def maps_link(latitude: float | None, longitude: float | None) -> str | None:
    if latitude is None or longitude is None:
        return None
    return f"https://www.google.com/maps/search/?api=1&query={latitude},{longitude}"


def alerts_delivered(count: int | None, summary: str | None) -> int:
    """How many alert texts were delivered (older rows only have the summary)."""
    if count is not None:
        return count
    match = re.match(r"^Texted (\d+) of", summary or "")
    return int(match.group(1)) if match else 0


# ----- 1. Missed check-ins -----


def mark_missed(db: Session, check_in_id: uuid.UUID | None = None) -> int:
    """Mark overdue active check-ins (all, or just this one) as missed."""
    now = utcnow()
    query = (
        update(CheckIn)
        .where(CheckIn.status == "active", CheckIn.return_by < now)
        .values(status="missed", missed_at=now, delete_after=data_kept_until(now))
        .returning(CheckIn.user_id)
    )
    if check_in_id is not None:
        query = query.where(CheckIn.id == check_in_id)
    users = db.scalars(query).all()
    db.commit()
    for user_id in set(users):
        clear_history_cache(str(user_id))
    return len(users)


def send_missed_alerts(db: Session) -> int:
    """Text the Circle of everyone whose check-in was missed and not yet texted."""
    claimed = (
        db.execute(
            update(CheckIn)
            .where(CheckIn.status == "missed", CheckIn.alerts_sent_at.is_(None))
            .values(alerts_sent_at=utcnow(), alerts_summary=SENDING)
            .returning(CheckIn.id)
        )
        .scalars()
        .all()
    )
    db.commit()

    for check_in_id in claimed:
        check_in = db.get(CheckIn, check_in_id)
        user_id = check_in.user_id
        result = sms.text_everyone(circle_of(db, user_id), missed_message(db, check_in))
        db.execute(
            update(CheckIn)
            .where(CheckIn.id == check_in_id)
            .values(alerts_summary=result.summary, alerts_sent_count=result.sent)
        )
        db.commit()
        clear_history_cache(str(user_id))
    return len(claimed)


def missed_message(db: Session, check_in: CheckIn) -> str:
    """
    "🚨 Androyit alert: Alex hasn't checked in. They were going to Central
    Park and expected to be back by 9:30 PM EDT. Last known location: <map>
    Details and photo: <link> Please try to contact them."
    """
    name = display_name(db, check_in.user_id)
    back_by = format_time(check_in.return_by, check_in.time_zone)
    going = f"They were going to {check_in.destination} and" if check_in.destination else "They"
    parts = [
        f"🚨 Androyit alert: {name} hasn't checked in. {going} expected to be back by {back_by}."
    ]
    location = maps_link(check_in.latitude, check_in.longitude) if check_in.share_location else None
    if location:
        parts.append(f"Last known location: {location}")
    link = details_link(check_in.share_token)
    if link:
        parts.append(f"Details: {link}")
    parts.append("Please try to contact them.")
    return " ".join(parts)


# ----- 2. "All clear" after you tap "I'm safe" on a missed check-in -----


def send_all_clears(db: Session) -> int:
    """Text the Circle that you're safe, once the alerts have finished sending."""
    claimed = db.execute(
        update(CheckIn)
        .where(
            CheckIn.status == "missed",
            CheckIn.confirmed_safe_at.is_not(None),
            CheckIn.all_clear_sent_at.is_(None),
            CheckIn.alerts_sent_at.is_not(None),
            CheckIn.alerts_summary != SENDING,
        )
        .values(all_clear_sent_at=utcnow(), all_clear_summary=SENDING)
        .returning(CheckIn.id, CheckIn.user_id, CheckIn.alerts_sent_count, CheckIn.alerts_summary)
    ).all()
    db.commit()

    for check_in_id, user_id, sent_count, summary in claimed:
        # No "all clear" about an alarm nobody received.
        if alerts_delivered(sent_count, summary) == 0:
            all_clear = "Not needed: no alert was delivered"
        else:
            name = display_name(db, user_id)
            message = (
                f"✅ Update from Androyit: {name} has checked in and is safe. "
                "Thank you for looking out for them."
            )
            all_clear = sms.text_everyone(circle_of(db, user_id), message).summary
        db.execute(
            update(CheckIn).where(CheckIn.id == check_in_id).values(all_clear_summary=all_clear)
        )
        db.commit()
        clear_history_cache(str(user_id))
    return len(claimed)


def delete_expired_sessions(db: Session) -> int:
    """Delete sessions (with their photo and location) whose 7 days are up."""
    rows = (
        db.execute(
            delete(CheckIn)
            .where(CheckIn.delete_after.is_not(None), CheckIn.delete_after < utcnow())
            .returning(CheckIn.user_id)
        )
        .scalars()
        .all()
    )
    db.commit()
    for user_id in set(rows):
        clear_history_cache(str(user_id))
    return len(rows)


def process_all(db: Session) -> dict[str, int]:
    """The every-minute sweep: mark missed, send alerts, send all-clears."""
    return {
        "missed": mark_missed(db),
        "alerted": send_missed_alerts(db),
        "all_clear": send_all_clears(db),
        "deleted": delete_expired_sessions(db),
    }


# ----- 3. SOS -----


def send_sos(db: Session, sos: SosEvent) -> sms.TextEveryoneResult:
    name = display_name(db, sos.user_id)
    has_location = sos.latitude is not None and sos.longitude is not None
    message = (
        f"🆘 SOS from {name} via Androyit. "
        + (
            "Their location: https://www.google.com/maps/search/?api=1"
            f"&query={sos.latitude},{sos.longitude} "
            if has_location
            else "Their location is not available. "
        )
        + "Please contact them now."
    )
    result = sms.text_everyone(circle_of(db, sos.user_id), message)
    sos.alerts_sent_at = utcnow()
    sos.alerts_summary = result.summary
    db.commit()
    clear_history_cache(str(sos.user_id))
    return result
