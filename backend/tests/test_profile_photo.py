"""Profile picture: upload, replace, remove, and shown to the Circle in alerts."""

from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import ProfilePhoto
from tests.test_api import add_contact, make_overdue, sweep
from tests.test_sessions import JPEG, PNG, start, token_of
from tests.test_sos import press_sos, sos_token


def upload(client, user, data=JPEG, name="me.jpg"):
    return client.put(
        "/v1/me/photo", files={"photo": (name, data, "image/jpeg")}, headers=user["headers"]
    )


def test_upload_replace_and_remove(client, user):
    assert client.get("/v1/me", headers=user["headers"]).json()["photo_updated_at"] is None
    r = upload(client, user)
    assert r.status_code == 200 and r.json()["photo_updated_at"]
    assert client.get("/v1/me/photo", headers=user["headers"]).content == JPEG

    upload(client, user, PNG, "me.png")
    got = client.get("/v1/me/photo", headers=user["headers"])
    assert got.headers["content-type"] == "image/png"

    assert upload(client, user, b"not an image").status_code == 415
    gone = client.delete("/v1/me/photo", headers=user["headers"]).json()
    assert gone["photo_updated_at"] is None
    assert client.get("/v1/me/photo", headers=user["headers"]).status_code == 404


def test_login_reports_photo(client, user):
    from tests.conftest import login

    upload(client, user)
    again = login(client)
    assert again["user"]["photo_updated_at"] is not None


def test_shown_on_missed_check_in_page(client, user):
    add_contact(client, user)
    upload(client, user)
    check_in_id = start(client, user)
    token = token_of(check_in_id)
    assert client.get(f"/s/{token}/profile").status_code == 404  # no alert yet
    make_overdue(check_in_id)
    sweep()
    assert "class='profile'" in client.get(f"/s/{token}").text
    assert client.get(f"/s/{token}/profile").content == JPEG
    client.post(f"/v1/check-ins/{check_in_id}/safe", headers=user["headers"])
    assert client.get(f"/s/{token}/profile").status_code == 404


def test_shown_on_sos_page(client, user):
    add_contact(client, user)
    upload(client, user)
    sos_id = press_sos(client, user)
    token = sos_token(sos_id)
    assert "class='profile'" in client.get(f"/s/{token}").text
    assert client.get(f"/s/{token}/profile").content == JPEG
    client.post(f"/v1/sos/{sos_id}/safe", headers=user["headers"])
    assert client.get(f"/s/{token}/profile").status_code == 404


def test_no_picture_no_image_tag(client, user):
    add_contact(client, user)
    sos_id = press_sos(client, user)
    assert "class='profile'" not in client.get(f"/s/{sos_token(sos_id)}").text


def test_deleted_with_account(client, user):
    upload(client, user)
    client.delete("/v1/me", headers=user["headers"])
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(ProfilePhoto)) == 0
