"""
Run the whole backend on your laptop WITHOUT Docker, PostgreSQL or Redis:

    python scripts/dev_server.py

- data is kept in a local SQLite file (backend/dev.db)
- Redis is replaced by an in-memory fake (login codes are lost on restart)
- instead of a Celery worker, a background thread runs the missed-check-in
  sweep every 15 seconds
- texts are printed here (SMS_BACKEND=console) unless backend/.env says otherwise

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

Base.metadata.create_all(engine)


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
