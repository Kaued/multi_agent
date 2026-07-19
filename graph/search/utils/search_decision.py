from typing import Literal

from langgraph.graph import END

from graph.states.search_state import SearchState


def search_decision(state: SearchState) -> Literal["tool_node", END]: # type: ignore
    """Decides whether to call the tool or the LLM based on the state."""
    last_message = state["messages"][-1]
    
    if last_message.tool_calls:
        return "tool_node"
    else:
        return END