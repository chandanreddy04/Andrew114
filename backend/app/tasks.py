"""
Celery: the timers and alerts that run in the background.

- check_in_due: scheduled for the exact return time of each check-in, so your
  Circle is texted on time.
- sweep: runs every minute (Celery beat) as a safety net, e.g. if the worker
  was restarted and lost its timers.
- send_all_clear: right after you tap "I'm safe" on a missed check-in.

Start the worker:  celery -A app.tasks worker --loglevel=info
Start the timer:   celery -A app.tasks beat --loglevel=info
"""

import logging
import uuid
from datetime import datetime, timedelta

from celery import Celery

from app import alerts
from app.config import get_settings
from app.db import SessionLocal
from app.errors import set_up_celery_errors

settings = get_settings()

celery_app = Celery("reached", broker=settings.redis_url, backend=None)
celery_app.conf.update(
    task_always_eager=settings.celery_always_eager,
    task_acks_late=True,  # a crashed worker's task is retried, not lost
    worker_prefetch_multiplier=1,
    timezone="UTC",
    # Timers for long check-ins (hours ahead) must not be re-delivered early.
    broker_transport_options={"visibility_timeout": 7 * 24 * 3600},
    beat_schedule={
        "sweep-every-minute": {"task": "reached.sweep", "schedule": 60.0},
    },
)
set_up_celery_errors()
log = logging.getLogger("reached")


@celery_app.task(name="reached.check_in_due")
def check_in_due(check_in_id: str) -> dict[str, int]:
    with SessionLocal() as db:
        missed = alerts.mark_missed(db, uuid.UUID(check_in_id))
        # Nothing to do if you checked in, or moved the time later (a new
        # timer was scheduled for that).
        alerted = alerts.send_missed_alerts(db) if missed else 0
    return {"missed": missed, "alerted": alerted}


@celery_app.task(name="reached.sweep")
def sweep() -> dict[str, int]:
    with SessionLocal() as db:
        return alerts.process_all(db)


@celery_app.task(name="reached.send_all_clear")
def send_all_clear() -> int:
    with SessionLocal() as db:
        return alerts.send_all_clears(db)


def schedule_check_in_timer(check_in_id: uuid.UUID, return_by: datetime) -> None:
    """Ask the worker to check this check-in a moment after its return time."""
    if settings.celery_always_eager:
        return  # tests run the sweep by hand instead of waiting
    try:
        check_in_due.apply_async(args=[str(check_in_id)], eta=return_by + timedelta(seconds=2))
    except Exception:  # noqa: BLE001 - the every-minute sweep still catches it
        log.exception("Could not schedule check-in timer")


def queue_all_clear() -> None:
    try:
        send_all_clear.delay()
    except Exception:  # noqa: BLE001 - the every-minute sweep still sends it
        log.exception("Could not queue all-clear")
