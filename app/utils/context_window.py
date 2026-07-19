import os
from collections.abc import Sequence
from dataclasses import dataclass

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.messages.utils import (
    count_tokens_approximately,
    trim_messages,
)
from langchain_core.tools import BaseTool


@dataclass(frozen=True)
class ContextWindow:
    total_tokens: int
    response_tokens: int

    @property
    def input_tokens(self) -> int:
        return self.total_tokens - self.response_tokens


def _has_valid_tool_pairs(messages: Sequence[BaseMessage]) -> bool:
    pending_tool_calls: set[str] = set()
    for message in messages:
        if isinstance(message, AIMessage) and message.tool_calls:
            pending_tool_calls = {tool_call["id"] for tool_call in message.tool_calls}
        elif isinstance(message, ToolMessage):
            if message.tool_call_id not in pending_tool_calls:
                return False
            pending_tool_calls.remove(message.tool_call_id)
        elif pending_tool_calls:
            return False
    return not pending_tool_calls


def _shorten_text(text: str, target_chars: int) -> str:
    marker = "\n\n[... conteúdo anterior compactado ...]\n\n"
    if target_chars >= len(text):
        return text
    if target_chars <= len(marker) + 2:
        return text[:target_chars]
    available = target_chars - len(marker)
    head_size = (available * 2) // 3
    return f"{text[:head_size]}{marker}{text[-(available - head_size) :]}"


def _compact_current_turn(
    messages: list[BaseMessage],
    max_tokens: int,
    token_counter,
) -> list[BaseMessage]:
    latest_user_index = max(
        (
            index
            for index, message in enumerate(messages)
            if isinstance(message, HumanMessage)
        ),
        default=-1,
    )
    system_messages = [
        message
        for message in messages[:latest_user_index]
        if isinstance(message, SystemMessage)
    ]
    current_turn = system_messages + messages[latest_user_index:]

    while token_counter(current_turn) > max_tokens:
        candidates = [
            (index, message)
            for index, message in enumerate(current_turn)
            if isinstance(message, ToolMessage)
            and isinstance(message.content, str)
            and len(message.content) > 256
        ]
        if not candidates:
            break
        index, message = max(candidates, key=lambda item: len(item[1].content))
        excess_tokens = token_counter(current_turn) - max_tokens
        target_chars = max(256, len(message.content) - excess_tokens * 3)
        current_turn[index] = message.model_copy(
            update={"content": _shorten_text(message.content, target_chars)}
        )

    if token_counter(current_turn) > max_tokens:
        raise ValueError(
            "LLM_CONTEXT_WINDOW is too small for the system prompt, tool schemas, "
            "latest user turn, and reserved response. Increase it in .env."
        )
    return current_turn


def get_context_window() -> ContextWindow:
    """Read and validate the model context limits from the environment."""
    try:
        total_tokens = int(os.getenv("LLM_CONTEXT_WINDOW", "32768"))
        response_tokens = int(os.getenv("LLM_RESPONSE_TOKEN_RESERVE", "4096"))
    except ValueError as error:
        raise ValueError(
            "LLM_CONTEXT_WINDOW and LLM_RESPONSE_TOKEN_RESERVE must be integers."
        ) from error

    if total_tokens < 2 or not 0 < response_tokens < total_tokens:
        raise ValueError(
            "Expected LLM_CONTEXT_WINDOW > LLM_RESPONSE_TOKEN_RESERVE > 0."
        )
    return ContextWindow(total_tokens, response_tokens)


def fit_messages_to_context(
    messages: Sequence[BaseMessage],
    tools: Sequence[BaseTool] = (),
) -> list[BaseMessage]:
    """Keep the latest valid chat history while reserving response capacity."""
    context_window = get_context_window()

    def token_counter(items: list[BaseMessage]) -> int:
        # Three characters per token is conservative for Portuguese text.
        return count_tokens_approximately(
            items,
            chars_per_token=3.0,
            tools=list(tools),
        )

    message_list = list(messages)
    if token_counter(message_list) <= context_window.input_tokens:
        return message_list

    trimmed = trim_messages(
        message_list,
        max_tokens=context_window.input_tokens,
        token_counter=token_counter,
        strategy="last",
        allow_partial=True,
        include_system=True,
        start_on="human",
        end_on=("human", "tool"),
    )
    latest_user = next(
        (
            message
            for message in reversed(message_list)
            if isinstance(message, HumanMessage)
        ),
        None,
    )
    if (
        latest_user is not None
        and latest_user in trimmed
        and _has_valid_tool_pairs(trimmed)
    ):
        return trimmed
    return _compact_current_turn(
        message_list,
        context_window.input_tokens,
        token_counter,
    )
