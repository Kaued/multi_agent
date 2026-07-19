import os

from app.utils.load_llm import load_llm
from tools.root.root_tools import get_root_tools


def root_agent():
    """Create the root orchestration model with all delegation tools bound."""
    model = os.getenv("ROOT_AGENT_MODEL")
    llm = load_llm(model)
    return llm.bind_tools(get_root_tools())
