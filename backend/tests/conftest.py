"""
Test setup: an in-memory SQLite database (or real PostgreSQL if
TEST_DATABASE_URL is set), a fake Redis, Celery tasks run in-process, and
texts go to sms.console_outbox.
"""

import os

os.environ.update(
    DATABASE_URL=os.environ.get("TEST_DATABASE_URL", "sqlite://"),
    SMS_BACKEND="console",
    CELERY_ALWAYS_EAGER="true",
    JWT_SECRET="test-secret-test-secret-test-secret",
    TEST_PHONE_NUMBERS="+15550001111=123456,+15550002222=654321",
    BUGSNAG_API_KEY="",
    TWILIO_TRIAL_TEMPLATE="",
)

import fakeredis  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import cache, sms  # noqa: E402
from app.db import Base, engine  # noqa: E402

fake = fakeredis.FakeRedis(decode_responses=True)
cache.get_redis.cache_clear()
cache.get_redis = lambda: fake  # type: ignore[assignment]
import app.otp  # noqa: E402

app.otp.get_redis = cache.get_redis  # type: ignore[attr-defined]

from app.main import app as fastapi_app  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_state():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    fake.flushall()
    sms.console_outbox.clear()
    yield


@pytest.fixture
def client() -> TestClient:
    return TestClient(fastapi_app)


def login(client: TestClient, phone: str = "+15550001111", code: str = "123456") -> dict:
    response = client.post("/v1/auth/verify", json={"phone": phone, "code": code})
    assert response.status_code == 200, response.text
    data = response.json()
    data["headers"] = {"Authorization": f"Bearer {data['access_token']}"}
    return data


@pytest.fixture
def user(client: TestClient) -> dict:
    return login(client)
