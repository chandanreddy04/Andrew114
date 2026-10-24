"""
Run the whole backend on your laptop WITHOUT Docker, PostgreSQL or Redis:

    python scripts/dev_server.py

- data is kept in a local SQLite file (backend/dev.db)
- Redis is replaced by an in-memory fake (login codes are lost on restart)
- instead of a Celery worker, a background thread runs the missed-check-in
  sweep every 15 seconds
- texts are printed here (SMS_BACKEND=console) unless backend/.env says otherwise
- everything printed is also saved to backend/dev-server.log

Good for trying the app quickly. For anything real, use docker compose.
"""

import os
import sys
import threading
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)

os.environ.setdefault("DATABASE_URL", f"sqlite:///{(BACKEND / 'dev.db').as_posix()}")
os.environ.setdefault("CELERY_ALWAYS_EAGER", "true")
os.environ.setdefault("TEST_PHONE_NUMBERS", "+15550001111=123456")
os.environ.setdefault("JWT_SECRET", "dev-only-secret-not-for-production-use-0000")


def _lan_address() -> str:
    """This laptop's Wi-Fi address, for the details link in alert texts."""
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("192.0.2.1", 80))  # no packet is sent; just picks the route
            return s.getsockname()[0]
        except OSError:
            return "localhost"


os.environ.setdefault(
    "PUBLIC_BASE_URL", f"http://{_lan_address()}:{os.environ.get('PORT', '8000')}"
)

import logging  # noqa: E402

import fakeredis  # noqa: E402
import uvicorn  # noqa: E402

from app import cache  # noqa: E402

fake = fakeredis.FakeRedis(decode_responses=True)
cache.get_redis = lambda: fake  # type: ignore[assignment]

import app.otp  # noqa: E402

app.otp.get_redis = cache.get_redis  # type: ignore[attr-defined]

from app import alerts  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402


def upgrade_database() -> None:
    """Bring dev.db up to date (it was first made without migrations)."""
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import inspect

    config = Config(str(BACKEND / "alembic.ini"))
    tables = inspect(engine).get_table_names()
    if "users" not in tables:
        Base.metadata.create_all(engine)
        command.stamp(config, "head")
        return
    if "alembic_version" not in tables:
        command.stamp(config, "0001")  # made by create_all before migration 0002
    command.upgrade(config, "head")


upgrade_database()
# Alembic's logging settings turn routine messages off; turn them back on so
# texts and crash reports are shown.
logging.getLogger().setLevel(logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)  # its URLs include the Twilio id

# Also keep the log in a file (backend/dev-server.log), e.g. to read crash
# reports from the app after the window was closed.
_file_log = logging.FileHandler(BACKEND / "dev-server.log", encoding="utf-8")
_file_log.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
logging.getLogger().addHandler(_file_log)


def sweep_forever() -> None:
    while True:
        time.sleep(15)
        try:
            with SessionLocal() as db:
                result = alerts.process_all(db)
            if any(result.values()):
                print("sweep:", result, flush=True)
        except Exception as error:  # noqa: BLE001
            print("sweep failed:", error, flush=True)


threading.Thread(target=sweep_forever, daemon=True).start()

if __name__ == "__main__":
    uvicorn.run(fastapi_app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
