"""Your past sessions and SOS alerts, newest first (only your own)."""

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.cache import cache_history, get_cached_history
from app.deps import CurrentUser, Db
from app.models import CheckIn, SessionPhoto, SosEvent
from app.schemas import HistoryCheckIn, HistorySos

router = APIRouter(prefix="/v1/history", tags=["history"])


@router.get("")
def history(
    user: CurrentUser, db: Db, limit: int = Query(default=20, ge=1, le=100)
) -> list[HistoryCheckIn | HistorySos]:
    cached = get_cached_history(str(user.id), limit)
    if cached is not None:
        return cached

    check_ins = db.scalars(
        select(CheckIn)
        .where(CheckIn.user_id == user.id)
        .order_by(CheckIn.started_at.desc())
        .limit(limit)
    ).all()
    with_photo = set(
        db.scalars(
            select(SessionPhoto.check_in_id).where(
                SessionPhoto.check_in_id.in_([c.id for c in check_ins])
            )
        )
    )
    sos_events = db.scalars(
        select(SosEvent)
        .where(SosEvent.user_id == user.id)
        .order_by(SosEvent.created_at.desc())
        .limit(limit)
    )
    items: list[HistoryCheckIn | HistorySos] = [
        HistoryCheckIn(
            id=c.id,
            destination=c.destination,
            has_photo=c.id in with_photo,
            delete_after=c.delete_after,
            at=c.started_at,
            return_by=c.return_by,
            status=c.status,
            ended_at=c.ended_at,
            alerts_summary=c.alerts_summary,
            confirmed_safe_at=c.confirmed_safe_at,
            all_clear_summary=c.all_clear_summary,
        )
        for c in check_ins
    ] + [
        HistorySos(
            at=s.created_at, alerts_summary=s.alerts_summary, had_location=s.latitude is not None
        )
        for s in sos_events
    ]
    # Newest first, then keep only the most recent `limit` overall.
    items.sort(key=lambda item: item.at, reverse=True)
    items = items[:limit]
    cache_history(str(user.id), limit, [item.model_dump(mode="json") for item in items])
    return items
