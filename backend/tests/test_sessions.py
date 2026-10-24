"""Session details: destination, outfit photo, location, the Circle's page and 7-day deletion."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update

from app import sms
from app.config import get_settings
from app.db import SessionLocal
from app.models import CheckIn, SessionPhoto
from tests.test_api import add_contact, later, make_overdue, sweep

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 100
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 100


def start(client, user, **extra) -> str:
    body = {"return_by": later(), "time_zone": "America/New_York", **extra}
    r = client.put("/v1/check-ins/active", json=body, headers=user["headers"])
    assert r.status_code == 200, r.text
    return r.json()["id"]


def token_of(check_in_id: str) -> str:
    with SessionLocal() as db:
        return db.get(CheckIn, uuid.UUID(check_in_id)).share_token


def test_destination_location_and_link_in_alert(client, user, monkeypatch):
    monkeypatch.setattr(get_settings(), "public_base_url", "https://api.example.com")
    client.put("/v1/me", json={"display_name": "Alex"}, headers=user["headers"])
    add_contact(client, user)
    check_in_id = start(client, user, destination="  Central Park ", share_location=True)
    r = client.put(
        f"/v1/check-ins/{check_in_id}/location",
        json={"latitude": 40.78, "longitude": -73.97, "accuracy_meters": 20},
        headers=user["headers"],
    )
    assert r.status_code == 204

    status = client.get(f"/v1/check-ins/{check_in_id}", headers=user["headers"]).json()
    assert status["destination"] == "Central Park" and status["has_location"] is True

    make_overdue(check_in_id)
    sweep()
    text = sms.console_outbox[-1][1]
    assert "They were going to Central Park and expected to be back by" in text
    assert "query=40.78,-73.97" in text
    assert f"https://api.example.com/s/{token_of(check_in_id)}" in text


def test_plus_30_keeps_destination(client, user):
    check_in_id = start(client, user, destination="Gym")
    client.put("/v1/check-ins/active", json={"return_by": later(60)}, headers=user["headers"])
    status = client.get(f"/v1/check-ins/{check_in_id}", headers=user["headers"]).json()
    assert status["destination"] == "Gym"


def test_location_sharing_off(client, user):
    add_contact(client, user)
    check_in_id = start(client, user, share_location=False)
    r = client.put(
        f"/v1/check-ins/{check_in_id}/location",
        json={"latitude": 1, "longitude": 2},
        headers=user["headers"],
    )
    assert r.status_code == 409
    make_overdue(check_in_id)
    sweep()
    assert "google.com/maps" not in sms.console_outbox[-1][1]


def test_turning_location_off_forgets_it(client, user):
    check_in_id = start(client, user)
    client.put(
        f"/v1/check-ins/{check_in_id}/location",
        json={"latitude": 1, "longitude": 2},
        headers=user["headers"],
    )
    client.put(
        "/v1/check-ins/active",
        json={"return_by": later(), "share_location": False},
        headers=user["headers"],
    )
    with SessionLocal() as db:
        assert db.get(CheckIn, uuid.UUID(check_in_id)).latitude is None


def test_photo_upload_rules(client, user):
    check_in_id = start(client, user)
    url = f"/v1/check-ins/{check_in_id}/photo"
    ok = client.put(url, files={"photo": ("a.jpg", JPEG, "image/jpeg")}, headers=user["headers"])
    assert ok.status_code == 204
    replaced = client.put(
        url, files={"photo": ("a.png", PNG, "image/png")}, headers=user["headers"]
    )
    assert replaced.status_code == 204
    fake = client.put(
        url, files={"photo": ("x.jpg", b"<html>", "image/jpeg")}, headers=user["headers"]
    )
    assert fake.status_code == 415
    big = JPEG + b"0" * (5 * 1024 * 1024)
    too_big = client.put(
        url, files={"photo": ("b.jpg", big, "image/jpeg")}, headers=user["headers"]
    )
    assert too_big.status_code == 413

    history = client.get("/v1/history", headers=user["headers"]).json()
    assert history[0]["has_photo"] is True

    assert client.delete(url, headers=user["headers"]).status_code == 204
    status = client.get(f"/v1/check-ins/{check_in_id}", headers=user["headers"]).json()
    assert status["has_photo"] is False


def test_photo_is_private_to_its_owner(client, user):
    from tests.conftest import login

    check_in_id = start(client, user)
    other = login(client, "+15550002222", "654321")
    r = client.put(
        f"/v1/check-ins/{check_in_id}/photo",
        files={"photo": ("a.jpg", JPEG, "image/jpeg")},
        headers=other["headers"],
    )
    assert r.status_code == 404


def test_circle_page_only_during_an_alert(client, user):
    add_contact(client, user)
    check_in_id = start(client, user, destination="Central <b>Park</b>")
    client.put(
        f"/v1/check-ins/{check_in_id}/photo",
        files={"photo": ("a.jpg", JPEG, "image/jpeg")},
        headers=user["headers"],
    )
    token = token_of(check_in_id)

    # Before the check-in is missed: nothing is shown.
    assert client.get(f"/s/{token}").status_code == 404
    assert client.get(f"/s/{token}/photo").status_code == 404

    make_overdue(check_in_id)
    sweep()
    page = client.get(f"/s/{token}")
    assert page.status_code == 200
    assert "Central &lt;b&gt;Park&lt;/b&gt;" in page.text  # never raw HTML from users
    assert page.headers["x-robots-tag"].startswith("noindex")
    photo = client.get(f"/s/{token}/photo")
    assert photo.status_code == 200 and photo.content == JPEG

    # After "I'm safe": hidden again.
    client.post(f"/v1/check-ins/{check_in_id}/safe", headers=user["headers"])
    assert client.get(f"/s/{token}").status_code == 404
    assert client.get("/s/not-a-real-token-at-all-123").status_code == 404


def test_session_data_deleted_after_7_days_and_keep(client, user):
    check_in_id = start(client, user)
    client.put(
        f"/v1/check-ins/{check_in_id}/photo",
        files={"photo": ("a.jpg", JPEG, "image/jpeg")},
        headers=user["headers"],
    )
    # Still going: can't be kept, and nothing is scheduled for deletion.
    assert (
        client.post(f"/v1/check-ins/{check_in_id}/keep", headers=user["headers"]).status_code == 409
    )

    client.post(f"/v1/check-ins/{check_in_id}/safe", headers=user["headers"])
    item = client.get("/v1/history", headers=user["headers"]).json()[0]
    first = datetime.fromisoformat(item["delete_after"])
    assert timedelta(days=6, hours=23) < first - datetime.now(UTC) <= timedelta(days=7)

    kept = client.post(f"/v1/check-ins/{check_in_id}/keep", headers=user["headers"]).json()
    assert datetime.fromisoformat(kept["delete_after"]) - first == timedelta(days=7)

    # Time passes: the session and its photo are deleted.
    with SessionLocal() as db:
        db.execute(update(CheckIn).values(delete_after=datetime.now(UTC) - timedelta(seconds=1)))
        db.commit()
    assert sweep()["deleted"] == 1
    assert client.get("/v1/history", headers=user["headers"]).json() == []
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(SessionPhoto)) == 0


def test_missed_sessions_are_kept_7_days_from_missing(client, user):
    check_in_id = start(client, user)
    make_overdue(check_in_id)
    sweep()
    with SessionLocal() as db:
        c = db.get(CheckIn, uuid.UUID(check_in_id))
        assert c.delete_after - c.missed_at == timedelta(days=7)
