"""Address search for Start Session's "Where are you going?"."""

from fastapi import APIRouter, HTTPException, Query, status

from app import places
from app.cache import hit_rate_limit
from app.deps import CurrentUser
from app.schemas import PlaceOut

router = APIRouter(prefix="/v1/places", tags=["places"])

# The app searches as you type (after a short pause), so allow plenty.
SEARCHES_PER_MINUTE = 60


@router.get("")
def search_places(
    user: CurrentUser,
    q: str = Query(min_length=3, max_length=120),
    lat: float | None = Query(default=None, ge=-90, le=90),
    lng: float | None = Query(default=None, ge=-180, le=180),
) -> list[PlaceOut]:
    if hit_rate_limit(f"places:{user.id}", SEARCHES_PER_MINUTE, 60):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many searches. Wait a moment.")
    return places.search(q, lat, lng)
