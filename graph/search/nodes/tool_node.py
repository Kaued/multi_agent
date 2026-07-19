from langchain_core.messages import ToolMessage

from tools.search.search_tools import get_search_tools


def tool_node(state: dict):
    """Performs the tool call"""

    result = []
    tools = get_search_tools()
    tools_by_name = {tool.name: tool for tool in tools}

    for tool_call in state["messages"][-1].tool_calls:
        tool = tools_by_name[tool_call["name"]]
        observation = tool.invoke(tool_call["args"])
        result.append(
            ToolMessage(
                content=observation,
                tool_call_id=tool_call["id"],
                name=tool_call["name"],
            )
        )

    return {"messages": result}
