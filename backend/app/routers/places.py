"""Address search for Start Session's "Where are you going?", and the map preview."""

import base64

from fastapi import APIRouter, HTTPException, Path, Query, status

from app import places
from app.cache import hit_rate_limit
from app.deps import CurrentUser
from app.schemas import MapPreviewOut, PlaceOut

router = APIRouter(prefix="/v1/places", tags=["places"])

# The app searches as you type (after a short pause), so allow plenty.
SEARCHES_PER_MINUTE = 60
# One search "session" (typing, then picking a place) for Google's billing.
SESSION = Query(default=None, pattern=r"^[A-Za-z0-9_-]{8,64}$")


def _limit(user: CurrentUser) -> None:
    if hit_rate_limit(f"places:{user.id}", SEARCHES_PER_MINUTE, 60):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many searches. Wait a moment.")


@router.get("")
def search_places(
    user: CurrentUser,
    q: str = Query(min_length=3, max_length=120),
    lat: float | None = Query(default=None, ge=-90, le=90),
    lng: float | None = Query(default=None, ge=-180, le=180),
    session: str | None = SESSION,
) -> list[PlaceOut]:
    _limit(user)
    return places.search(q, lat, lng, session)


@router.get("/map-preview")
def map_preview(
    user: CurrentUser,
    lat: float = Query(ge=-90, le=90),
    lng: float = Query(ge=-180, le=180),
    width: int = Query(default=720, ge=100, le=1200),
    height: int = Query(default=336, ge=100, le=1200),
) -> MapPreviewOut:
    """A small street map of where you are, shown under the Location switch.

    Your position is only passed on to draw the map; it isn't saved.
    """
    _limit(user)
    image = places.map_image(lat, lng, width, height)
    if image is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "The map isn't available.")
    return MapPreviewOut(image=f"data:image/jpeg;base64,{base64.b64encode(image).decode()}")


@router.get("/{place_id}")
def place_details(
    user: CurrentUser,
    place_id: str = Path(pattern=r"^[A-Za-z0-9_-]{10,300}$"),
    session: str | None = SESSION,
) -> PlaceOut:
    """The full address and map position of a search result that came without one."""
    _limit(user)
    place = places.place_details(place_id, session)
    if place is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Place not found")
    return place
