from dataclasses import dataclass

import redis

from animal_finder.agents.feature_agent import SearchFilters


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    remaining: float
    retry_after: float


class RedisCache:
    FEATURES_PREFIX = "features:"

    def __init__(self, host="localhost", port=6379):
        self.client = redis.Redis(host=host, port=port)
        self._token_bucket = self.client.register_script(TOKEN_BUCKET_LUA)

    def _features_key(self, session_id: str) -> str:
        return f"{self.FEATURES_PREFIX}{session_id}"

    def clear_session_features(self, session_id: str):
        self.client.delete(self._features_key(session_id))

    def retrieve_features(self, session_id: str) -> SearchFilters | None:
        features = self.client.get(self._features_key(session_id))

        if features:
            return SearchFilters.model_validate_json(features)

    def store_features(self, session_id: str, serialized_features: str):
        self.client.set(
            self._features_key(session_id), serialized_features, ex=60 * 60
        )  # 60 min ttl

    def consume_token(
        self, key: str, capacity: int, refill_rate: float, cost: int = 1
    ) -> RateLimitResult:
        """
        Takes `cost` tokens from the bucket at `key` if it has enough.
        Raises redis.RedisError if Redis is unreachable.
        """
        allowed, remaining, retry_after = self._token_bucket(
            keys=[key], args=[capacity, refill_rate, cost]
        )
        return RateLimitResult(
            allowed=bool(allowed),
            remaining=float(remaining),
            retry_after=float(retry_after),
        )


# Token bucket, run atomically in Redis so concurrent requests can't both spend the
# same token. The bucket is a hash of `tokens` (float) and `ts` (last update, seconds).
# KEYS[1] = bucket key; ARGV = capacity, refill rate (tokens/sec), cost.
# Returns {allowed (0/1), remaining tokens, seconds until `cost` tokens are available}.
TOKEN_BUCKET_LUA = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local rate = tonumber(ARGV[2])
local cost = tonumber(ARGV[3])

-- use the Redis clock so every API worker agrees on the time
local t = redis.call('TIME')
local now = tonumber(t[1]) + tonumber(t[2]) / 1000000

local bucket = redis.call('HMGET', key, 'tokens', 'ts')
local tokens = tonumber(bucket[1]) or capacity
local ts = tonumber(bucket[2]) or now

tokens = math.min(capacity, tokens + math.max(0, now - ts) * rate)

local allowed = 0
local retry_after = 0
if tokens >= cost then
    tokens = tokens - cost
    allowed = 1
else
    retry_after = (cost - tokens) / rate
end

redis.call('HSET', key, 'tokens', tostring(tokens), 'ts', tostring(now))
-- an idle bucket refills completely in capacity/rate seconds, so it can be dropped after that
redis.call('EXPIRE', key, math.ceil(capacity / rate) * 2)

-- tostring: Redis truncates Lua numbers to integers in replies
return {allowed, tostring(tokens), tostring(retry_after)}
"""
