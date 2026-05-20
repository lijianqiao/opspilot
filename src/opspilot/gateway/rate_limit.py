"""Gateway rate limiter (fixed-window).

审查报告：原 check() 用 incr + (仅 count==1 时) expire 两步，两步间崩溃则 key
永不过期 → 该 client 永久被限流。改为单一原子调用 incr_with_ttl，由后端
（redis pipeline / Lua / EXPIRE NX）保证 atomic；fake 实现也只需一个方法。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class RedisLike(Protocol):
    async def incr_with_ttl(self, key: str, ttl_seconds: int) -> int:
        """Atomically increment counter and ensure TTL is set; return new count."""
        ...


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
        count = await self._redis.incr_with_ttl(key, self._window_seconds)
        remaining = max(self._limit - count, 0)
        return RateLimitResult(allowed=count <= self._limit, remaining=remaining)
