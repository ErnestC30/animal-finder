import pytest
from pydantic_ai import ModelResponse, ToolCallPart
from pydantic_ai.messages import ModelMessage, UserPromptPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from animal_finder import tools
from animal_finder.agents.feature_agent import SearchFilters
from animal_finder.agents.rerank_agent import initialize_rerank_agent
from animal_finder.config import AgentSettings, RerankAgentSettings
from animal_finder.tools import (
    CANDIDATE_POOL,
    RERANK_TOP_K,
    AnimalData,
    rerank_animals,
)

pytestmark = pytest.mark.anyio

QUERY = "a large striped cat"
FILTERS = SearchFilters(
    include=[{"category": "physical_characteristics", "values": ["striped"]}],
    exclude=[{"category": "habitat", "values": ["Asia"]}],
)


def make_candidates(count: int = CANDIDATE_POOL) -> list[AnimalData]:
    return [
        AnimalData(id=i, name=f"Animal {i}", text=f"Text for animal {i}", distance=i / 100)
        for i in range(1, count + 1)
    ]


def make_agent():
    """Build the real rerank agent; its model is overridden in each test, so no API calls are made."""
    settings = AgentSettings(model="gemini-3.1-flash-lite", api_key="test", _env_file=None)
    return initialize_rerank_agent(settings)


def ranked(*ids: int) -> list[dict]:
    return [{"id": i, "score": 10 - n * 0.5, "reason": f"reason {i}"} for n, i in enumerate(ids)]


def responding_with(ranked_items: list[dict], captured: dict | None = None):
    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        if captured is not None:
            captured["messages"] = messages
            captured["info"] = info
        return ModelResponse(
            parts=[ToolCallPart(info.output_tools[0].name, {"ranked": ranked_items})]
        )

    return FunctionModel(respond)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def agent(monkeypatch):
    agent = make_agent()
    monkeypatch.setattr(tools, "initialize_rerank_agent", lambda: agent)
    return agent


async def test_reorders_candidates_by_llm_output(agent):
    candidates = make_candidates()

    with agent.override(model=responding_with(ranked(5, 2, 9))):
        result = await rerank_animals(QUERY, FILTERS, candidates)

    assert [a.id for a in result] == [5, 2, 9]
    assert result[0].rerank_score == 10
    assert result[0].rerank_reason == "reason 5"
    # Original candidate data is preserved
    assert result[0].text == "Text for animal 5"
    assert result[0].distance == 0.05


async def test_ignores_unknown_and_duplicate_ids(agent):
    with agent.override(model=responding_with(ranked(3, 999, 3, 1))):
        result = await rerank_animals(QUERY, FILTERS, make_candidates())

    assert [a.id for a in result] == [3, 1]


async def test_caps_results_at_top_k_from_candidate_pool(agent):
    candidates = make_candidates()
    assert len(candidates) == 12

    with agent.override(model=responding_with(ranked(*reversed(range(1, 13))))):
        result = await rerank_animals(QUERY, FILTERS, candidates)

    assert RERANK_TOP_K == 6
    assert [a.id for a in result] == [12, 11, 10, 9, 8, 7]


async def test_rerank_agent_has_no_tools(agent):
    captured: dict = {}

    with agent.override(model=responding_with(ranked(1), captured)):
        await rerank_animals(QUERY, FILTERS, make_candidates())

    info: AgentInfo = captured["info"]
    assert info.function_tools == []
    assert info.model_request_parameters.native_tools == []


async def test_prompt_contains_full_candidate_text_and_filters(agent):
    long_text = "Striped coat and long tail. " * 40  # well over 500 characters
    candidates = make_candidates()
    candidates[0] = candidates[0].model_copy(update={"text": long_text})
    captured: dict = {}

    with agent.override(model=responding_with(ranked(1), captured)):
        await rerank_animals(QUERY, FILTERS, candidates)

    prompt = "".join(
        part.content
        for message in captured["messages"]
        for part in getattr(message, "parts", [])
        if isinstance(part, UserPromptPart)
    )
    assert long_text in prompt
    assert QUERY in prompt
    assert "striped" in prompt
    assert "Asia" in prompt
    for candidate in candidates:
        assert f"id: {candidate.id}" in prompt


async def test_falls_back_to_distance_order_when_agent_raises(agent):
    def fail(messages, info):
        raise RuntimeError("model unavailable")

    candidates = make_candidates()

    with agent.override(model=FunctionModel(fail)):
        result = await rerank_animals(QUERY, FILTERS, candidates)

    assert result == candidates[:RERANK_TOP_K]


@pytest.mark.parametrize("ranked_items", [[], ranked(100, 200)])
async def test_falls_back_to_distance_order_when_no_valid_ids(agent, ranked_items):
    candidates = make_candidates()

    with agent.override(model=responding_with(ranked_items)):
        result = await rerank_animals(QUERY, FILTERS, candidates)

    assert result == candidates[:RERANK_TOP_K]


async def test_empty_candidates_skip_reranking(monkeypatch):
    def should_not_be_called():
        raise AssertionError("rerank agent should not be built for empty candidates")

    monkeypatch.setattr(tools, "initialize_rerank_agent", should_not_be_called)

    assert await rerank_animals(QUERY, FILTERS, []) == []


def test_rerank_settings_read_prefixed_env_vars(monkeypatch):
    monkeypatch.setenv("RERANK_AGENT_MODEL", "claude-sonnet-5-5")
    monkeypatch.setenv("RERANK_AGENT_API_KEY", "rerank-key")

    settings = RerankAgentSettings(_env_file=None)

    assert settings.model == "claude-sonnet-5-5"
    assert settings.api_key.get_secret_value() == "rerank-key"
    assert settings.provider == "anthropic"
