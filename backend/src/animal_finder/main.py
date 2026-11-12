import sqlite3
import asyncio
import os
import uuid

import logging
import logfire
from contextlib import asynccontextmanager
from collections.abc import AsyncIterable
from dotenv import load_dotenv
from pydantic import BaseModel
from pydantic_ai import Agent, Embedder, RunContext, ModelRetry
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider
from pydantic_ai.exceptions import UnexpectedModelBehavior
from dataclasses import dataclass
from fastapi import FastAPI, Depends, Cookie, status
from fastapi.responses import JSONResponse
from fastapi.sse import EventSourceResponse, ServerSentEvent
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session
from sqlalchemy import Text, select, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from pgvector.sqlalchemy import Vector
from typing import Annotated

from animal_finder.database import sessionmanager, get_db

from animal_finder.agents.chat_agent import initialize_chat_agent, ChatDeps
from animal_finder.agents.feature_agent import initialize_features_agent
from animal_finder.embedder import get_embedder
from animal_finder.models import Animal

"""
USEFUL LINKS:
https://fastapi.tiangolo.com/tutorial/server-sent-events/#sse-with-post
- fastapi implementation of POST request -> SSE response
https://developer.mozilla.org/en-US/docs/Web/API/EventSource 
- how to consume SSE response in frontend
https://pydantic.dev/docs/ai/core-concepts/output/#streamed-results
"""

load_dotenv()


logfire.configure()
logfire.instrument_httpx()
logfire.instrument_pydantic_ai()
logging.basicConfig(handlers=[logfire.LogfireLoggingHandler()], level=logging.INFO)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # before application starts
    logger.info("performing startup process...")
    sessionmanager.init()
    yield
    # after application ends
    await sessionmanager.close()


app = FastAPI(lifespan=lifespan)
logfire.instrument_fastapi(app)


# not needed in main application -> used for loading data into db
def initialize_search_agent():
    load_dotenv()
    api_key = os.environ.get("GEMINI_API_KEY")
    provider = GoogleProvider(api_key=api_key)
    model = GoogleModel(
        "gemini-3.1-flash-lite",
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

    Return the name of the animal (in singular term) and the relevant details as plain text
    """
    agent = Agent(model, instructions=instructions, output_type=AnimalData)
    return agent


class AnimalData(BaseModel):
    name: str
    text: str


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/health")
async def health_check():
    """
    health check for the API
    - returns 200 when the API is up and the database is reachable
    - returns 503 when the database cannot be reached
    """
    try:
        async with sessionmanager.connect() as conn:
            await conn.execute(text("SELECT 1"))
        database = "ok"
    except Exception as e:
        logfire.error("health check: database unreachable", error=str(e))
        database = "unavailable"

    healthy = database == "ok"
    return JSONResponse(
        status_code=(
            status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE
        ),
        content={
            "status": "ok" if healthy else "degraded",
            "checks": {"api": "ok", "database": database},
        },
    )


@app.get("/redis")
async def redis_test():
    import redis

    r = redis.Redis(host="localhost", port=6379)
    r.set("foo", "bar")


@app.post("/redis_reserialize")
async def redis_key_retrieve(key: str):
    """
    test to retrieve previous search filters stored in redis
    """
    import redis
    from animal_finder.agents.feature_agent import SearchFilters

    r = redis.Redis(host="localhost", port=6379)
    json = r.get(key)
    data = SearchFilters.model_validate_json(json)
    print(data)


@app.post("/test")
async def get_features(prompt: str):
    agent = initialize_features_agent()
    result = await agent.run(prompt)
    print(result.output)

    return {"status": "ok"}


@app.get("/testdb")
async def test_db(db: Annotated[AsyncSession, Depends(get_db)]):
    from sqlalchemy import select

    result = await db.execute(select(Animal))
    animals = result.scalars().all()
    print(len(animals))


@app.post("/chat/stream")
async def stream_chat(
    prompt: str,
    db: Annotated[Session, Depends(get_db)],
    session_id: Annotated[str | None, Cookie()] = None,
):
    """
    main flow:
    - user gives a description of an animal they are trying to find
    - the chat agent will collect the list of features (include / exclude x feature) in json format as well as formatting
        the features into a more concise format
        - not sure if the json formatting part should be broken up as a tool call to another agent or not...
    - pass the formatted text to an embedder via tool call
    - pass the embedded vector to database to retrieve top x results, should also try to retrieve the full text of best result
        - maybe split this up into two parts (have a tool that retrieve full text for specified animal)
    - reformat this into a message showing the top animal, matching description points, and other animals that may be related
    """
    # need to manually set EventSourceResponse in order to attach session cookie

    if not session_id:
        session_id = str(uuid.uuid4())

    embedder = get_embedder()
    deps = ChatDeps(db, embedder, session_id)

    # agent = initialize_chat_agent()

    async def event_generator():
        agent = initialize_chat_agent()

        async with agent.run_stream(prompt, deps=deps) as result:
            async for message in result.stream_text():
                yield message

                # ServerSentEvent need to convert data to string instead of raw ServerSentEvent class
                # yield ServerSentEvent(
                #     data=message,
                #     event="message",
                # ).model_dump_json()
        print(result.all_messages())

    response = EventSourceResponse(event_generator())

    if session_id:
        response.set_cookie(
            key="session_id",
            value=session_id,
            httponly=True,
            samesite="lax",
            secure=True,  # False for local HTTP development
        )

    return response

    # async with agent.run_stream(prompt, deps=deps) as result:
    #     async for message in result.stream_text():
    #         yield ServerSentEvent(data=message, event="some event")


# @app.post("/chat/test_stream", response_class=EventSourceResponse)
# async def stream_chat(prompt: str) -> AsyncIterable[ServerSentEvent]:
#     agent = initialize_chat_agent()
#     async with agent.run_stream(prompt) as result:
#         async for message in result.stream_text():
#             yield ServerSentEvent(data=message, event="some event")
