from langchain_core.messages import SystemMessage

from agents.postgres_agent import postgres_agent
from app.utils.context_window import fit_messages_to_context
from graph.prompts.postgres_prompt import system_prompt
from graph.states.postgres_state import PostgresState
from tools.postgres.postgres_tools import get_postgres_tools


def llm_call(state: PostgresState) -> PostgresState:
    messages = list(state["messages"])
    model_llm = postgres_agent()

    if not any(
        isinstance(message, SystemMessage) and message.content == system_prompt
        for message in messages
    ):
        messages.insert(0, SystemMessage(content=system_prompt))

    model_messages = fit_messages_to_context(messages, get_postgres_tools())
    response = model_llm.invoke(model_messages)

    return {
        "messages": [response],
    }
