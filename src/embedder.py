from pydantic_ai import Embedder


def get_embedder():
    embedder = Embedder("google:gemini-embedding-2")
    return embedder


async def embed(query: str) -> list[float]:
    embedder = Embedder("google:gemini-embedding-2")
    result = await embedder.embed_query(query)
    embedded_query = result.embeddings[0]
    return embedded_query
