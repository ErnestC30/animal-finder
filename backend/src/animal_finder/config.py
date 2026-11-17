from functools import lru_cache
from pathlib import Path
from typing import Literal, get_args

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]

GeminiModelName = Literal["gemini-3.5-flash-lite", "gemini-3.1-flash-lite"]
AnthropicModelName = Literal["claude-opus-5-5", "claude-sonnet-5-5"]
AgentModelName = GeminiModelName | AnthropicModelName
AgentProvider = Literal["google", "anthropic"]


class DbSettings(BaseSettings):
    db_host: str
    db_user: str
    db_password: SecretStr
    db_name: str

    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")


class AppSettings(BaseSettings):

    cookie_key: str = "session_id"
    cookie_httponly: bool = True
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    cookie_secure: bool = True

    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")


class AgentSettings(BaseSettings):
    """Model and API key for an agent. The provider is derived from the model name."""

    model: AgentModelName
    api_key: SecretStr

    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", extra="ignore")

    @property
    def provider(self) -> AgentProvider:
        if self.model in get_args(AnthropicModelName):
            return "anthropic"
        return "google"


class ChatAgentSettings(AgentSettings):
    """Reads CHAT_AGENT_MODEL and CHAT_AGENT_API_KEY."""

    model: AgentModelName = "gemini-3.5-flash-lite"

    model_config = SettingsConfigDict(env_prefix="CHAT_AGENT_")


class FeatureAgentSettings(AgentSettings):
    """Reads FEATURE_AGENT_MODEL and FEATURE_AGENT_API_KEY."""

    model: AgentModelName = "gemini-3.1-flash-lite"

    model_config = SettingsConfigDict(env_prefix="FEATURE_AGENT_")


class RerankAgentSettings(AgentSettings):
    """Reads RERANK_AGENT_MODEL and RERANK_AGENT_API_KEY."""

    model: AgentModelName = "gemini-3.1-flash-lite"

    model_config = SettingsConfigDict(env_prefix="RERANK_AGENT_")


@lru_cache
def get_app_settings() -> AppSettings:
    return AppSettings()


@lru_cache
def get_chat_agent_settings() -> ChatAgentSettings:
    return ChatAgentSettings()


@lru_cache
def get_feature_agent_settings() -> FeatureAgentSettings:
    return FeatureAgentSettings()


@lru_cache
def get_rerank_agent_settings() -> RerankAgentSettings:
    return RerankAgentSettings()
