"""Crash reports from the phone app, passed on to Bugsnag."""

from fastapi import APIRouter, Response, status

from app.cache import hit_rate_limit
from app.deps import CurrentUser
from app.errors import report_client_error
from app.schemas import ClientErrorIn

router = APIRouter(prefix="/v1/client-errors", tags=["errors"])


@router.post("", status_code=status.HTTP_204_NO_CONTENT)
def client_error(body: ClientErrorIn, user: CurrentUser) -> Response:
    # A crash loop must not flood Bugsnag.
    if not hit_rate_limit(f"client-errors:{user.id}", 30, 3600):
        report_client_error(
            body.message,
            body.stack,
            body.is_fatal,
            {"user_id": str(user.id), "app_version": body.app_version, "platform": body.platform},
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
