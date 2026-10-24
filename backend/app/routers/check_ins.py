"""
Check-ins ("sessions"): tell the server when you expect to be back.

The server keeps watching even if your phone dies. If you don't tap "I'm
safe" by your return time, it marks the check-in missed and texts your Circle
(see app/alerts.py and app/tasks.py).
"""

import uuid
from datetime import timedelta

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app import alerts, tasks
from app.cache import clear_history_cache
from app.deps import CurrentUser, Db
from app.models import CheckIn, utcnow
from app.schemas import CheckInIn, CheckInStartedOut, CheckInStatusOut, ConfirmSafeOut

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
        check_in = CheckIn(user_id=user.id, return_by=return_by, time_zone=body.time_zone)
        db.add(check_in)
    else:
        check_in.return_by = return_by
        check_in.time_zone = body.time_zone
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
    )


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
        db.commit()
        clear_history_cache(str(user.id))
        return ConfirmSafeOut(result="safe")

    if c.status == "missed":
        if c.confirmed_safe_at is None:
            c.confirmed_safe_at = utcnow()
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
