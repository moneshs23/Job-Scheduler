import time

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware

from app.config.settings import get_settings
from app.queues.redis_client import get_redis


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Fixed-window rate limit keyed by client IP, backed by Redis so it holds across
    multiple API replicas."""

    async def dispatch(self, request: Request, call_next):
        if request.url.path in ("/health", "/metrics", "/docs", "/openapi.json"):
            return await call_next(request)

        settings = get_settings()
        if settings.environment == "test":
            # The test suite's ASGI transport and any local curl/manual testing both
            # report as the same client IP against the same dev Redis instance — without
            # this, heavy test runs get rate-limited by unrelated manual API testing.
            return await call_next(request)

        redis = get_redis()
        client_ip = request.client.host if request.client else "unknown"
        window = int(time.time() // settings.rate_limit_window_sec)
        key = f"ratelimit:{client_ip}:{window}"

        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, settings.rate_limit_window_sec)

        if count > settings.rate_limit_requests:
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Rate limit exceeded")

        return await call_next(request)
