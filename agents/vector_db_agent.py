import os

from app.utils.load_llm import load_llm
from tools.vector_db.search_tools import get_vector_db_tools


def vector_db_agent():
    model = os.getenv("VECTOR_DB_AGENT_MODEL")

    llm = load_llm(model)

    tools = get_vector_db_tools()
    
    llm_with_tools = llm.bind_tools(tools)

    return llm_with_tools