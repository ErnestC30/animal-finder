from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic_ai import Embedder


@dataclass
class ChatDeps:
    db: AsyncSession
    embedder: Embedder
    session_id: str | None
