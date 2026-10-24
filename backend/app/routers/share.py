"""
The page your Circle opens from an alert text (/s/<token>): where you were
going, your outfit photo, your last known location and when you were due.

It only works while the alert is real: after the check-in was missed (or
while an SOS is active) and before you tapped "I'm safe". Before that, and
after, it shows nothing about you. The link is long and random, and the page
tells search engines to stay away.
"""

from datetime import timedelta
from html import escape

from fastapi import APIRouter, HTTPException, Response, status
from fastapi.responses import HTMLResponse
from sqlalchemy import select

from app import alerts
from app.deps import Db
from app.models import CheckIn, SessionPhoto, SosEvent, utcnow

router = APIRouter(tags=["share"], include_in_schema=False)

PRIVATE = {"Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow"}
# An SOS link stops working after this long, even if "I'm safe" was never tapped.
SOS_LINK_HOURS = 24


def _alerting(db: Db, token: str) -> CheckIn | None:
    if len(token) < 20:
        return None
    check_in = db.scalar(select(CheckIn).where(CheckIn.share_token == token))
    if check_in is None or check_in.status != "missed" or check_in.confirmed_safe_at:
        return None
    return check_in


def _active_sos(db: Db, token: str) -> SosEvent | None:
    if len(token) < 20:
        return None
    sos = db.scalar(select(SosEvent).where(SosEvent.share_token == token))
    if sos is None or sos.ended_at is not None:
        return None
    if sos.created_at < utcnow() - timedelta(hours=SOS_LINK_HOURS):
        return None
    return sos


def _current_session(db: Db, user_id) -> CheckIn | None:
    """The session that's going (or missed and not yet resolved), for SOS pages."""
    return db.scalar(
        select(CheckIn)
        .where(
            CheckIn.user_id == user_id,
            CheckIn.status.in_(("active", "missed")),
            CheckIn.confirmed_safe_at.is_(None),
        )
        .order_by(CheckIn.started_at.desc())
    )


def _sos_page(db: Db, sos: SosEvent, token: str) -> HTMLResponse:
    name = escape(alerts.display_name(db, sos.user_id))
    session = _current_session(db, sos.user_id)
    zone = session.time_zone if session else None
    when = escape(alerts.format_time(sos.created_at, zone))
    rows = [f"<p class='alert'>{name} pressed SOS at {when}.</p>"]
    if session and session.destination:
        rows.append(f"<h2>Where they were going</h2><p>{escape(session.destination)}</p>")
    location = alerts.maps_link(sos.latitude, sos.longitude)
    if location:
        rows.append(
            f"<h2>Location when they pressed SOS</h2>"
            f"<p><a href='{escape(location)}'>Open in Google Maps</a></p>"
        )
    if sos.battery_level is not None:
        rows.append(f"<h2>Phone battery</h2><p>{sos.battery_level}%</p>")
    if session and db.get(SessionPhoto, session.id) is not None:
        rows.append(
            f"<h2>What they were wearing</h2>"
            f"<img src='/s/{escape(token)}/photo' alt='Outfit photo'>"
        )
    rows.append("<p><strong>Please contact them now.</strong></p>")
    return HTMLResponse(_page(f"SOS from {name}", "".join(rows)), headers=PRIVATE)


@router.get("/s/{token}", response_class=HTMLResponse)
def details_page(token: str, db: Db) -> HTMLResponse:
    sos = _active_sos(db, token)
    if sos is not None:
        return _sos_page(db, sos, token)
    check_in = _alerting(db, token)
    if check_in is None:
        return HTMLResponse(
            _page(
                "Nothing to show",
                "<p>There's no active alert at this link. "
                "If you were worried about someone, try calling them.</p>",
            ),
            status_code=status.HTTP_404_NOT_FOUND,
            headers=PRIVATE,
        )

    name = escape(alerts.display_name(db, check_in.user_id))
    back_by = escape(alerts.format_time(check_in.return_by, check_in.time_zone))
    rows = [
        f"<p class='alert'>{name} hasn't checked in. They expected to be back by {back_by}.</p>"
    ]
    if check_in.destination:
        rows.append(f"<h2>Where they were going</h2><p>{escape(check_in.destination)}</p>")
    location = (
        alerts.maps_link(check_in.latitude, check_in.longitude) if check_in.share_location else None
    )
    if location:
        when = escape(alerts.format_time(check_in.location_at, check_in.time_zone))
        rows.append(
            f"<h2>Last known location</h2><p><a href='{escape(location)}'>Open in Google Maps</a>"
            f" <span class='muted'>(from {when})</span></p>"
        )
    if db.get(SessionPhoto, check_in.id) is not None:
        rows.append(
            f"<h2>What they were wearing</h2>"
            f"<img src='/s/{escape(token)}/photo' alt='Outfit photo'>"
        )
    rows.append("<p><strong>Please try to contact them.</strong></p>")
    return HTMLResponse(_page(f"{name} needs checking on", "".join(rows)), headers=PRIVATE)


@router.get("/s/{token}/photo")
def details_photo(token: str, db: Db) -> Response:
    sos = _active_sos(db, token)
    check_in = _current_session(db, sos.user_id) if sos else _alerting(db, token)
    photo = db.get(SessionPhoto, check_in.id) if check_in else None
    if photo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    return Response(photo.content, media_type=photo.content_type, headers=PRIVATE)


def _page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>Androyit alert</title>
<style>
  body {{ font-family: system-ui, sans-serif; margin: 0; padding: 24px 16px;
         background: #F5F7FA; color: #2C3E50; }}
  main {{ max-width: 520px; margin: 0 auto; background: #fff; border-radius: 20px;
         padding: 24px; box-shadow: 0 2px 12px rgba(0,0,0,.06); }}
  h1 {{ font-size: 22px; margin: 0 0 12px; }}
  h2 {{ font-size: 15px; color: #7B8794; margin: 20px 0 4px; }}
  .alert {{ background: #E5484D; color: #fff; padding: 12px 14px; border-radius: 12px; }}
  .muted {{ color: #7B8794; }}
  a {{ color: #14A38B; font-weight: 600; }}
  img {{ max-width: 100%; border-radius: 12px; }}
</style></head>
<body><main><h1>{title}</h1>{body}</main></body></html>"""
