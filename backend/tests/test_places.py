"""Address search, and a destination picked from it (with its map position)."""

import httpx

from app import places
from app.config import get_settings
from tests.test_api import add_contact, make_overdue, sweep
from tests.test_sessions import start, token_of

PHOTON_ANSWER = {
    "features": [
        {
            "properties": {
                "name": "Olive Garden",
                "housenumber": "2001",
                "street": "South Lamar Boulevard",
                "city": "Austin",
                "state": "Texas",
                "postcode": "78745",
                "countrycode": "US",
            },
            "geometry": {"coordinates": [-97.79, 30.24]},
        },
        {"properties": {"name": "No position"}, "geometry": {}},
    ]
}


def fake_photon(monkeypatch, answer=PHOTON_ANSWER):
    asked: list[dict] = []

    def get(url, params, headers, timeout):
        asked.append(params)
        return httpx.Response(200, json=answer, request=httpx.Request("GET", url))

    monkeypatch.setattr(places.httpx, "get", get)
    return asked


def test_search_returns_addresses_and_caches(client, user, monkeypatch):
    asked = fake_photon(monkeypatch)
    r = client.get(
        "/v1/places",
        params={"q": "olive garden", "lat": 30.27, "lng": -97.74},
        headers=user["headers"],
    )
    assert r.status_code == 200, r.text
    assert r.json() == [
        {
            "name": "Olive Garden",
            "address": "2001 South Lamar Boulevard, Austin, Texas 78745",
            "latitude": 30.24,
            "longitude": -97.79,
            "place_id": None,
            "source": "openstreetmap",
        }
    ]
    assert asked[0]["lat"] == 30.3 and asked[0]["lon"] == -97.7  # only a rough position is sent

    client.get(
        "/v1/places",
        params={"q": "Olive  Garden", "lat": 30.27, "lng": -97.74},
        headers=user["headers"],
    )
    assert len(asked) == 1  # the second search came from the cache


def test_search_needs_login_and_3_letters(client, user):
    assert client.get("/v1/places", params={"q": "olive"}).status_code == 401
    assert client.get("/v1/places", params={"q": "ol"}, headers=user["headers"]).status_code == 422


def test_search_service_down_gives_no_results(client, user, monkeypatch):
    def down(*args, **kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(places.httpx, "get", down)
    r = client.get("/v1/places", params={"q": "central park"}, headers=user["headers"])
    assert r.status_code == 200 and r.json() == []


def test_picked_destination_has_map_link_on_circle_page(client, user):
    add_contact(client, user)
    check_in_id = start(
        client,
        user,
        destination="Olive Garden, 2001 South Lamar Boulevard, Austin, Texas 78745",
        destination_latitude=30.24,
        destination_longitude=-97.79,
    )
    status = client.get(f"/v1/check-ins/{check_in_id}", headers=user["headers"]).json()
    assert status["destination_latitude"] == 30.24

    make_overdue(check_in_id)
    sweep()
    page = client.get(f"/s/{token_of(check_in_id)}").text
    assert "Olive Garden, 2001 South Lamar Boulevard" in page
    assert "query=30.24,-97.79" in page


def test_typed_destination_drops_old_map_position(client, user):
    check_in_id = start(
        client,
        user,
        destination="Olive Garden",
        destination_latitude=30.24,
        destination_longitude=-97.79,
    )
    start(client, user, destination="Gym")
    status = client.get(f"/v1/check-ins/{check_in_id}", headers=user["headers"]).json()
    assert status["destination"] == "Gym" and status["destination_latitude"] is None


GOOGLE_SUGGESTIONS = {
    "suggestions": [
        {
            "placePrediction": {
                "placeId": "ChIJolive123456",
                "text": {"text": "Olive Garden Italian Restaurant, Austin, TX, USA"},
                "structuredFormat": {
                    "mainText": {"text": "Olive Garden Italian Restaurant"},
                    "secondaryText": {"text": "South Lamar Boulevard, Austin, TX, USA"},
                },
            }
        },
        {"queryPrediction": {"text": {"text": "olive garden near me"}}},
    ]
}


def fake_google(monkeypatch):
    monkeypatch.setattr(get_settings(), "google_maps_api_key", "test-key")
    calls: list[tuple[str, dict]] = []

    def post(url, json, headers, timeout):
        calls.append((url, json))
        assert headers["X-Goog-Api-Key"] == "test-key"
        return httpx.Response(200, json=GOOGLE_SUGGESTIONS, request=httpx.Request("POST", url))

    def get(url, params, headers, timeout):
        calls.append((url, params))
        assert headers["X-Goog-FieldMask"] == "formattedAddress,location"
        answer = {
            "formattedAddress": "2001 S Lamar Blvd, Austin, TX 78704, USA",
            "location": {"latitude": 30.2449, "longitude": -97.7811},
        }
        return httpx.Response(200, json=answer, request=httpx.Request("GET", url))

    monkeypatch.setattr(places.httpx, "post", post)
    monkeypatch.setattr(places.httpx, "get", get)
    return calls


def test_google_search_then_details(client, user, monkeypatch):
    calls = fake_google(monkeypatch)
    session = "abcdef123456"
    r = client.get(
        "/v1/places",
        params={"q": "olive gard", "lat": 30.2672, "lng": -97.7431, "session": session},
        headers=user["headers"],
    )
    assert r.status_code == 200, r.text
    assert r.json() == [
        {
            "name": "Olive Garden Italian Restaurant",
            "address": "South Lamar Boulevard, Austin, TX, USA",
            "latitude": None,
            "longitude": None,
            "place_id": "ChIJolive123456",
            "source": "google",
        }
    ]
    body = calls[0][1]
    assert body["sessionToken"] == session
    assert body["locationBias"]["circle"]["center"] == {"latitude": 30.27, "longitude": -97.74}

    r = client.get(
        "/v1/places/ChIJolive123456", params={"session": session}, headers=user["headers"]
    )
    assert r.status_code == 200, r.text
    assert r.json()["address"] == "2001 S Lamar Blvd, Austin, TX 78704, USA"
    assert r.json()["latitude"] == 30.2449
    assert calls[1] == (f"{places.GOOGLE}/places/ChIJolive123456", {"sessionToken": session})


def test_google_down_falls_back_to_openstreetmap(client, user, monkeypatch):
    monkeypatch.setattr(get_settings(), "google_maps_api_key", "test-key")

    def down(*args, **kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(places.httpx, "post", down)
    fake_photon(monkeypatch)
    r = client.get("/v1/places", params={"q": "olive garden"}, headers=user["headers"])
    assert r.json()[0]["source"] == "openstreetmap"


def test_details_without_google_is_not_found(client, user):
    r = client.get("/v1/places/ChIJolive123456", headers=user["headers"])
    assert r.status_code == 404
