import asyncio
import os
from dotenv import load_dotenv

from pydantic import BaseModel
from pydantic_ai import Agent, Embedder
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.exceptions import UnexpectedModelBehavior
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from animal_finder.models import Animal
from animal_finder.database import db_url

load_dotenv()


class AnimalSearchData(BaseModel):
    name: str
    text: str


def initialize_search_agent():
    api_key = os.environ.get("FEATURE_AGENT_API_KEY")
    provider = GoogleProvider(api_key=api_key)
    model = GoogleModel(
        "gemini-3.5-flash-lite",
        provider=provider,
    )
    instructions = """
    Write 6-8 paragraphs focusing on the particular animal species while focusing on following details:

    Animal: {animal_name}

    Physical characteristics like size, shape, coats, limbs, tails, ears, eyes where applicable.
    Include the taxonomy and closeness to other related species.
    Habitat and geographic locations (continent, climate, biome)
    Food and diet
    How they move
    Ecological role
    Reproduction
    Unique traits of animals if applicable

    Return the name of the animal (capitalized and in singular term) and the relevant details as plain text
    """
    agent = Agent(model, instructions=instructions, output_type=AnimalSearchData)
    return agent


async def insert_into_db(
    db: AsyncSession,
    embedder: Embedder,
    name: str,
    text: str,
):
    """Stage an Animal row on the session. The caller owns the transaction."""
    embedding_result = await embedder.embed_documents(text)
    embedded_document = embedding_result.embeddings[0]

    animal_instance = Animal(name=name, text=text, vector=embedded_document)
    db.add(animal_instance)


async def main():
    embedder = Embedder("google:gemini-embedding-2")
    engine = create_async_engine(db_url)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    # Research on animal characteristics and store into database
    animals = ["yak", "bison", "water buffalo", "antelope"]
    agent = initialize_search_agent()

    try:
        for animal in animals:
            try:
                result = await agent.run(f"Give me details on {animal}")
                # One transaction per animal: commits on success, rolls back on
                # error, so a failed insert can't break the remaining ones.
                async with Session.begin() as db:
                    await insert_into_db(
                        db, embedder, result.output.name, result.output.text
                    )
            except UnexpectedModelBehavior as e:
                print(f"{animal}: model error: {e}")
            except SQLAlchemyError as e:
                print(f"{animal}: database error: {e}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
