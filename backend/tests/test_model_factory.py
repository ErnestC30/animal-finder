import asyncio
from types import SimpleNamespace
from typing import get_args
from unittest.mock import MagicMock

import httpx2
import pytest
from pydantic import SecretStr
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.google import GoogleModel

from animal_finder.agents import model_factory
from animal_finder.agents.model_factory import build_model
from animal_finder.config import AgentSettings, AnthropicModelName, GeminiModelName

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


def test_google_provider_receives_the_unwrapped_api_key_and_retrying_client(monkeypatch):
    model_name = get_args(GeminiModelName)[0]
    model_mock = MagicMock()
    provider_mock = MagicMock()
    monkeypatch.setattr(model_factory, "GoogleModel", model_mock)
    monkeypatch.setattr(model_factory, "GoogleProvider", provider_mock)

    result = build_model(make_settings(model_name))

    provider_mock.assert_called_once_with(
        api_key=API_KEY, http_client=model_factory.get_http_client()
    )
    model_mock.assert_called_once_with(model_name, provider=provider_mock.return_value)
    assert result is model_mock.return_value


def test_anthropic_client_uses_retrying_client_with_sdk_retries_disabled(monkeypatch):
    model_name = get_args(AnthropicModelName)[0]
    model_mock = MagicMock()
    provider_mock = MagicMock()
    client_mock = MagicMock()
    monkeypatch.setattr(model_factory, "AnthropicModel", model_mock)
    monkeypatch.setattr(model_factory, "AnthropicProvider", provider_mock)
    monkeypatch.setattr(model_factory, "AsyncAnthropic", client_mock)

    result = build_model(make_settings(model_name))

    client_mock.assert_called_once_with(
        api_key=API_KEY, http_client=model_factory.get_http_client(), max_retries=0
    )
    provider_mock.assert_called_once_with(anthropic_client=client_mock.return_value)
    model_mock.assert_called_once_with(model_name, provider=provider_mock.return_value)
    assert result is model_mock.return_value


def test_models_share_one_http_client():
    assert model_factory.get_http_client() is model_factory.get_http_client()


def _mock_transport(statuses):
    """Return responses with the given statuses in order and record how many requests were made."""
    calls = []

    def handler(request):
        calls.append(request)
        # Retry-After: 0 keeps the backoff instant in tests
        return httpx2.Response(statuses[len(calls) - 1], headers={"Retry-After": "0"})

    return httpx2.MockTransport(handler), calls


async def _post(client):
    async with client:
        return await client.post("https://model.example/generate", content=b"{}")


@pytest.mark.parametrize("status_code", sorted(model_factory.RETRYABLE_STATUS_CODES))
def test_retryable_status_is_retried_until_success(status_code):
    transport, calls = _mock_transport([status_code, status_code, 200])
    client = model_factory.build_retrying_http_client(wrapped=transport)

    response = asyncio.run(_post(client))

    assert response.status_code == 200
    assert len(calls) == 3


def test_exhausted_retries_raise_model_http_error():
    transport, calls = _mock_transport([503] * model_factory.MAX_ATTEMPTS)
    client = model_factory.build_retrying_http_client(wrapped=transport)

    async def post_to_gemini():
        async with client:
            return await client.post(
                "https://model.example/v1beta/models/gemini-test:generateContent",
                content=b"{}",
            )

    with pytest.raises(ModelHTTPError) as exc_info:
        asyncio.run(post_to_gemini())

    assert exc_info.value.status_code == 503
    assert exc_info.value.model_name == "gemini-test"
    assert exc_info.value.headers == {"retry-after": "0"}
    assert len(calls) == model_factory.MAX_ATTEMPTS


def test_retries_are_logged(caplog):
    transport, _ = _mock_transport([503, 200])
    client = model_factory.build_retrying_http_client(wrapped=transport)

    with caplog.at_level("WARNING", logger=model_factory.__name__):
        asyncio.run(_post(client))

    assert "model request failed (503)" in caplog.text
    assert "attempt 1/4" in caplog.text


@pytest.mark.parametrize("status_code", [400, 401, 404])
def test_non_retryable_status_is_returned_without_retry(status_code):
    transport, calls = _mock_transport([status_code])
    client = model_factory.build_retrying_http_client(wrapped=transport)

    response = asyncio.run(_post(client))

    assert response.status_code == status_code
    assert len(calls) == 1


def test_network_error_is_retried():
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            raise httpx2.ConnectError("connection refused", request=request)
        return httpx2.Response(200)

    client = model_factory.build_retrying_http_client(
        wrapped=httpx2.MockTransport(handler)
    )
    # no Retry-After on a network error, so skip the exponential backoff
    client._transport.config["wait"] = lambda state: 0

    response = asyncio.run(_post(client))

    assert response.status_code == 200
    assert len(calls) == 2


def test_unsupported_provider_raises_value_error():
    settings = SimpleNamespace(
        provider="openai",
        model="gpt-test",
        api_key=SecretStr(API_KEY),
    )

    with pytest.raises(ValueError, match="Unsupported provider: openai"):
        build_model(settings)
