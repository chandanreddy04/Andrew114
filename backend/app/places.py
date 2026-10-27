"""
Address search for "Where are you going?" on Start Session.

Asks Photon (OpenStreetMap data, see settings.places_url) and keeps each
answer in Redis for a day, so the same search isn't sent out twice. Results
near the phone come first when its rough location is given.
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


def search(
    query: str, latitude: float | None = None, longitude: float | None = None
) -> list[PlaceOut]:
    """Up to 6 places matching `query`. Empty if the search service can't be reached."""
    query = " ".join(query.split())
    near = (
        (round(latitude, 1), round(longitude, 1))
        if latitude is not None and longitude is not None
        else None
    )
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
