from typing import Literal

from langgraph.graph import END

from graph.states.root_state import RootState


def root_decision(state: RootState) -> Literal["tool_node", END]:  # type: ignore
    """Continue to delegation tools when the root model requests a tool call."""
    if state["messages"][-1].tool_calls:
        return "tool_node"
    return END