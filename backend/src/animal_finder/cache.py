import redis

from animal_finder.agents.feature_agent import SearchFilters


class RedisCache:
    def __init__(self, host="localhost", port=6379):
        self.client = redis.Redis(host=host, port=port)

    def clear_session(self, session_id: str):
        self.client.delete(session_id)

    def retrieve_features(self, session_id: str) -> SearchFilters | None:
        features = self.client.get(session_id)

        if features:
            return SearchFilters.model_validate_json(features)

    def store_features(self, session_id: str, serialized_features: str):
        self.client.set(session_id, serialized_features, ex=60 * 60)  # 60 min ttl
