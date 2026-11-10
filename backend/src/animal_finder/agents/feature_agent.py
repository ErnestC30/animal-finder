from pydantic import BaseModel, Field
from pydantic_ai import Agent

from animal_finder.config import AgentSettings, get_feature_agent_settings
from animal_finder.agents.model_factory import build_model


class SearchFilters(BaseModel):
    include: dict[str, list[str]] = Field(default_factory=dict)
    exclude: dict[str, list[str]] = Field(default_factory=dict)


class FeaturesOutput(BaseModel):
    search_filters: SearchFilters
    query: str


def initialize_features_agent(settings: AgentSettings | None = None):
    settings = settings or get_feature_agent_settings()
    model = build_model(settings)
    instructions = """
    You are an agent responsible for collecting important attributes used to find an animal.
    Some of these attributes include:
    1. physical characteristics (size, shape, coats, limbs, tails, eyes)
    2. habitat and geographic locations
    3. food and diet
    4. how they move
    5. ecological role
    6. reproduction

    Allow these attributes to be separated in a way that some features can be 'included' or 'excluded' from the following embedding search.
    Return the collected attributes and rewrite these attributes into a string that displays these attributes so that they can be used for an embedding search. 
    For the excluded features, avoid negation words (like cannot, not) from being used in the query.
    If additional features are provided from previous messages, use these features as well.
    """
    agent = Agent(model, instructions=instructions, output_type=FeaturesOutput)

    return agent
