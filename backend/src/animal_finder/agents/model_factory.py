import logging
from functools import cache

import httpx2
from anthropic import AsyncAnthropic
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.models import Model
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.retries import (
    AsyncHTTPX2TenacityTransport,
    RetryConfig,
    wait_retry_after,
)
from tenacity import (
    RetryCallState,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from animal_finder.config import AgentSettings

RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
MAX_ATTEMPTS = 4
MAX_WAIT_SECONDS = 30
REQUEST_TIMEOUT_SECONDS = 60

logger = logging.getLogger(__name__)


def _is_retryable(exc: BaseException) -> bool:
    """Retry on retryable status codes and on transient network failures."""
    if isinstance(exc, httpx2.HTTPStatusError):
        return exc.response.status_code in RETRYABLE_STATUS_CODES
    return isinstance(exc, (httpx2.TimeoutException, httpx2.NetworkError))


def _raise_if_retryable(response: httpx2.Response) -> None:
    """Turn only retryable statuses into exceptions; other 4xx pass through to the SDK unchanged."""
    if response.status_code in RETRYABLE_STATUS_CODES:
        response.raise_for_status()


def _log_retry(state: RetryCallState) -> None:
    """Log each retry so repeated provider failures are visible in logfire."""
    exc = state.outcome.exception() if state.outcome else None
    reason = (
        exc.response.status_code
        if isinstance(exc, httpx2.HTTPStatusError)
        else type(exc).__name__
    )
    wait = state.next_action.sleep if state.next_action else 0
    logger.warning(
        "model request failed (%s), retrying in %.1fs (attempt %d/%d)",
        reason,
        wait,
        state.attempt_number,
        MAX_ATTEMPTS,
    )


def _model_name_from_url(url: httpx2.URL) -> str:
    """Best-effort model name for error messages, e.g. `.../models/gemini-x:generateContent`."""
    last_segment = url.path.rsplit("/", 1)[-1]
    return last_segment.split(":", 1)[0] or url.host


class ModelRetryTransport(AsyncHTTPX2TenacityTransport):
    """Retrying transport that reports exhausted retries as pydantic-ai's `ModelHTTPError`.

    Raising `httpx2.HTTPStatusError` out of the transport bypasses the provider SDK's own error
    handling, so without this the app would see raw httpx errors instead of `ModelHTTPError`.
    """

    async def handle_async_request(self, request: httpx2.Request) -> httpx2.Response:
        try:
            return await super().handle_async_request(request)
        except httpx2.HTTPStatusError as exc:
            response = exc.response
            raise ModelHTTPError(
                status_code=response.status_code,
                model_name=_model_name_from_url(request.url),
                headers=response.headers,
            ) from exc


def build_retrying_http_client(
    wrapped: httpx2.AsyncBaseTransport | None = None,
) -> httpx2.AsyncClient:
    """Create an httpx2 client that retries transient model provider failures with backoff.

    Honours the provider's Retry-After header when present, otherwise uses exponential backoff.
    `wrapped` is the underlying transport (defaults to a real network transport; tests pass a mock).
    """
    transport = ModelRetryTransport(
        config=RetryConfig(
            retry=retry_if_exception(_is_retryable),
            wait=wait_retry_after(
                fallback_strategy=wait_exponential(multiplier=1, max=10),
                max_wait=MAX_WAIT_SECONDS,
            ),
            stop=stop_after_attempt(MAX_ATTEMPTS),
            reraise=True,
            before_sleep=_log_retry,
        ),
        wrapped=wrapped,
        validate_response=_raise_if_retryable,
    )
    return httpx2.AsyncClient(transport=transport, timeout=REQUEST_TIMEOUT_SECONDS)


@cache
def get_http_client() -> httpx2.AsyncClient:
    """Shared retrying client, so agents built per request reuse one connection pool."""
    return build_retrying_http_client()


def build_model(settings: AgentSettings) -> Model:
    """Create the pydantic-ai model for the configured model name and API key."""
    api_key = settings.api_key.get_secret_value()
    http_client = get_http_client()

    match settings.provider:
        case "anthropic":
            # The Anthropic SDK retries by default; disable it so retries only happen in the transport.
            client = AsyncAnthropic(
                api_key=api_key, http_client=http_client, max_retries=0
            )
            return AnthropicModel(
                settings.model, provider=AnthropicProvider(anthropic_client=client)
            )
        case "google":
            return GoogleModel(
                settings.model,
                provider=GoogleProvider(api_key=api_key, http_client=http_client),
            )
        case _:
            raise ValueError(f"Unsupported provider: {settings.provider}")
