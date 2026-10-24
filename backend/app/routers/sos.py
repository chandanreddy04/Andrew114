"""SOS: texts your whole Circle right away, with your location."""

from datetime import timedelta

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app import alerts, sms
from app.cache import hit_rate_limit
from app.config import get_settings
from app.deps import CurrentUser, Db
from app.models import SosEvent, utcnow
from app.schemas import SosIn, SosOut

router = APIRouter(prefix="/v1/sos", tags=["sos"])

TOO_MANY = "Too many SOS alerts in the last 10 minutes. Please call someone directly."


@router.post("")
def send_sos(body: SosIn, user: CurrentUser, db: Db) -> SosOut:
    # Limit: protects against a stuck button sending dozens of texts. Checked
    # in Redis (fast, works across servers) and in the database (survives a
    # Redis restart).
    limit = get_settings().max_sos_per_10_min
    recent = db.scalar(
        select(func.count())
        .select_from(SosEvent)
        .where(SosEvent.user_id == user.id, SosEvent.created_at >= utcnow() - timedelta(minutes=10))
    )
    if (recent or 0) >= limit or hit_rate_limit(f"sos:{user.id}", limit, 600):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, TOO_MANY)

    has_location = body.latitude is not None and body.longitude is not None
    sos = SosEvent(
        user_id=user.id,
        latitude=body.latitude if has_location else None,
        longitude=body.longitude if has_location else None,
        accuracy_meters=body.accuracy_meters,
    )
    db.add(sos)
    db.commit()

    # Sent straight away (not queued): you see at once whether it worked.
    result = alerts.send_sos(db, sos)
    return SosOut(
        sent=result.sent,
        total=result.total,
        errors=result.errors,
        trial_template=sms.trial_template() is not None,
    )
