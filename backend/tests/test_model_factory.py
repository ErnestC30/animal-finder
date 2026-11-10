from types import SimpleNamespace
from typing import get_args
from unittest.mock import MagicMock

import pytest
from pydantic import SecretStr
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.google import GoogleModel

from agents import model_factory
from agents.model_factory import build_model
from config import AgentSettings, AnthropicModelName, GeminiModelName

API_KEY = "test-api-key"


def make_settings(model: str) -> AgentSettings:
    """Build settings from explicit values so a local .env cannot affect the tests."""
    return AgentSettings(model=model, api_key=API_KEY, _env_file=None)


@pytest.mark.parametrize("model_name", get_args(GeminiModelName))
def test_gemini_model_names_build_a_google_model(model_name):
    model = build_model(make_settings(model_name))

    assert isinstance(model, GoogleModel)
    assert model.model_name == model_name


@pytest.mark.parametrize("model_name", get_args(AnthropicModelName))
def test_anthropic_model_names_build_an_anthropic_model(model_name):
    model = build_model(make_settings(model_name))

    assert isinstance(model, AnthropicModel)
    assert model.model_name == model_name


@pytest.mark.parametrize(
    ("model_name", "model_class", "provider_class"),
    [
        (get_args(GeminiModelName)[0], "GoogleModel", "GoogleProvider"),
        (get_args(AnthropicModelName)[0], "AnthropicModel", "AnthropicProvider"),
    ],
)
def test_provider_receives_the_unwrapped_api_key(
    monkeypatch, model_name, model_class, provider_class
):
    model_mock = MagicMock()
    provider_mock = MagicMock()
    monkeypatch.setattr(model_factory, model_class, model_mock)
    monkeypatch.setattr(model_factory, provider_class, provider_mock)

    result = build_model(make_settings(model_name))

    provider_mock.assert_called_once_with(api_key=API_KEY)
    model_mock.assert_called_once_with(model_name, provider=provider_mock.return_value)
    assert result is model_mock.return_value


def test_unsupported_provider_raises_value_error():
    settings = SimpleNamespace(
        provider="openai",
        model="gpt-test",
        api_key=SecretStr(API_KEY),
    )

    with pytest.raises(ValueError, match="Unsupported provider: openai"):
        build_model(settings)
