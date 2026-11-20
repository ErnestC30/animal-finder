import logging
from pydantic_ai import RunContext
from sqlalchemy import select
from pydantic import BaseModel


from animal_finder.agents.feature_agent import (
    initialize_features_agent,
    FeaturesOutput,
    SearchFilters,
)
from animal_finder.agents.rerank_agent import initialize_rerank_agent
from animal_finder.cache import RedisCache
from animal_finder.models import Animal
from animal_finder.agents.dependencies import ChatDeps

"""
might want to seperate tools into their own files
"""

logger = logging.getLogger(__name__)

# Number of candidates pulled from the vector search and passed to the reranker
CANDIDATE_POOL = 12
# Number of animals returned after reranking (best match + 5 related)
RERANK_TOP_K = 6


class AnimalData(BaseModel):
    id: int
    name: str
    text: str
    distance: float
    rerank_score: float | None = None
    rerank_reason: str | None = None

    def __repr__(self) -> str:
        truncated_text = self.text[:40] + "..." if len(self.text) > 40 else self.text

        return (
            f"AnimalData(id={self.id!r}, "
            f"name={self.name!r}, "
            f"text={truncated_text!r}, "
            f"distance={self.distance!r}, "
            f"rerank_score={self.rerank_score!r}, "
            f"rerank_reason={self.rerank_reason!r})"
        )


def build_rerank_prompt(
    query: str, filters: SearchFilters | None, candidates: list[AnimalData]
) -> str:
    """Build the reranker prompt. Candidate text is passed in full, without truncation."""
    filters = filters or SearchFilters()
    candidate_lines = "\n\n".join(
        f"id: {animal.id} | name: {animal.name} | text: {animal.text}"
        for animal in candidates
    )

    return (
        f"Search query: {query}\n\n"
        f"Included features: {filters.include}\n"
        f"Excluded features: {filters.exclude}\n\n"
        f"Candidates:\n{candidate_lines}"
    )


async def rerank_animals(
    query: str, filters: SearchFilters | None, candidates: list[AnimalData]
) -> list[AnimalData]:
    """
    Rerank retrieved candidates with the rerank agent and return the top RERANK_TOP_K.
    Falls back to the original distance ordering if reranking fails or returns no valid ids.
    """
    if not candidates:
        return []
    fallback = candidates[:RERANK_TOP_K]

    try:
        agent = initialize_rerank_agent()
        result = await agent.run(build_rerank_prompt(query, filters, candidates))
    except Exception:
        logger.exception("reranking failed, falling back to distance ordering")
        return fallback

    by_id = {animal.id: animal for animal in candidates}
    reranked: list[AnimalData] = []
    seen: set[int] = set()

    for ranked in result.output.ranked:
        # Drop ids that were not retrieved and duplicate ids
        if ranked.id not in by_id or ranked.id in seen:
            continue
        seen.add(ranked.id)
        reranked.append(
            by_id[ranked.id].model_copy(
                update={"rerank_score": ranked.score, "rerank_reason": ranked.reason}
            )
        )

    if not reranked:
        logger.info(
            "reranking returned no valid ids, falling back to distance ordering"
        )
        return fallback

    reranked.sort(key=lambda x: x.rerank_score, reverse=True)
    return reranked[:RERANK_TOP_K]


def load_session_filters(session_id: str | None) -> SearchFilters | None:
    if not session_id:
        return None

    try:
        return RedisCache().retrieve_features(session_id)
    except Exception:
        logger.exception("unable to load search filters for reranking")
        return None


async def retrieve_relevant_animals(
    ctx: RunContext[ChatDeps],
    query: str,
) -> list[AnimalData]:
    """
    Retrieve animals from the database using a formatted semantic-search query.
    Results are reranked and returned in order, with the best match first.
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
        .limit(CANDIDATE_POOL)
    )

    result = await ctx.deps.db.execute(q)
    animals = result.all()

    candidates = [
        AnimalData(
            id=animal.id, name=animal.name, text=animal.text, distance=animal.distance
        )
        for animal in animals
    ]

    filters = load_session_filters(ctx.deps.session_id)

    return await rerank_animals(query, filters, candidates)


async def extract_features(ctx: RunContext[ChatDeps], query: str) -> FeaturesOutput:
    """
    Extract important animal features from a given prompt into a structured format and returns a
    formatted query that can be used for document retrieval.
    """

    cache = RedisCache()
    agent = initialize_features_agent()

    @agent.instructions
    def current_search_features() -> str:
        features = cache.retrieve_features(ctx.deps.session_id)
        if not features:
            return "There are no previous features to extract from. Start a new feature extraction."

        return (
            "These are the current features in the current session that the user is already searching for: \n"
            f"include: {features.include} \n"
            f"exclude: {features.exclude} \n"
            "Add new features from the current query to these existing features, and prioritize the current query"
            "if new features from the current query contradict the existing features."
        )

    result = await agent.run(query)
    output = result.output

    cache.store_features(ctx.deps.session_id, output.search_filters.model_dump_json())

    return output


async def search_new_animal(ctx: RunContext[ChatDeps], reason: str) -> None:
    """DESTRUCTIVE: permanently discards all features gathered so far in this session.
    Remove existing context in order to start a search for a new animal.
    `reason`: quote the user's words that signal a new search.
    """
    cache = RedisCache()
    cache.clear_session_features(ctx.deps.session_id)
