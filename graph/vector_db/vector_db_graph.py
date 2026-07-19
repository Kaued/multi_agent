from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.utils.checkpointer import get_checkpointer
from graph.states.vector_db_state import VectorDbState
from graph.vector_db.nodes.llm_node import llm_call
from graph.vector_db.nodes.tool_node import tool_node
from graph.vector_db.utils.vector_db_decision import vector_db_decision


def vector_db_graph(
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph[VectorDbState, None, VectorDbState, VectorDbState]:
    vector_db_agent = StateGraph(VectorDbState)

    vector_db_agent.add_node("llm_node", llm_call)
    vector_db_agent.add_node("tool_node", tool_node)

    vector_db_agent.add_edge(START, "llm_node")
    vector_db_agent.add_conditional_edges(
        "llm_node", vector_db_decision, ["tool_node", END]
    )

    vector_db_agent.add_edge("tool_node", "llm_node")

    return vector_db_agent.compile(
        checkpointer=checkpointer if checkpointer is not None else get_checkpointer()
    )
