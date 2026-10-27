"""
Address search for "Where are you going?" on Start Session.

With a Google key (settings.google_maps_api_key) this is Google Places, the
same search Google Maps, Uber and Lyft use: suggestions as you type, then
the picked place's address and position (two calls, billed by Google as one
"session" when they share a session token). Google's results aren't stored,
as its terms require.

Without a key, or if Google can't be reached, Photon is asked instead
(OpenStreetMap data, settings.places_url), with answers kept in Redis for a
day. Either way, places near the phone come first when its rough location
is given.
"""

import json
import logging

import httpx
import redis

from app.cache import get_redis
from app.config import get_settings
from app.schemas import PlaceOut

log = logging.getLogger(__name__)

CACHE_SECONDS = 24 * 60 * 60
MAX_RESULTS = 6
GOOGLE = "https://places.googleapis.com/v1"
# Prefer places within this distance of the phone (they're not limited to it).
NEARBY_METERS = 50_000.0


# ----- Google Places -----


def _google_headers(field_mask: str | None = None) -> dict[str, str]:
    headers = {"X-Goog-Api-Key": get_settings().google_maps_api_key}
    if field_mask:
        headers["X-Goog-FieldMask"] = field_mask
    return headers


def _google_search(
    query: str, near: tuple[float, float] | None, session: str | None
) -> list[PlaceOut]:
    body: dict = {"input": query, "languageCode": "en", "regionCode": "us"}
    if session:
        body["sessionToken"] = session
    if near:
        body["locationBias"] = {
            "circle": {
                "center": {"latitude": near[0], "longitude": near[1]},
                "radius": NEARBY_METERS,
            }
        }
    response = httpx.post(
        f"{GOOGLE}/places:autocomplete", json=body, headers=_google_headers(), timeout=5
    )
    response.raise_for_status()
    places: list[PlaceOut] = []
    for suggestion in response.json().get("suggestions") or []:
        prediction = suggestion.get("placePrediction")
        if not prediction or not prediction.get("placeId"):
            continue  # e.g. a "search for pizza near me" suggestion
        parts = prediction.get("structuredFormat") or {}
        name = (parts.get("mainText") or {}).get("text") or (prediction.get("text") or {}).get(
            "text"
        )
        if not name:
            continue
        places.append(
            PlaceOut(
                name=name,
                address=(parts.get("secondaryText") or {}).get("text") or "",
                place_id=prediction["placeId"],
                source="google",
            )
        )
    return places[:MAX_RESULTS]


def place_details(place_id: str, session: str | None = None) -> PlaceOut | None:
    """The full address and position of a Google result. None if it can't be found."""
    if not get_settings().google_maps_api_key:
        return None
    try:
        response = httpx.get(
            f"{GOOGLE}/places/{place_id}",
            params={"sessionToken": session} if session else None,
            headers=_google_headers("formattedAddress,location"),
            timeout=5,
        )
        response.raise_for_status()
        data = response.json()
    except (httpx.HTTPError, ValueError) as error:
        log.warning("Place details failed: %s", error)
        return None
    location = data.get("location") or {}
    if "latitude" not in location or "longitude" not in location:
        return None
    return PlaceOut(
        name="",  # the app already has the name from the suggestion
        address=data.get("formattedAddress") or "",
        latitude=location["latitude"],
        longitude=location["longitude"],
        place_id=place_id,
        source="google",
    )


# ----- Photon (OpenStreetMap) -----


def _address(props: dict) -> str:
    """e.g. "2001 South Lamar Boulevard, Austin, Texas 78745"."""
    street = " ".join(p for p in (props.get("housenumber"), props.get("street")) if p)
    city = props.get("city") or props.get("town") or props.get("village") or props.get("county")
    state = " ".join(p for p in (props.get("state"), props.get("postcode")) if p)
    parts = [street, props.get("district") or props.get("locality"), city, state]
    if props.get("countrycode") != "US":
        parts.append(props.get("country"))
    seen: list[str] = []
    for part in parts:  # drop blanks and repeats ("Austin, Austin")
        if part and part not in seen and part != props.get("name"):
            seen.append(part)
    return ", ".join(seen)


def _to_place(feature: dict) -> PlaceOut | None:
    props = feature.get("properties") or {}
    coords = (feature.get("geometry") or {}).get("coordinates") or []
    if len(coords) != 2:
        return None
    address = _address(props)
    name = props.get("name") or address
    if not name:
        return None
    return PlaceOut(
        name=name,
        address=address if address != name else "",
        latitude=coords[1],
        longitude=coords[0],
    )


def _photon_search(query: str, near: tuple[float, float] | None) -> list[PlaceOut]:
    near = (round(near[0], 1), round(near[1], 1)) if near else None
    key = f"places:{query.lower()}:{near}"
    try:
        cached = get_redis().get(key)
        if cached:
            return [PlaceOut(**p) for p in json.loads(cached)]
    except redis.RedisError:
        pass  # the cache is optional

    params: dict[str, str | int | float] = {"q": query, "limit": MAX_RESULTS, "lang": "en"}
    if near:
        params["lat"], params["lon"] = near
    try:
        response = httpx.get(
            get_settings().places_url,
            params=params,
            headers={"User-Agent": "Androyit/1.0 (safety check-in app)"},
            timeout=5,
        )
        response.raise_for_status()
        features = response.json().get("features") or []
    except (httpx.HTTPError, ValueError) as error:
        log.warning("Address search failed: %s", error)
        return []

    places: list[PlaceOut] = []
    for feature in features:
        place = _to_place(feature)
        if place and all((p.name, p.address) != (place.name, place.address) for p in places):
            places.append(place)
    try:
        get_redis().set(key, json.dumps([p.model_dump() for p in places]), ex=CACHE_SECONDS)
    except redis.RedisError:
        pass
    return places


def search(
    query: str,
    latitude: float | None = None,
    longitude: float | None = None,
    session: str | None = None,
) -> list[PlaceOut]:
    """Up to 6 places matching `query`. Empty if no search service can be reached."""
    query = " ".join(query.split())
    # About 1 km accuracy is plenty to rank nearby places first.
    near = (
        (round(latitude, 2), round(longitude, 2))
        if latitude is not None and longitude is not None
        else None
    )
    if get_settings().google_maps_api_key:
        try:
            return _google_search(query, near, session)
        except (httpx.HTTPError, ValueError) as error:
            log.warning("Google address search failed, using OpenStreetMap: %s", error)
    return _photon_search(query, near)
