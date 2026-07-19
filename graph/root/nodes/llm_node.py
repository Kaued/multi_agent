from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from agents.root_agent import root_agent
from app.utils.context_window import fit_messages_to_context
from app.utils.sources import (
    SOURCE_LINE_PATTERN,
    ensure_sources_section,
    find_source_heading,
)
from graph.prompts.root_promp import system_prompt
from graph.states.root_state import RootState
from tools.root.root_tools import get_root_tools


def _extract_search_sources(messages: list) -> list[tuple[str, str]]:
    """Collect URLs returned by the search agent during the current user turn."""
    latest_user_index = max(
        (
            index
            for index, message in enumerate(messages)
            if isinstance(message, HumanMessage)
        ),
        default=-1,
    )
    sources: list[tuple[str, str]] = []
    seen_urls: set[str] = set()

    for message in messages[latest_user_index + 1 :]:
        if not isinstance(message, ToolMessage) or not isinstance(message.content, str):
            continue
        if message.name not in (None, "call_search_agent"):
            continue
        heading = find_source_heading(message.content)
        if heading is None:
            continue
        source_block = message.content[heading.end() :]
        for title, url in SOURCE_LINE_PATTERN.findall(source_block):
            if url not in seen_urls:
                seen_urls.add(url)
                sources.append((title.strip(), url))

    return sources


def llm_call(state: RootState) -> RootState:
    messages = list(state["messages"])
    model_llm = root_agent()

    if not any(
        isinstance(message, SystemMessage) and message.content == system_prompt
        for message in messages
    ):
        messages.insert(0, SystemMessage(content=system_prompt))

    model_messages = fit_messages_to_context(messages, get_root_tools())
    response = model_llm.invoke(model_messages)

    if not response.tool_calls and isinstance(response.content, str):
        sources = _extract_search_sources(messages)
        response = response.model_copy(
            update={
                "content": ensure_sources_section(response.content, sources),
            }
        )

    return {
        "messages": [response],
    }
