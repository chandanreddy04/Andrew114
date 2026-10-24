"""
SOS: texts your whole Circle right away, with your location and battery.

The SOS stays active (and your Circle's details page shows it) until you tap
"I'm safe", which texts them that you're OK.
"""

import secrets
import uuid
from datetime import timedelta

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app import alerts, sms
from app.cache import clear_history_cache, hit_rate_limit
from app.config import get_settings
from app.deps import CurrentUser, Db
from app.models import SosEvent, utcnow
from app.schemas import SosIn, SosOut, SosSafeOut

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
        battery_level=body.battery_level,
        share_token=secrets.token_urlsafe(24),
    )
    db.add(sos)
    db.commit()

    # Sent straight away (not queued): you see at once whether it worked.
    result = alerts.send_sos(db, sos)
    return SosOut(
        id=sos.id,
        sent=result.sent,
        total=result.total,
        errors=result.errors,
        trial_template=sms.trial_template() is not None,
    )


@router.post("/{sos_id}/safe")
def sos_safe(sos_id: uuid.UUID, user: CurrentUser, db: Db) -> SosSafeOut:
    """ "I'm safe" after an SOS: ends it and texts your Circle an all-clear (once)."""
    sos = db.get(SosEvent, sos_id)
    if sos is None or sos.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "SOS not found")
    if sos.ended_at is None:
        sos.ended_at = utcnow()
        sos.all_clear_summary = "Sending…"
        db.commit()
        sos.all_clear_summary = alerts.send_sos_all_clear(db, sos)
        db.commit()
        clear_history_cache(str(user.id))
    return SosSafeOut(
        all_clear_sent=(sos.all_clear_summary or "").startswith("Texted"),
        all_clear_summary=sos.all_clear_summary,
    )
