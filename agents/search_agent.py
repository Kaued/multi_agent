import os

from app.utils.load_llm import load_llm
from tools.search.search_tools import get_search_tools


def search_agent():
    model = os.getenv("SEARCH_AGENT_MODEL")

    llm = load_llm(model)

    tools = get_search_tools()

    llm_with_tools = llm.bind_tools(tools)

    return llm_with_tools
