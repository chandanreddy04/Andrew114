"""
Bugsnag: crash and error reports, from the API, the Celery worker and the app.

Does nothing until BUGSNAG_API_KEY is set. Phone numbers and tokens are
filtered out of reports.
"""

import logging

import bugsnag

from app.config import get_settings

log = logging.getLogger("reached")


def bugsnag_enabled() -> bool:
    return bool(get_settings().bugsnag_api_key)


def configure_bugsnag() -> None:
    s = get_settings()
    if not s.bugsnag_api_key:
        return
    bugsnag.configure(
        api_key=s.bugsnag_api_key,
        release_stage=s.environment,
        project_root=__file__.rsplit("app", 1)[0],
        params_filters=["phone", "code", "password", "token", "authorization", "refresh_token"],
    )


def set_up_celery_errors() -> None:
    configure_bugsnag()
    if bugsnag_enabled():
        from bugsnag.celery import connect_failure_handler

        connect_failure_handler()


def report_client_error(
    message: str, stack: str | None, fatal: bool, metadata: dict[str, object]
) -> None:
    """An error from the phone app (sent to POST /v1/client-errors)."""
    log.warning("App error%s: %s", " (fatal)" if fatal else "", message)
    if not bugsnag_enabled():
        return

    class AppError(Exception):
        pass

    bugsnag.notify(
        AppError(message),
        severity="error" if fatal else "warning",
        context="mobile-app",
        metadata={"app": {**metadata, "stack": stack, "fatal": fatal}},
    )
