from typing import Literal

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from animal_finder.config import AgentSettings, get_feature_agent_settings
from animal_finder.agents.model_factory import build_model

FeatureCategory = Literal[
    "physical_characteristics",
    "taxonomy",
    "habitat",
    "diet",
    "movement",
    "behavior",
    "ecological_role",
    "reproduction",
]


class FeatureGroup(BaseModel):
    category: FeatureCategory
    values: list[str]


class SearchFilters(BaseModel):
    include: list[FeatureGroup] = Field(default_factory=list)
    exclude: list[FeatureGroup] = Field(default_factory=list)


class FeaturesOutput(BaseModel):
    search_filters: SearchFilters
    query: str


def initialize_features_agent(settings: AgentSettings | None = None):
    settings = settings or get_feature_agent_settings()
    model = build_model(settings)
    instructions = """
    You are an agent responsible for collecting important attributes used to find an animal.
    Extract features into these categories:
    1. physical characteristics: size, shape, coats, limbs, tails, eyes, teeth
    2. taxonomy
    3. habitat and geographic locations: continent, country, climate, biome
    4. food and diet
    5. how they move: walking, hopping, climbing, swimming, flying
    6. behavior
    5. ecological role
    6. reproduction

    ## Include vs exclude
    - Features the animal has go in include. Uncertain features ("maybe", "I think") still go in include.
    - Features the user says the animal does NOT have go in exclude, written positively:
    "it doesn't have stripes" -> exclude physical_characteristics: ["stripes"].

    ## Query
    - Build the query from the included features only. Do not mention excluded features in any form:
    the embedding search cannot understand negation, so mentioning them pulls results toward them.
    - Write a short descriptive paragraph in the style of an encyclopedia entry, ordered by category.
    - Do not name a specific animal unless the user named it.

    ## Example for the search filter
    User: "A small grey animal from Australia that hops and sleeps during the day. It doesn't have a long tail."
    include:
    physical_characteristics: ["small size", "grey fur"]
    habitat: ["Australia"]
    movement: ["hops"]
    behavior: ["nocturnal"]
    exclude:
    physical_characteristics: ["long tail"]
    """
    # The generated query should NOT explicitly mention animal names unless mentioned in the user's query.
    agent = Agent(model, instructions=instructions, output_type=FeaturesOutput)

    return agent
