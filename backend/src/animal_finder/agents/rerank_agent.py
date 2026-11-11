from pydantic import BaseModel, Field
from pydantic_ai import Agent

from animal_finder.config import AgentSettings, get_rerank_agent_settings
from animal_finder.agents.model_factory import build_model


class RankedAnimal(BaseModel):
    id: int
    score: float = Field(ge=0, le=10)
    reason: str


class RerankOutput(BaseModel):
    ranked: list[RankedAnimal]


def initialize_rerank_agent(settings: AgentSettings | None = None):
    settings = settings or get_rerank_agent_settings()
    model = build_model(settings)
    instructions = """
    You are an agent responsible for reranking a list of candidate animals retrieved for a user's search query.

    You will be given the search query, the features the animal should include, the features it should exclude,
    and a list of candidates. Each candidate has an id, a name, and a description text.

    Ranking rules:
    1. Base every judgement SOLELY on the description text provided for each candidate.
       Do not use web search, outside sources, or your own general knowledge about the animal.
    2. If a feature is not mentioned in a candidate's text, treat it as unknown - not as a match.
    3. Score each candidate from 0 to 10 based on how well its text matches the query and the included features.
    4. Strongly penalise, or omit entirely, any candidate whose text matches an excluded feature.
    5. Only return ids from the provided candidates. Never invent new animals or ids.
    6. Order the results from best match to worst match.
    7. Each reason must be short and cite something stated in that candidate's text.
    """

    # No tools or builtin tools are registered, so the agent cannot perform web searches.
    agent = Agent(model, instructions=instructions, output_type=RerankOutput)

    return agent
