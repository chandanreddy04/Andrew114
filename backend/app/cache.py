"""
Redis: short-lived data that doesn't belong in PostgreSQL.

- login codes (hashed, expire after 10 minutes, limited attempts)
- rate limits (login codes per phone, SOS per person)
- a short cache of each person's history, cleared whenever it changes
"""

import json
from functools import lru_cache

import redis

from app.config import get_settings


@lru_cache
def get_redis() -> redis.Redis:
    return redis.Redis.from_url(get_settings().redis_url, decode_responses=True)


def hit_rate_limit(key: str, limit: int, window_seconds: int) -> bool:
    """Count one more use of `key`. True if that's over `limit` in the window."""
    full_key = f"rate:{key}"
    try:
        r = get_redis()
        count = r.incr(full_key)
        if count == 1:
            r.expire(full_key, window_seconds)
    except redis.RedisError:
        # Never block an SOS because Redis is down (the SOS limit is also
        # checked in the database).
        return False
    return count > limit


HISTORY_TTL_SECONDS = 60


def _history_key(user_id: str, limit: int) -> str:
    return f"history:{user_id}:{limit}"


def get_cached_history(user_id: str, limit: int) -> list | None:
    try:
        text = get_redis().get(_history_key(user_id, limit))
    except redis.RedisError:
        return None  # the cache is optional; fall back to the database
    return json.loads(text) if text else None


def cache_history(user_id: str, limit: int, items: list) -> None:
    try:
        get_redis().set(_history_key(user_id, limit), json.dumps(items), ex=HISTORY_TTL_SECONDS)
    except redis.RedisError:
        pass


def clear_history_cache(user_id: str) -> None:
    try:
        r = get_redis()
        keys = list(r.scan_iter(f"history:{user_id}:*"))
        if keys:
            r.delete(*keys)
    except redis.RedisError:
        pass
