from sqlalchemy.ext.asyncio import AsyncSession
from pydantic_ai import Embedder, RunContext
from sqlalchemy import Text, select
from pydantic import BaseModel, Field
import uuid

from agents.feature_agent import (
    initialize_features_agent,
    FeaturesOutput,
    SearchFilters,
)
from cache import RedisCache
from models import Animal
from agents.dependencies import ChatDeps

"""
might want to seperate tools into their own files
"""


class AnimalData(BaseModel):
    id: int
    name: str
    text: str
    distance: float

    def __repr__(self) -> str:
        truncated_text = self.text[:40] + "..." if len(self.text) > 40 else self.text

        return (
            f"AnimalData(id={self.id!r}, "
            f"name={self.name!r}, "
            f"text={truncated_text!r}, "
            f"distance={self.distance!r})"
        )


async def retrieve_relevant_animals(
    ctx: RunContext[ChatDeps],
    query: str,
) -> list[AnimalData]:
    """
    Retrieve animals from the database using a formatted semantic-search query.
    """
    # Should add a filter for results > threshold value to be removed
    # Lower distance - more closely related

    embedding_result = await ctx.deps.embedder.embed_query(query)
    embedded_query = embedding_result.embeddings[0]

    # cosine distance: Animal.vector.cosine_distance()
    # dot product: Animal.vector.max_inner_product()

    q = (
        select(
            Animal.id,
            Animal.name,
            Animal.text,
            Animal.vector.cosine_distance(embedded_query).label("distance"),
        )
        .order_by("distance")
        .limit(10)
    )

    result = await ctx.deps.db.execute(q)
    animals = result.all()

    # data = [RelevantAnimals(animal.id, animal.name, animal.text, animal.distance) for animal in animals]

    return [
        AnimalData(
            id=animal.id, name=animal.name, text=animal.text, distance=animal.distance
        )
        for animal in animals
    ]


async def extract_features(ctx: RunContext[ChatDeps], query: str) -> FeaturesOutput:
    """
    Extract important animal features from a given prompt into a structured format and returns a
    formatted query that can be used for document retrieval.
    """

    cache = RedisCache()
    features = cache.retrieve_features(ctx.deps.session_id)

    if features:
        query += f"""
            \n The previous included features are: {features}
        """
        print("including additional features", features)

    print(query)
    agent = initialize_features_agent()
    result = await agent.run(query)
    output = result.output

    cache.store_features(ctx.deps.session_id, output.search_filters.model_dump_json())

    return output


async def search_new_animal(ctx: RunContext[ChatDeps]) -> None:
    """Remove existing context to start a search for a new animal query."""
    cache = RedisCache()
    cache.clear_session(ctx.deps.session_id)
