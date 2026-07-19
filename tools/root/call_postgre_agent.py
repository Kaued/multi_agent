from typing import Annotated

from langchain_core.messages import AnyMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

from graph.postgres.postgres_graph import postgres_graph
from graph.prompts.postgres_prompt import system_prompt
from tools.root.delegation import invoke_specialist


@tool
def call_postgres_agent(
    messages: Annotated[list[AnyMessage], InjectedState("messages")],
    config: RunnableConfig = None,
) -> str:
    """Delegate commerce-data requests to the PostgreSQL commerce agent.

    Use this agent when the user asks to perform an action involving customers,
    products, or orders. It can safely retrieve, create, update, and delete
    records in those commerce tables, and it requests explicit confirmation
    before changing data.

    Returns:
        The PostgreSQL commerce agent's final database-backed response.
    """
    graph = postgres_graph()
    result = invoke_specialist(messages, graph, system_prompt, "postgres", config)
    return str(result["messages"][-1].content)


# Preserve compatibility with the module's original abbreviated filename.
call_postgre_agent = call_postgres_agent
