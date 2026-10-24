"""SOS: battery and details link in the text, active until "I'm safe", all-clear."""

from app import sms
from app.config import get_settings
from tests.test_api import add_contact
from tests.test_sessions import JPEG, start


def press_sos(client, user, **body):
    r = client.post("/v1/sos", json=body, headers=user["headers"])
    assert r.status_code == 200, r.text
    return r.json()["id"]


def sos_token(sos_id: str) -> str:
    import uuid

    from app.db import SessionLocal
    from app.models import SosEvent

    with SessionLocal() as db:
        return db.get(SosEvent, uuid.UUID(sos_id)).share_token


def test_sos_text_has_battery_and_details_link(client, user, monkeypatch):
    monkeypatch.setattr(get_settings(), "public_base_url", "https://api.example.com")
    client.put("/v1/me", json={"display_name": "Alex"}, headers=user["headers"])
    add_contact(client, user)
    sos_id = press_sos(client, user, latitude=1.5, longitude=2.5, battery_level=23)
    text = sms.console_outbox[-1][1]
    assert "SOS from Alex" in text and "query=1.5,2.5" in text and "Battery: 23%." in text
    assert f"https://api.example.com/s/{sos_token(sos_id)}" in text


def test_sos_page_shows_session_details_until_safe(client, user):
    add_contact(client, user)
    check_in_id = start(client, user, destination="Night market")
    client.put(
        f"/v1/check-ins/{check_in_id}/photo",
        files={"photo": ("a.jpg", JPEG, "image/jpeg")},
        headers=user["headers"],
    )
    sos_id = press_sos(client, user, latitude=1, longitude=2, battery_level=50)
    token = sos_token(sos_id)

    page = client.get(f"/s/{token}")
    assert page.status_code == 200
    assert "pressed SOS" in page.text and "Night market" in page.text and "50%" in page.text
    assert client.get(f"/s/{token}/photo").content == JPEG

    safe = client.post(f"/v1/sos/{sos_id}/safe", headers=user["headers"]).json()
    assert safe["all_clear_sent"] is True
    assert "says they're safe now" in sms.console_outbox[-1][1]
    # Tapping again doesn't text twice; the page is gone.
    before = len(sms.console_outbox)
    client.post(f"/v1/sos/{sos_id}/safe", headers=user["headers"])
    assert len(sms.console_outbox) == before
    assert client.get(f"/s/{token}").status_code == 404
    assert client.get(f"/s/{token}/photo").status_code == 404


def test_no_all_clear_when_nobody_got_the_sos(client, user):
    sos_id = press_sos(client, user)
    safe = client.post(f"/v1/sos/{sos_id}/safe", headers=user["headers"]).json()
    assert safe["all_clear_sent"] is False
    assert sms.console_outbox == []


def test_sos_safe_is_private(client, user):
    from tests.conftest import login

    sos_id = press_sos(client, user)
    other = login(client, "+15550002222", "654321")
    assert client.post(f"/v1/sos/{sos_id}/safe", headers=other["headers"]).status_code == 404


def test_bad_battery_rejected(client, user):
    r = client.post("/v1/sos", json={"battery_level": 150}, headers=user["headers"])
    assert r.status_code == 422
