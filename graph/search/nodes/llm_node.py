import re

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from agents.search_agent import search_agent
from app.utils.context_window import fit_messages_to_context
from app.utils.sources import SOURCE_LINE_PATTERN, ensure_sources_section
from graph.prompts.search_prompt import system_prompt
from graph.states.search_state import SearchState
from tools.search.search_tools import get_search_tools

IGNORED_RESULT_PATTERN = re.compile(
    r"(?:"
    r"n[aã]o (?:tenho|possuo|consigo|consegui|foi poss[ií]vel).{0,30}(?:acesso|acessar)"
    r"|n[aã]o encontrei"
    r"|nenhum resultado"
    r"|(?:do not|don['’]t) have access"
    r"|cannot access"
    r"|unable to access"
    r"|could not find"
    r"|no (?:search )?results"
    r")",
    flags=re.IGNORECASE | re.DOTALL,
)
PORTUGUESE_PATTERN = re.compile(
    r"\b(?:qual|quais|como|quando|onde|quem|porque|por que|pesquise|busque|sobre)\b",
    flags=re.IGNORECASE,
)
SEARCH_RESULT_MARKER = "Source URLs returned by the search tool:"
SEARCH_RESULT_INSTRUCTION = """
The current user turn already contains a successful `search_web` ToolMessage.
Treat its titles, URLs, and content excerpts as the evidence retrieved for this
request. Answer from that evidence now. Do not say that you cannot access the
search, that no search was performed, or that the returned result is merely
hypothetical. If the evidence is incomplete, use what it explicitly supports
and state only the remaining limitation.
""".strip()


def _current_turn(messages: list) -> list:
    latest_user_index = max(
        (
            index
            for index, message in enumerate(messages)
            if isinstance(message, HumanMessage)
        ),
        default=0,
    )
    return messages[latest_user_index:]


def _search_evidence(messages: list) -> str | None:
    """Return the latest successful search result from the current user turn."""
    for message in reversed(_current_turn(messages)):
        if not isinstance(message, ToolMessage) or not isinstance(message.content, str):
            continue
        if SEARCH_RESULT_MARKER not in message.content:
            continue
        evidence = message.content.split(SEARCH_RESULT_MARKER, maxsplit=1)[0]
        evidence = evidence.removeprefix("Search results:").strip()
        if evidence:
            return evidence
    return None


def _extract_sources(messages: list) -> list[tuple[str, str]]:
    """Extract and deduplicate source titles and URLs from search tool output."""
    sources: list[tuple[str, str]] = []
    seen_urls: set[str] = set()

    for message in _current_turn(messages):
        if not isinstance(message, ToolMessage) or not isinstance(message.content, str):
            continue
        if SEARCH_RESULT_MARKER not in message.content:
            continue
        source_block = message.content.rsplit(SEARCH_RESULT_MARKER, maxsplit=1)[-1]
        for title, url in SOURCE_LINE_PATTERN.findall(source_block):
            if url not in seen_urls:
                seen_urls.add(url)
                sources.append((title.strip(), url))

    return sources


def _fallback_to_search_evidence(messages: list, evidence: str) -> str:
    """Expose retrieved evidence when the model incorrectly rejects it."""
    user_message = next(
        (
            message.content
            for message in reversed(messages)
            if isinstance(message, HumanMessage) and isinstance(message.content, str)
        ),
        "",
    )
    if PORTUGUESE_PATTERN.search(user_message):
        introduction = (
            "A pesquisa retornou as evidências abaixo. Elas são o resultado "
            "obtido pela ferramenta para esta solicitação:"
        )
    else:
        introduction = (
            "The search returned the evidence below. This is the result "
            "retrieved by the tool for this request:"
        )
    return f"{introduction}\n\n{evidence}"


def llm_call(state: SearchState) -> SearchState:
    messages = list(state["messages"])
    model_llm = search_agent()
    evidence = _search_evidence(messages)

    effective_system_prompt = system_prompt
    if evidence is not None:
        effective_system_prompt += f"\n\n{SEARCH_RESULT_INSTRUCTION}"
    system_index = next(
        (
            index
            for index, message in enumerate(messages)
            if isinstance(message, SystemMessage) and message.content == system_prompt
        ),
        None,
    )
    if system_index is None:
        messages.insert(0, SystemMessage(content=effective_system_prompt))
    else:
        messages[system_index] = messages[system_index].model_copy(
            update={"content": effective_system_prompt}
        )

    model_messages = fit_messages_to_context(messages, get_search_tools())
    response = model_llm.invoke(model_messages)

    if not response.tool_calls and isinstance(response.content, str):
        sources = _extract_sources(messages)
        content = response.content
        if evidence is not None and (
            not content.strip() or IGNORED_RESULT_PATTERN.search(content)
        ):
            content = _fallback_to_search_evidence(messages, evidence)
        response = response.model_copy(
            update={
                "content": ensure_sources_section(content, sources),
            }
        )

    return {
        "messages": [response],
    }
