from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Text
from pgvector.sqlalchemy import Vector

EMBEDDING_VECTORS = 3072  # default gemini embedder value


class Base(DeclarativeBase):
    pass


class Animal(Base):
    __tablename__ = "animals"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text)
    vector = mapped_column(Vector(EMBEDDING_VECTORS))
