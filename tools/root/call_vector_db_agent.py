from typing import Annotated

from langchain_core.messages import AnyMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

from graph.prompts.vector_db_prompt import system_prompt
from graph.vector_db.vector_db_graph import vector_db_graph
from tools.root.delegation import invoke_specialist


@tool
def call_vector_db_agent(
    messages: Annotated[list[AnyMessage], InjectedState("messages")],
    config: RunnableConfig = None,
) -> str:
    """Delegate a knowledge-base request to the vector database agent.

    Use this agent when the user asks for information that should be retrieved
    from the project's vector database. For a general informational question
    that does not belong to the PostgreSQL or weather agents, call this agent
    before considering web search. It searches the database in English and
    answers in the user's language using only facts supported by retrieved
    records.

    Returns:
        The vector database agent's final retrieval-based response.
    """
    graph = vector_db_graph()
    result = invoke_specialist(messages, graph, system_prompt, "vector-db", config)

    return str(result["messages"][-1].content)
