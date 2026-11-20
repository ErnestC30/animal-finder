import time
from functools import partial

import fakeredis
import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.sse import EventSourceResponse, ServerSentEvent
from fastapi.testclient import TestClient

from animal_finder import cache
from animal_finder.cache import RedisCache
from animal_finder.rate_limit import RateLimit


@pytest.fixture
def server(monkeypatch) -> fakeredis.FakeServer:
    """Every RedisCache() talks to one in-memory server, as they would to one real Redis."""
    server = fakeredis.FakeServer()
    monkeypatch.setattr(cache.redis, "Redis", partial(fakeredis.FakeRedis, server=server))
    return server


class FakeClient:
    def __init__(self, host: str):
        self.host = host


class FakeRequest:
    def __init__(self, ip: str = "1.2.3.4"):
        self.client = FakeClient(ip)


class FakeResponse:
    def __init__(self):
        self.headers: dict[str, str] = {}


def call(limit: RateLimit, ip: str = "1.2.3.4") -> FakeResponse:
    response = FakeResponse()
    limit(FakeRequest(ip), response)
    return response


def test_consume_token_allows_up_to_capacity(server):
    redis_cache = RedisCache()
    results = [redis_cache.consume_token("bucket", capacity=3, refill_rate=0.5) for _ in range(4)]

    assert [r.allowed for r in results] == [True, True, True, False]
    assert results[2].remaining == pytest.approx(0, abs=0.01)
    # one token short at 0.5 tokens/sec -> about 2s to wait
    assert results[3].retry_after == pytest.approx(2, abs=0.05)


def test_consume_token_refills_over_time(server):
    redis_cache = RedisCache()
    assert redis_cache.consume_token("bucket", capacity=1, refill_rate=20).allowed
    assert not redis_cache.consume_token("bucket", capacity=1, refill_rate=20).allowed

    time.sleep(0.1)  # 20 tokens/sec -> a full token after 0.05s

    assert redis_cache.consume_token("bucket", capacity=1, refill_rate=20).allowed


def test_consume_token_sets_expiry(server):
    redis_cache = RedisCache()
    redis_cache.consume_token("bucket", capacity=10, refill_rate=0.2)
    # idle buckets expire after twice the full-refill time (10 / 0.2 = 50s)
    assert redis_cache.client.ttl("bucket") == 100


def test_rate_limit_sets_headers_then_rejects(server):
    limit = RateLimit("test", capacity=2, refill_rate=0.1)

    assert call(limit).headers == {"X-RateLimit-Limit": "2", "X-RateLimit-Remaining": "1"}
    assert call(limit).headers["X-RateLimit-Remaining"] == "0"

    with pytest.raises(HTTPException) as exc:
        call(limit)
    assert exc.value.status_code == 429
    assert exc.value.headers["Retry-After"] == "10"  # 1 token at 0.1/sec
    assert exc.value.headers["X-RateLimit-Remaining"] == "0"


def test_rate_limit_buckets_are_per_ip(server):
    limit = RateLimit("test", capacity=1, refill_rate=0.1)
    call(limit, ip="1.1.1.1")

    with pytest.raises(HTTPException):
        call(limit, ip="1.1.1.1")
    call(limit, ip="2.2.2.2")  # a different IP still has its own token


def test_rate_limit_buckets_are_per_scope(server):
    chat = RateLimit("chat", capacity=1, refill_rate=0.1)
    search = RateLimit("search", capacity=1, refill_rate=0.1)
    call(chat)

    with pytest.raises(HTTPException):
        call(chat)
    call(search)  # same IP, different endpoint: separate bucket


def test_rate_limit_fails_closed_when_redis_is_down(server):
    server.connected = False
    with pytest.raises(HTTPException) as exc:
        call(RateLimit("test", capacity=5, refill_rate=1))
    assert exc.value.status_code == 503


def test_rate_limit_rejects_streaming_endpoint_before_stream_starts(server):
    """The 429 must arrive as a plain HTTP error, not inside a 200 SSE stream."""
    app = FastAPI()

    @app.post(
        "/stream",
        response_class=EventSourceResponse,
        dependencies=[Depends(RateLimit("stream", capacity=2, refill_rate=0.1))],
    )
    async def stream():
        yield ServerSentEvent(data="hi")
        yield ServerSentEvent(event="done", data="")

    client = TestClient(app)
    for _ in range(2):
        ok = client.post("/stream")
        assert ok.status_code == 200
        assert "X-RateLimit-Remaining" in ok.headers
        assert "event: done" in ok.text

    limited = client.post("/stream")
    assert limited.status_code == 429
    assert limited.headers["Retry-After"] == "10"
    assert limited.json() == {"detail": "Too many requests, slow down."}


def test_rate_limit_rejects_invalid_config():
    with pytest.raises(ValueError):
        RateLimit("test", capacity=0, refill_rate=1)
    with pytest.raises(ValueError):
        RateLimit("test", capacity=1, refill_rate=0)
