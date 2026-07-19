import os
from collections.abc import Sequence
from typing import Any

from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command, interrupt

_CHECKPOINT_CONFIG_KEYS = {
    "checkpoint_id",
    "checkpoint_map",
    "checkpoint_ns",
}


def _new_turn_messages(
    messages: Sequence[AnyMessage],
    system_prompt: str,
    has_history: bool,
) -> list[AnyMessage]:
    latest_user_message = next(
        (
            message
            for message in reversed(messages)
            if isinstance(message, HumanMessage)
        ),
        messages[-1] if messages else None,
    )
    agent_messages = [latest_user_message] if latest_user_message is not None else []
    if not has_history:
        agent_messages.insert(0, SystemMessage(content=system_prompt))
    return agent_messages


def _specialist_config(
    config: RunnableConfig | None,
    agent_name: str,
) -> RunnableConfig:
    """Give each specialist an isolated, stable checkpoint thread."""
    specialist_config: RunnableConfig = dict(config or {})
    configurable = {
        key: value
        for key, value in (config or {}).get("configurable", {}).items()
        if key not in _CHECKPOINT_CONFIG_KEYS and not key.startswith("__")
    }
    root_thread_id = configurable.get(
        "thread_id",
        os.getenv("LANGGRAPH_THREAD_ID", "default-conversation"),
    )
    configurable["thread_id"] = f"{root_thread_id}:{agent_name}"
    specialist_config["configurable"] = configurable
    specialist_tag = f"agent:{agent_name}"
    specialist_config["tags"] = [
        tag for tag in specialist_config.get("tags", []) if tag != specialist_tag
    ] + [specialist_tag]
    return specialist_config


def prepare_specialist_invocation(
    messages: Sequence[AnyMessage],
    graph: Any,
    system_prompt: str,
    agent_name: str,
    config: RunnableConfig | None,
) -> tuple[list[AnyMessage], RunnableConfig]:
    """Build non-duplicating input and config for a persistent specialist."""
    specialist_config = _specialist_config(config, agent_name)

    # Preserve direct-call compatibility. Normal graph tool execution always
    # injects a RunnableConfig and follows the checkpoint-aware branch below.
    if config is None:
        agent_messages = list(messages)
        if not any(
            isinstance(message, SystemMessage) and message.content == system_prompt
            for message in agent_messages
        ):
            agent_messages.insert(0, SystemMessage(content=system_prompt))
        return agent_messages, specialist_config

    snapshot = graph.get_state(specialist_config)
    has_history = bool(snapshot.values.get("messages"))
    return (
        _new_turn_messages(messages, system_prompt, has_history),
        specialist_config,
    )


def _snapshot_interrupts(snapshot: Any) -> list[Any]:
    return [
        pending_interrupt
        for task in getattr(snapshot, "tasks", ())
        for pending_interrupt in getattr(task, "interrupts", ())
    ]


def _result_interrupts(result: Any) -> list[Any]:
    if isinstance(result, dict):
        return list(result.get("__interrupt__", ()))
    return list(getattr(result, "interrupts", ()))


def _request_specialist_resume(
    pending_interrupts: Sequence[Any],
    specialist_config: RunnableConfig,
    agent_name: str,
) -> Any:
    """Surface a specialist interrupt through the root graph's checkpoint."""
    return interrupt(
        {
            "agent": agent_name,
            "thread_id": specialist_config["configurable"]["thread_id"],
            "requests": [
                {
                    "id": getattr(pending_interrupt, "id", None),
                    "value": getattr(pending_interrupt, "value", pending_interrupt),
                }
                for pending_interrupt in pending_interrupts
            ],
        }
    )


def invoke_specialist(
    messages: Sequence[AnyMessage],
    graph: Any,
    system_prompt: str,
    agent_name: str,
    config: RunnableConfig | None,
) -> Any:
    """Invoke a persistent specialist and bridge its HITL interrupts to root."""
    specialist_config = _specialist_config(config, agent_name)
    snapshot = graph.get_state(specialist_config) if config is not None else None
    pending_interrupts = _snapshot_interrupts(snapshot)

    if pending_interrupts:
        resume_value = _request_specialist_resume(
            pending_interrupts,
            specialist_config,
            agent_name,
        )
        result = graph.invoke(Command(resume=resume_value), specialist_config)
    else:
        if snapshot is None:
            agent_messages, specialist_config = prepare_specialist_invocation(
                messages,
                graph,
                system_prompt,
                agent_name,
                config,
            )
        else:
            agent_messages = _new_turn_messages(
                messages,
                system_prompt,
                bool(snapshot.values.get("messages")),
            )
        result = graph.invoke(
            {"messages": agent_messages},
            specialist_config,
        )

    pending_interrupts = _result_interrupts(result)
    while pending_interrupts:
        resume_value = _request_specialist_resume(
            pending_interrupts,
            specialist_config,
            agent_name,
        )
        result = graph.invoke(Command(resume=resume_value), specialist_config)
        pending_interrupts = _result_interrupts(result)

    return result
