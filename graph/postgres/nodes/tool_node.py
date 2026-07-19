from langchain.messages import ToolMessage
from pydantic import ValidationError

from tools.postgres.postgres_tools import get_postgres_tools


def tool_node(state: dict):
    """Performs the tool call"""

    result = []
    tools = get_postgres_tools()
    tools_by_name = {tool.name: tool for tool in tools}

    for tool_call in state["messages"][-1].tool_calls:
        tool = tools_by_name[tool_call["name"]]
        try:
            observation = tool.invoke(tool_call["args"])
        except ValidationError as error:
            observation = (
                "Argumentos inválidos para a ferramenta PostgreSQL. "
                "Envie params como um objeto JSON com os placeholders da query. "
                f"Detalhes: {error}"
            )
        result.append(ToolMessage(content=observation, tool_call_id=tool_call["id"]))

    return {"messages": result}
