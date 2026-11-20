import logging
import math

import redis
from fastapi import HTTPException, Request, Response, status

from animal_finder.cache import RedisCache

logger = logging.getLogger(__name__)


class RateLimit:
    """
    Per-IP token-bucket rate limit, used as a route dependency:

        @app.post("/chat/stream", dependencies=[Depends(RateLimit("chat", 10, 0.2))])

    Each instance's `scope` namespaces its buckets, so endpoints with different
    RateLimit instances don't share tokens. Allows bursts of up to `capacity`
    requests, then `refill_rate` requests per second.

    This is a dependency rather than a decorator: on a generator (streaming)
    endpoint, a wrapper would only run once streaming starts, after the 200 status
    is sent, too late to return a 429. Dependencies run before the response starts.

    `__call__` is a sync `def` on purpose: FastAPI runs sync dependencies in its
    threadpool, so the blocking Redis call doesn't stall the event loop.
    """

    def __init__(self, scope: str, capacity: int, refill_rate: float):
        if capacity < 1:
            raise ValueError("capacity must be at least 1")
        if refill_rate <= 0:
            raise ValueError("refill_rate must be positive")
        self.scope = scope
        self.capacity = capacity
        self.refill_rate = refill_rate

    def __call__(self, request: Request, response: Response) -> None:
        # behind a trusted proxy, ProxyHeadersMiddleware has already set this from X-Forwarded-For
        ip = request.client.host if request.client else "unknown"

        try:
            result = RedisCache().consume_token(
                f"ratelimit:{self.scope}:{ip}", self.capacity, self.refill_rate
            )
        except redis.RedisError:
            # fail closed: without Redis we can't enforce the limit
            logger.exception("rate limiter unavailable")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Rate limiter unavailable, try again later.",
            )

        if not result.allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests, slow down.",
                headers={
                    "Retry-After": str(max(1, math.ceil(result.retry_after))),
                    "X-RateLimit-Limit": str(self.capacity),
                    "X-RateLimit-Remaining": "0",
                },
            )

        response.headers["X-RateLimit-Limit"] = str(self.capacity)
        response.headers["X-RateLimit-Remaining"] = str(math.floor(result.remaining))
