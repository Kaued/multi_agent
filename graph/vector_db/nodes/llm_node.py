from langchain_core.messages import SystemMessage

from agents.vector_db_agent import vector_db_agent
from app.utils.context_window import fit_messages_to_context
from graph.prompts.vector_db_prompt import system_prompt
from graph.states.vector_db_state import VectorDbState
from tools.vector_db.search_tools import get_vector_db_tools


def llm_call(state: VectorDbState) -> VectorDbState:
    messages = list(state["messages"])
    model_llm = vector_db_agent()

    if not any(
        isinstance(message, SystemMessage) and message.content == system_prompt
        for message in messages
    ):
        messages.insert(0, SystemMessage(content=system_prompt))

    model_messages = fit_messages_to_context(messages, get_vector_db_tools())
    response = model_llm.invoke(model_messages)

    return {
        "messages": [response],
    }
