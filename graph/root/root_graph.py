from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.utils.checkpointer import get_checkpointer
from graph.root.nodes.llm_node import llm_call
from graph.root.nodes.tool_node import tool_node
from graph.root.utils.postgres_decision import root_decision
from graph.states.root_state import RootState


def root_graph(
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph[RootState, None, RootState, RootState]:
    """Build the graph that orchestrates all specialized agents."""
    graph = StateGraph(RootState)
    graph.add_node("llm_node", llm_call)
    graph.add_node("tool_node", tool_node)
    graph.add_edge(START, "llm_node")
    graph.add_conditional_edges("llm_node", root_decision, ["tool_node", END])
    graph.add_edge("tool_node", "llm_node")
    return graph.compile(
        checkpointer=checkpointer if checkpointer is not None else get_checkpointer()
    )
