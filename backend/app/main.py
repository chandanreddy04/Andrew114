"""
Androyit API: the backend the phone app talks to (HTTP/JSON).

    Mobile app (Expo)  <->  this API (FastAPI)
                              |-- PostgreSQL  (data)
                              |-- Redis       (login codes, rate limits, cache)
                              |-- Celery      (check-in timers, alerts)
                              |-- Twilio      (texts, login codes)
                              '-- Bugsnag     (errors)

Run locally:  uvicorn app.main:app --reload
Docs:         http://localhost:8000/docs
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.cache import get_redis
from app.config import get_settings
from app.db import engine
from app.errors import bugsnag_enabled, configure_bugsnag
from app.routers import auth, check_ins, client_errors, contacts, history, me, sos

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

settings = get_settings()
configure_bugsnag()

app = FastAPI(
    title="Androyit API",
    version="1.0.0",
    # The interactive docs are handy while developing; hidden in production.
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)
if bugsnag_enabled():
    from bugsnag.asgi import BugsnagMiddleware

    app.add_middleware(BugsnagMiddleware)

for router in (auth, me, contacts, check_ins, sos, history, client_errors):
    app.include_router(router.router)


@app.get("/", tags=["health"])
def root() -> dict[str, str]:
    """Opening the server's address in a browser shows this, not "Not Found"."""
    return {
        "app": "Androyit API",
        "status": "running",
        "health": "/health",
        "docs": "/docs" if not settings.is_production else "hidden in production",
    }


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    """For the hosting provider's health check: is the database and Redis up?"""
    result = {"status": "ok", "database": "ok", "redis": "ok"}
    try:
        with engine.connect() as connection:
            connection.execute(text("select 1"))
    except Exception:  # noqa: BLE001
        result.update(status="degraded", database="down")
    try:
        get_redis().ping()
    except Exception:  # noqa: BLE001
        result.update(status="degraded", redis="down")
    return result
