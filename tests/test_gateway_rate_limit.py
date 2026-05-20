"""
@Author: li
@Email: lijianqiao2906@live.com
@FileName: test_gateway_rate_limit.py
@DateTime: 2026-05-20
@Docs: Tests Redis fixed-window rate limiter atomicity.
    测试 Redis 固定窗口限流原子性。
"""

import pytest

from opspilot.gateway.rate_limit import RateLimitResult, RedisRateLimiter


class FakeRedis:
    """Test double for RedisLike.

    incr_with_ttl 模拟原子操作：自增计数 + 总是更新 TTL（生产实现用
    redis pipeline + EXPIRE NX 或 Lua 脚本，保证原子）。
    """

    def __init__(self) -> None:
        self.values: dict[str, int] = {}
        self.expirations: dict[str, int] = {}
        self.call_log: list[tuple[str, int]] = []

    async def incr_with_ttl(self, key: str, ttl_seconds: int) -> int:
        self.values[key] = self.values.get(key, 0) + 1
        # 关键：每次都保证 TTL 存在（与生产实现一致）。即便首调失败也不会丢 TTL。
        self.expirations[key] = ttl_seconds
        self.call_log.append((key, ttl_seconds))
        return self.values[key]


@pytest.mark.anyio
async def test_allows_requests_until_limit() -> None:
    redis = FakeRedis()
    limiter = RedisRateLimiter(redis=redis, limit=2, window_seconds=60)
    assert await limiter.check("client-a") == RateLimitResult(allowed=True, remaining=1)
    assert await limiter.check("client-a") == RateLimitResult(allowed=True, remaining=0)


@pytest.mark.anyio
async def test_blocks_after_limit() -> None:
    redis = FakeRedis()
    limiter = RedisRateLimiter(redis=redis, limit=1, window_seconds=60)
    assert (await limiter.check("client-a")).allowed is True
    result = await limiter.check("client-a")
    assert result.allowed is False
    assert result.remaining == 0


@pytest.mark.anyio
async def test_ttl_set_atomically_with_every_incr() -> None:
    # 审查报告：原实现 incr 后只在 count==1 时 expire，两步间崩溃则 key 永不过期。
    # 新实现要求 incr_with_ttl 是单一原子调用 → 每次调用都会更新 TTL。
    redis = FakeRedis()
    limiter = RedisRateLimiter(redis=redis, limit=10, window_seconds=60)
    for _ in range(5):
        await limiter.check("client-a")
    assert redis.expirations["opspilot:gateway:rate:client-a"] == 60
    # 每次 check 都恰好一次 incr_with_ttl（无两步分离）
    assert len(redis.call_log) == 5
