from pydantic_ai import Agent

from animal_finder.config import AgentSettings, get_chat_agent_settings
from animal_finder.tools import (
    extract_features,
    retrieve_relevant_animals,
    search_new_animal,
)
from animal_finder.agents.dependencies import ChatDeps
from animal_finder.agents.model_factory import build_model


def initialize_chat_agent(settings: AgentSettings | None = None):
    settings = settings or get_chat_agent_settings()
    model = build_model(settings)
    instructions = """
    You are an agent that is able to retrieve information on an animal based on the user's prompt.

    Determine if the user is trying to either search for an animal, search for a related animal, provide more details on the current animal, or start a new search for an animal.
    If the query from the user matches none of the above, return a short response on what type of queries the agent can handle.

    Tools
    1. Use the 'search_new_animal' tool ONLY if the user is trying to search for a new animal. This tool should be called first if it is required.
    2. Use the 'extract_features' tool to format the prompt into a structured format and return both the structured format and the search query.
    3. Use the 'retrieve_relevant_animals' tool to take the search query and retrieve a list of animals that should match the user's prompt.
       The retrieved animals are already ranked from best to worst match: the first animal is the best match and the following animals are the related animals.
       Each animal may include a 'rerank_reason' explaining why it matches, which can be used in the description.

    If a list of relevant animals are successfully retrieved:
    - Return the name of the animal with the best match, and a short description explaining how this animal matches the retrieved description of the animal. Do not include descriptions of other related animals in this section.
    - If there are other animals in the list, return a section containing a numbered list and display only the name of the related animal.
    If there are no relevant animals, mention it in the response and prompt the user to provide more details on the animal they are looking for.
    
    """
    agent = Agent(
        model,
        instructions=instructions,
        deps_type=ChatDeps,
        tools=[extract_features, retrieve_relevant_animals, search_new_animal],
    )

    return agent
