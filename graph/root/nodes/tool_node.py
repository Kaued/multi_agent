from langchain_core.messages import ToolMessage

from tools.root.root_tools import get_root_tools


def tool_node(state: dict):
    """Performs the tool call"""

    result = []
    tools = get_root_tools()
    tools_by_name = {tool.name: tool for tool in tools}

    for tool_call in state["messages"][-1].tool_calls:
        tool = tools_by_name[tool_call["name"]]
        # The root model only selects a specialized agent. Conversation state is
        # injected here instead of asking the model to serialize LangChain
        # message objects as tool arguments. Exclude the pending delegation call
        # itself from the specialized agent's input history.
        tool_args = {
            **tool_call["args"],
            "messages": state["messages"][:-1],
        }
        observation = tool.invoke(tool_args)
        result.append(
            ToolMessage(
                content=str(observation),
                tool_call_id=tool_call["id"],
                name=tool_call["name"],
            )
        )

    return {"messages": result}
