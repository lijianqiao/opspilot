import pytest

from opspilot.gateway.rate_limit import RateLimitResult, RedisRateLimiter


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, int] = {}
        self.expirations: dict[str, int] = {}

    async def incr(self, key: str) -> int:
        self.values[key] = self.values.get(key, 0) + 1
        return self.values[key]

    async def expire(self, key: str, seconds: int) -> None:
        self.expirations[key] = seconds


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
async def test_sets_expiration_on_first_increment() -> None:
    redis = FakeRedis()
    limiter = RedisRateLimiter(redis=redis, limit=10, window_seconds=60)
    await limiter.check("client-a")
    assert redis.expirations["opspilot:gateway:rate:client-a"] == 60
