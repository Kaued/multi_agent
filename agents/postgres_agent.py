import os

from app.utils.load_llm import load_llm
from tools.postgres.postgres_tools import get_postgres_tools


def postgres_agent():
    model = os.getenv("POSTGRES_AGENT_MODEL")

    llm = load_llm(model)

    tools = get_postgres_tools()

    llm_with_tools = llm.bind_tools(tools)

    return llm_with_tools
