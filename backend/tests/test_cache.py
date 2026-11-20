from functools import partial

import fakeredis
import pytest

from animal_finder import cache
from animal_finder.agents.feature_agent import SearchFilters
from animal_finder.cache import RedisCache


@pytest.fixture
def redis_cache(monkeypatch) -> RedisCache:
    server = fakeredis.FakeServer()
    monkeypatch.setattr(cache.redis, "Redis", partial(fakeredis.FakeRedis, server=server))
    return RedisCache()


def test_features_are_stored_under_prefixed_key(redis_cache):
    redis_cache.store_features("abc", SearchFilters().model_dump_json())

    assert redis_cache.client.exists("features:abc")
    assert not redis_cache.client.exists("abc")
    assert 0 < redis_cache.client.ttl("features:abc") <= 60 * 60


def test_retrieve_features_reads_prefixed_key(redis_cache):
    redis_cache.store_features("abc", SearchFilters().model_dump_json())

    assert redis_cache.retrieve_features("abc") == SearchFilters()
    assert redis_cache.retrieve_features("other") is None


def test_clear_session_features_deletes_prefixed_key(redis_cache):
    redis_cache.store_features("abc", SearchFilters().model_dump_json())
    redis_cache.client.set("abc", "unrelated")

    redis_cache.clear_session_features("abc")

    assert not redis_cache.client.exists("features:abc")
    assert redis_cache.client.exists("abc")
