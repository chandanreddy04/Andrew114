from datetime import UTC, datetime, timedelta

from sqlalchemy import update

from app import alerts, sms
from app.db import SessionLocal
from app.models import CheckIn
from tests.conftest import login


def later(minutes: float = 30) -> str:
    return (datetime.now(UTC) + timedelta(minutes=minutes)).isoformat()


def make_overdue(check_in_id: str) -> None:
    import uuid

    with SessionLocal() as db:
        db.execute(
            update(CheckIn)
            .where(CheckIn.id == uuid.UUID(check_in_id))
            .values(return_by=datetime.now(UTC) - timedelta(minutes=1))
        )
        db.commit()


def sweep() -> dict:
    with SessionLocal() as db:
        return alerts.process_all(db)


def add_contact(client, user, name="Sam", phone="+15557654321"):
    r = client.post("/v1/contacts", json={"name": name, "phone": phone}, headers=user["headers"])
    assert r.status_code == 201, r.text
    return r.json()


# ----- Login -----


def test_health(client):
    assert client.get("/health").json()["database"] == "ok"


def test_login_with_texted_code(client):
    phone = "+15551112222"
    assert client.post("/v1/auth/send-code", json={"phone": phone}).status_code == 204
    to, body = sms.console_outbox[-1]
    assert to == phone
    code = body.split("code is ")[1][:6]

    wrong = client.post(
        "/v1/auth/verify", json={"phone": phone, "code": "000000" if code != "000000" else "111111"}
    )
    assert wrong.status_code == 400

    ok = client.post("/v1/auth/verify", json={"phone": phone, "code": code})
    assert ok.status_code == 200
    assert ok.json()["user"]["phone"] == phone

    # Each code works once.
    again = client.post("/v1/auth/verify", json={"phone": phone, "code": code})
    assert again.status_code == 400


def test_phone_is_normalized_and_validated(client):
    assert client.post("/v1/auth/send-code", json={"phone": "555-1234"}).status_code == 422
    assert client.post("/v1/auth/send-code", json={"phone": "+1 (555) 111-3333"}).status_code == 204
    assert sms.console_outbox[-1][0] == "+15551113333"


def test_code_rate_limit(client):
    for _ in range(5):
        assert client.post("/v1/auth/send-code", json={"phone": "+15551114444"}).status_code == 204
    assert client.post("/v1/auth/send-code", json={"phone": "+15551114444"}).status_code == 429


def test_too_many_wrong_codes(client):
    phone = "+15551115555"
    client.post("/v1/auth/send-code", json={"phone": phone})
    code = sms.console_outbox[-1][1].split("code is ")[1][:6]
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(5):
        client.post("/v1/auth/verify", json={"phone": phone, "code": wrong})
    r = client.post("/v1/auth/verify", json={"phone": phone, "code": code})
    assert r.status_code == 400 and "Too many" in r.json()["detail"]


def test_test_number_is_never_texted(client):
    assert client.post("/v1/auth/send-code", json={"phone": "+15550001111"}).status_code == 204
    assert sms.console_outbox == []


def test_refresh_rotates_and_logout_revokes(client, user):
    r = client.post("/v1/auth/refresh", json={"refresh_token": user["refresh_token"]})
    assert r.status_code == 200
    new = r.json()
    # The old refresh token can't be used again.
    assert (
        client.post("/v1/auth/refresh", json={"refresh_token": user["refresh_token"]}).status_code
        == 401
    )

    client.post("/v1/auth/logout", json={"refresh_token": new["refresh_token"]})
    assert (
        client.post("/v1/auth/refresh", json={"refresh_token": new["refresh_token"]}).status_code
        == 401
    )


def test_requires_login(client):
    assert client.get("/v1/contacts").status_code == 401
    assert (
        client.get("/v1/contacts", headers={"Authorization": "Bearer nonsense"}).status_code == 401
    )


# ----- Profile and contacts -----


def test_profile_name(client, user):
    assert client.get("/v1/me", headers=user["headers"]).json()["display_name"] is None
    r = client.put("/v1/me", json={"display_name": "  Alex "}, headers=user["headers"])
    assert r.json()["display_name"] == "Alex"


def test_contacts_crud_and_privacy(client, user):
    sam = add_contact(client, user)
    assert [c["name"] for c in client.get("/v1/contacts", headers=user["headers"]).json()] == [
        "Sam"
    ]

    r = client.put(
        f"/v1/contacts/{sam['id']}",
        json={"name": "Sammy", "phone": "+15557654321"},
        headers=user["headers"],
    )
    assert r.json()["name"] == "Sammy"

    # Someone else can't see or change it.
    other = login(client, "+15550002222", "654321")
    assert client.get("/v1/contacts", headers=other["headers"]).json() == []
    assert client.delete(f"/v1/contacts/{sam['id']}", headers=other["headers"]).status_code == 404

    assert client.delete(f"/v1/contacts/{sam['id']}", headers=user["headers"]).status_code == 204
    assert client.get("/v1/contacts", headers=user["headers"]).json() == []


def test_contacts_block_duplicate_and_own_number(client, user):
    add_contact(client, user)
    dup = client.post(
        "/v1/contacts", json={"name": "Other", "phone": "+1 555 765 4321"}, headers=user["headers"]
    )
    assert dup.status_code == 409
    own = client.post(
        "/v1/contacts", json={"name": "Me", "phone": "+15550001111"}, headers=user["headers"]
    )
    assert own.status_code == 400


# ----- Check-ins -----


def test_check_in_safe_in_time(client, user):
    add_contact(client, user)
    r = client.put(
        "/v1/check-ins/active",
        json={"return_by": later(), "time_zone": "America/New_York"},
        headers=user["headers"],
    )
    assert r.status_code == 200
    check_in_id = r.json()["id"]

    # Moving the time keeps the same check-in.
    r2 = client.put("/v1/check-ins/active", json={"return_by": later(60)}, headers=user["headers"])
    assert r2.json()["id"] == check_in_id

    safe = client.post(f"/v1/check-ins/{check_in_id}/safe", headers=user["headers"])
    assert safe.json()["result"] == "safe"
    assert sweep()["missed"] == 0
    assert sms.console_outbox == []
    assert (
        client.get(f"/v1/check-ins/{check_in_id}", headers=user["headers"]).json()["status"]
        == "safe"
    )


def test_rejects_past_and_too_long(client, user):
    assert (
        client.put(
            "/v1/check-ins/active", json={"return_by": later(-1)}, headers=user["headers"]
        ).status_code
        == 400
    )
    assert (
        client.put(
            "/v1/check-ins/active", json={"return_by": later(8 * 24 * 60)}, headers=user["headers"]
        ).status_code
        == 400
    )


def test_missed_check_in_texts_circle_once_then_all_clear(client, user):
    client.put("/v1/me", json={"display_name": "Alex"}, headers=user["headers"])
    add_contact(client, user)
    add_contact(client, user, "Kim", "+15559876543")
    check_in_id = client.put(
        "/v1/check-ins/active",
        json={"return_by": later(), "time_zone": "America/New_York"},
        headers=user["headers"],
    ).json()["id"]

    make_overdue(check_in_id)
    result = sweep()
    assert result == {"missed": 1, "alerted": 1, "all_clear": 0, "deleted": 0}
    assert len(sms.console_outbox) == 2
    assert "Alex hasn't checked in" in sms.console_outbox[0][1]
    assert "M E" in sms.console_outbox[0][1]  # "… PM EDT" / "AM EST": local time zone

    # Running again never texts twice.
    assert sweep() == {"missed": 0, "alerted": 0, "all_clear": 0, "deleted": 0}
    assert len(sms.console_outbox) == 2

    status = client.get(f"/v1/check-ins/{check_in_id}", headers=user["headers"]).json()
    assert status["status"] == "missed" and status["alerts_summary"] == "Texted 2 of 2"

    # Tapping "I'm safe" late: stays missed, Circle gets an all-clear (once).
    safe = client.post(f"/v1/check-ins/{check_in_id}/safe", headers=user["headers"]).json()
    assert safe["result"] == "already_missed"
    assert safe["all_clear_sending"] is True
    assert len(sms.console_outbox) == 4
    assert "is safe" in sms.console_outbox[-1][1]
    client.post(f"/v1/check-ins/{check_in_id}/safe", headers=user["headers"])
    sweep()
    assert len(sms.console_outbox) == 4

    history = client.get("/v1/history", headers=user["headers"]).json()
    assert history[0]["status"] == "missed"
    assert history[0]["confirmed_safe_at"] is not None
    assert history[0]["all_clear_summary"] == "Texted 2 of 2"


def test_no_all_clear_when_nobody_was_alerted(client, user):
    check_in_id = client.put(
        "/v1/check-ins/active", json={"return_by": later()}, headers=user["headers"]
    ).json()["id"]
    make_overdue(check_in_id)
    sweep()
    safe = client.post(f"/v1/check-ins/{check_in_id}/safe", headers=user["headers"]).json()
    assert safe["all_clear_sending"] is False
    assert safe["alerts_summary"] == "No one in Circle"
    history = client.get("/v1/history", headers=user["headers"]).json()
    assert history[0]["all_clear_summary"] == "Not needed: no alert was delivered"
    assert sms.console_outbox == []


def test_new_check_in_after_missed(client, user):
    first = client.put(
        "/v1/check-ins/active", json={"return_by": later()}, headers=user["headers"]
    ).json()["id"]
    make_overdue(first)
    sweep()
    second = client.put(
        "/v1/check-ins/active", json={"return_by": later()}, headers=user["headers"]
    ).json()["id"]
    assert second != first


def test_check_in_timer_task(client, user):
    from app.tasks import check_in_due

    add_contact(client, user)
    check_in_id = client.put(
        "/v1/check-ins/active", json={"return_by": later()}, headers=user["headers"]
    ).json()["id"]
    # Before the return time (or after moving it later) the timer does nothing.
    assert check_in_due(check_in_id) == {"missed": 0, "alerted": 0}
    make_overdue(check_in_id)
    assert check_in_due(check_in_id) == {"missed": 1, "alerted": 1}
    assert len(sms.console_outbox) == 1


# ----- SOS -----


def test_sos_with_location_and_rate_limit(client, user):
    client.put("/v1/me", json={"display_name": "Alex"}, headers=user["headers"])
    add_contact(client, user)
    r = client.post(
        "/v1/sos",
        json={"latitude": 40.7, "longitude": -74.0, "accuracy_meters": 12},
        headers=user["headers"],
    )
    assert r.status_code == 200
    body = r.json()
    assert body["id"] and {k: body[k] for k in ("sent", "total", "errors", "trial_template")} == {
        "sent": 1,
        "total": 1,
        "errors": [],
        "trial_template": False,
    }
    assert "SOS from Alex" in sms.console_outbox[-1][1]
    assert "query=40.7,-74.0" in sms.console_outbox[-1][1]

    r = client.post("/v1/sos", json={}, headers=user["headers"])
    assert "not available" in sms.console_outbox[-1][1]
    client.post("/v1/sos", json={}, headers=user["headers"])
    assert client.post("/v1/sos", json={}, headers=user["headers"]).status_code == 429

    history = client.get("/v1/history", headers=user["headers"]).json()
    assert [h["kind"] for h in history] == ["sos"] * 3
    assert history[-1]["had_location"] is True


def test_sos_rejects_bad_location(client, user):
    assert (
        client.post(
            "/v1/sos", json={"latitude": 200, "longitude": 0}, headers=user["headers"]
        ).status_code
        == 422
    )


# ----- Delete account -----


def test_delete_account_removes_everything(client, user):
    add_contact(client, user)
    client.put("/v1/check-ins/active", json={"return_by": later()}, headers=user["headers"])
    client.post("/v1/sos", json={}, headers=user["headers"])
    assert client.delete("/v1/me", headers=user["headers"]).status_code == 204
    assert client.get("/v1/me", headers=user["headers"]).status_code == 401

    with SessionLocal() as db:
        from sqlalchemy import func, select

        from app.models import Contact, RefreshToken, SosEvent

        for model in (Contact, CheckIn, SosEvent, RefreshToken):
            assert db.scalar(select(func.count()).select_from(model)) == 0

    # Logging in again starts a fresh, empty account.
    again = login(client)
    assert client.get("/v1/contacts", headers=again["headers"]).json() == []


def test_client_error_report(client, user):
    r = client.post(
        "/v1/client-errors", json={"message": "boom", "is_fatal": True}, headers=user["headers"]
    )
    assert r.status_code == 204


def test_time_format():
    when = datetime(2026, 7, 1, 1, 30, tzinfo=UTC)
    assert alerts.format_time(when, "America/New_York") == "9:30 PM EDT"
    assert alerts.format_time(when, "Not/AZone") == "1:30 AM UTC"
    assert alerts.format_time(when, None) == "1:30 AM UTC"
