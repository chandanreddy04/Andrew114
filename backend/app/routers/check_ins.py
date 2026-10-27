"""
Check-ins ("sessions"): tell the server when you expect to be back.

The server keeps watching even if your phone dies. If you don't tap "I'm
safe" by your return time, it marks the check-in missed and texts your Circle
(see app/alerts.py and app/tasks.py).

A session can also carry where you're going, an outfit photo and your last
known location. These are only shown to your Circle if an alert triggers
(app/routers/share.py), and deleted 7 days after the session ends.
"""

import secrets
import uuid
from datetime import timedelta

from fastapi import APIRouter, HTTPException, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app import alerts, tasks
from app.cache import clear_history_cache
from app.config import get_settings
from app.deps import CurrentUser, Db
from app.models import CheckIn, SessionPhoto, utcnow
from app.photos import read_photo
from app.schemas import (
    CheckInIn,
    CheckInStartedOut,
    CheckInStatusOut,
    ConfirmSafeOut,
    KeepOut,
    LocationIn,
)

router = APIRouter(prefix="/v1/check-ins", tags=["check-ins"])

MAX_LENGTH = timedelta(days=7)


@router.put("/active")
def start_or_update(body: CheckInIn, user: CurrentUser, db: Db) -> CheckInStartedOut:
    """
    Start a check-in, or move the return time of the one that's already active
    (you can only have one active check-in at a time).
    """
    return_by = body.return_by
    if return_by.tzinfo is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "return_by needs a time zone")
    now = utcnow()
    if return_by <= now:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The return time has already passed.")
    if return_by - now > MAX_LENGTH:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "A check-in can last at most 7 days.")

    check_in = db.scalar(
        select(CheckIn)
        .where(CheckIn.user_id == user.id, CheckIn.status == "active")
        .with_for_update()
    )
    if check_in is None:
        check_in = CheckIn(
            user_id=user.id,
            return_by=return_by,
            time_zone=body.time_zone,
            share_location=True,
            share_token=secrets.token_urlsafe(24),
        )
        db.add(check_in)
    else:
        check_in.return_by = return_by
        check_in.time_zone = body.time_zone
    # Only change what was sent (the +30m buttons send just the time).
    if "destination" in body.model_fields_set:
        check_in.destination = body.destination
        has_place = body.destination is not None and body.destination_latitude is not None
        check_in.destination_latitude = body.destination_latitude if has_place else None
        check_in.destination_longitude = body.destination_longitude if has_place else None
    if "share_location" in body.model_fields_set and body.share_location is not None:
        check_in.share_location = body.share_location
        if not body.share_location:  # switched off: forget it straight away
            check_in.latitude = check_in.longitude = check_in.accuracy_meters = None
            check_in.location_at = None
    try:
        db.commit()
    except IntegrityError as error:  # two "start" taps at once
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "A check-in is already active.") from error

    tasks.schedule_check_in_timer(check_in.id, check_in.return_by)
    clear_history_cache(str(user.id))
    return CheckInStartedOut(id=check_in.id, status=check_in.status)


def _own(db: Db, user_id: uuid.UUID, check_in_id: uuid.UUID, lock: bool = False) -> CheckIn:
    query = select(CheckIn).where(CheckIn.id == check_in_id, CheckIn.user_id == user_id)
    check_in = db.scalar(query.with_for_update() if lock else query)
    if check_in is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Check-in not found")
    return check_in


@router.get("/{check_in_id}")
def get_status(check_in_id: uuid.UUID, user: CurrentUser, db: Db) -> CheckInStatusOut:
    c = _own(db, user.id, check_in_id)
    return CheckInStatusOut(
        id=c.id,
        status=c.status,
        return_by=c.return_by,
        alerts_sent_at=c.alerts_sent_at,
        alerts_summary=c.alerts_summary,
        destination=c.destination,
        destination_latitude=c.destination_latitude,
        destination_longitude=c.destination_longitude,
        share_location=c.share_location,
        has_location=c.latitude is not None,
        has_photo=db.get(SessionPhoto, c.id) is not None,
    )


def _still_going(c: CheckIn) -> None:
    """Location and photo can only change while the session isn't over."""
    if c.status == "safe" or c.confirmed_safe_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This session has already ended.")


@router.put("/{check_in_id}/location", status_code=status.HTTP_204_NO_CONTENT)
def update_location(
    check_in_id: uuid.UUID, body: LocationIn, user: CurrentUser, db: Db
) -> Response:
    """Your last known location, shared with your Circle only if an alert triggers."""
    c = _own(db, user.id, check_in_id, lock=True)
    _still_going(c)
    if not c.share_location:
        raise HTTPException(status.HTTP_409_CONFLICT, "Location sharing is off for this session.")
    c.latitude, c.longitude = body.latitude, body.longitude
    c.accuracy_meters = body.accuracy_meters
    c.location_at = utcnow()
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/{check_in_id}/photo", status_code=status.HTTP_204_NO_CONTENT)
async def upload_photo(
    check_in_id: uuid.UUID, photo: UploadFile, user: CurrentUser, db: Db
) -> Response:
    """The outfit photo (JPEG or PNG, at most 5 MB). Replaces any earlier one."""
    c = _own(db, user.id, check_in_id, lock=True)
    _still_going(c)
    content, content_type = await read_photo(photo)
    existing = db.get(SessionPhoto, c.id)
    if existing is None:
        db.add(SessionPhoto(check_in_id=c.id, content_type=content_type, content=content))
    else:
        existing.content_type, existing.content = content_type, content
        existing.created_at = utcnow()
    db.commit()
    clear_history_cache(str(user.id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{check_in_id}/photo", status_code=status.HTTP_204_NO_CONTENT)
def delete_photo(check_in_id: uuid.UUID, user: CurrentUser, db: Db) -> Response:
    c = _own(db, user.id, check_in_id)
    existing = db.get(SessionPhoto, c.id)
    if existing is not None:
        db.delete(existing)
        db.commit()
        clear_history_cache(str(user.id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


MAX_KEEP = timedelta(days=90)


@router.post("/{check_in_id}/keep")
def keep_longer(check_in_id: uuid.UUID, user: CurrentUser, db: Db) -> KeepOut:
    """Session History's "Keep 7 more days" (at most 90 days from now)."""
    c = _own(db, user.id, check_in_id, lock=True)
    if c.delete_after is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This session is still going.")
    now = utcnow()
    extended = max(c.delete_after, now) + timedelta(days=get_settings().session_data_days)
    c.delete_after = min(extended, now + MAX_KEEP)
    db.commit()
    clear_history_cache(str(user.id))
    return KeepOut(delete_after=c.delete_after)


@router.post("/{check_in_id}/safe")
def confirm_safe(check_in_id: uuid.UUID, user: CurrentUser, db: Db) -> ConfirmSafeOut:
    """
    "I'm safe".
      - still active  -> marked 'safe' (nobody was alerted)
      - already missed -> remembered, so an "all clear" text goes to your
                          Circle; the check-in stays 'missed' in your history
    Returns what really happened, so the app can tell you the truth.
    """
    c = _own(db, user.id, check_in_id, lock=True)

    if c.status == "active":
        c.status = "safe"
        c.ended_at = utcnow()
        c.delete_after = alerts.data_kept_until(c.ended_at)
        db.commit()
        clear_history_cache(str(user.id))
        return ConfirmSafeOut(result="safe")

    if c.status == "missed":
        if c.confirmed_safe_at is None:
            c.confirmed_safe_at = utcnow()
            c.delete_after = alerts.data_kept_until(c.confirmed_safe_at)
        db.commit()
        clear_history_cache(str(user.id))
        delivered = alerts.alerts_delivered(c.alerts_sent_count, c.alerts_summary)
        all_clear_pending = c.all_clear_sent_at is None
        if all_clear_pending:
            tasks.queue_all_clear()  # the every-minute sweep would also send it
        return ConfirmSafeOut(
            result="already_missed",
            alerts_sent_at=c.alerts_sent_at,
            alerts_summary=c.alerts_summary,
            alerts_sent_count=c.alerts_sent_count,
            all_clear_sending=delivered > 0 and all_clear_pending,
        )

    db.commit()
    return ConfirmSafeOut(result="safe")  # already safe (tapped twice)
