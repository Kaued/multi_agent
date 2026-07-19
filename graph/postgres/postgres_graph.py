from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.utils.checkpointer import get_checkpointer
from graph.postgres.nodes.llm_node import llm_call
from graph.postgres.nodes.tool_node import tool_node
from graph.postgres.utils.postgres_decision import postgres_decision
from graph.states.postgres_state import PostgresState


def postgres_graph(
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph[PostgresState, None, PostgresState, PostgresState]:
    postgres_agent = StateGraph(PostgresState)

    postgres_agent.add_node("llm_node", llm_call)
    postgres_agent.add_node("tool_node", tool_node)

    postgres_agent.add_edge(START, "llm_node")
    postgres_agent.add_conditional_edges(
        "llm_node", postgres_decision, ["tool_node", END]
    )

    postgres_agent.add_edge("tool_node", "llm_node")

    return postgres_agent.compile(
        checkpointer=checkpointer if checkpointer is not None else get_checkpointer()
    )
