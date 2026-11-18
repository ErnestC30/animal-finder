from pydantic_ai import Embedder


def get_embedder():
    embedder = Embedder("google:gemini-embedding-2")
    return embedder
