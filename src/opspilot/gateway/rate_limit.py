"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: rate_limit.py
@DateTime: 2026-05-20
@Docs: Fixed-window Redis rate limiter with atomic incr+TTL (per client).
    固定窗口 Redis 限流器：按客户端原子 incr+TTL，避免 key 永不过期。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class RedisLike(Protocol):
    """Minimal Redis backend for atomic fixed-window counting.

    固定窗口计数所需的最小 Redis 后端协议。

    Methods:
        incr_with_ttl: Atomically increment a key and ensure TTL.
            原子递增计数并确保 key 带有 TTL。
    """

    async def incr_with_ttl(self, key: str, ttl_seconds: int) -> int:
        """Atomically increment counter and ensure TTL is set; return new count.

        原子递增计数器并设置 TTL；返回递增后的计数值。

        Args:
            key: Redis key for this client/window.
                该客户端/窗口对应的 Redis 键。
            ttl_seconds: Window length in seconds.
                窗口长度（秒）。

        Returns:
            New counter value after increment.
                递增后的计数值。
        """
        ...


@dataclass(frozen=True)
class RateLimitResult:
    """Outcome of a single rate-limit check.

    单次限流检查的结果。

    Attributes:
        allowed: Whether the request may proceed.
            是否允许继续处理请求。
        remaining: Remaining quota in the current window (>= 0).
            当前窗口剩余配额（>= 0）。
    """

    allowed: bool
    remaining: int


class RedisRateLimiter:
    """Fixed-window Redis limiter (one key per client per window).

    固定窗口 Redis 限流器（每客户端每窗口一个键）。

    Stage 5 intentionally omits token buckets, billing, and per-model quotas.
    第五阶段刻意不实现令牌桶、计费与按模型配额。

    Args:
        redis: Backend implementing incr_with_ttl.
            实现 incr_with_ttl 的 Redis 后端。
        limit: Maximum requests allowed per window.
            每窗口允许的最大请求数。
        window_seconds: Window length in seconds (default 60).
            窗口长度（秒，默认 60）。
    """

    def __init__(self, redis: RedisLike, limit: int, window_seconds: int = 60) -> None:
        if limit < 1:
            raise ValueError("limit must be >= 1")
        self._redis = redis
        self._limit = limit
        self._window_seconds = window_seconds

    async def check(self, client_id: str) -> RateLimitResult:
        """Check and consume one unit of quota for the client.

        检查并为该客户端消耗一个配额单位。

        Args:
            client_id: Caller identifier (e.g. header or IP).
                调用方标识（如请求头或 IP）。

        Returns:
            Whether the request is allowed and remaining quota.
                是否允许请求及剩余配额。
        """
        key = f"opspilot:gateway:rate:{client_id}"
        count = await self._redis.incr_with_ttl(key, self._window_seconds)
        remaining = max(self._limit - count, 0)
        return RateLimitResult(allowed=count <= self._limit, remaining=remaining)
