from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.utils.checkpointer import get_checkpointer
from graph.search.nodes.llm_node import llm_call
from graph.search.nodes.tool_node import tool_node
from graph.search.utils.search_decision import search_decision
from graph.states.search_state import SearchState


def search_graph(
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph[SearchState, None, SearchState, SearchState]:
    search_agent = StateGraph(SearchState)

    search_agent.add_node("llm_node", llm_call)
    search_agent.add_node("tool_node", tool_node)

    search_agent.add_edge(START, "llm_node")
    search_agent.add_conditional_edges("llm_node", search_decision, ["tool_node", END])

    search_agent.add_edge("tool_node", "llm_node")

    return search_agent.compile(
        checkpointer=checkpointer if checkpointer is not None else get_checkpointer()
    )
