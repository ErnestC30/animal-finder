from pydantic_ai.models import Model
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.providers.google import GoogleProvider

from animal_finder.config import AgentSettings


def build_model(settings: AgentSettings) -> Model:
    """Create the pydantic-ai model for the configured model name and API key."""
    api_key = settings.api_key.get_secret_value()

    match settings.provider:
        case "anthropic":
            return AnthropicModel(
                settings.model, provider=AnthropicProvider(api_key=api_key)
            )
        case "google":
            return GoogleModel(settings.model, provider=GoogleProvider(api_key=api_key))
        case _:
            raise ValueError(f"Unsupported provider: {settings.provider}")
