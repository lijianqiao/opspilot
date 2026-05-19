from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class RedisLike(Protocol):
    async def incr(self, key: str) -> int: ...

    async def expire(self, key: str, seconds: int) -> object: ...


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    remaining: int


class RedisRateLimiter:
    """Fixed-window Redis limiter.

    The limiter is deliberately small: one Redis key per client per window.
    Stage 5 does not implement distributed fairness, token buckets, billing,
    or per-model quotas.
    """

    def __init__(self, redis: RedisLike, limit: int, window_seconds: int = 60) -> None:
        if limit < 1:
            raise ValueError("limit must be >= 1")
        self._redis = redis
        self._limit = limit
        self._window_seconds = window_seconds

    async def check(self, client_id: str) -> RateLimitResult:
        key = f"opspilot:gateway:rate:{client_id}"
        count = await self._redis.incr(key)
        if count == 1:
            await self._redis.expire(key, self._window_seconds)
        remaining = max(self._limit - count, 0)
        return RateLimitResult(allowed=count <= self._limit, remaining=remaining)
