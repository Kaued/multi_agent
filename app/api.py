import json
import os
from collections.abc import Iterator, Mapping
from datetime import date, datetime
from typing import Any
from uuid import uuid4

import dotenv
from flask import Flask, Response, jsonify, request, stream_with_context
from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.types import Command

from graph.root.root_graph import root_graph

dotenv.load_dotenv()

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}
MAX_THREAD_ID_LENGTH = 256
MAX_MESSAGE_LENGTH = 100_000


def _message_payload(message: BaseMessage) -> dict[str, Any]:
    payload = {"type": message.type, "content": message.content}
    for field in ("id", "name", "tool_call_id", "tool_calls"):
        value = getattr(message, field, None)
        if value:
            payload[field] = value
    return payload


def _json_default(value: Any) -> Any:
    if isinstance(value, BaseMessage):
        return _message_payload(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return str(value)


def _sse(payload: dict[str, Any]) -> str:
    data = json.dumps(payload, ensure_ascii=False, default=_json_default)
    return f"data: {data}\n\n"


def _pending_interrupts(snapshot: Any) -> list[Any]:
    return [
        pending_interrupt
        for task in getattr(snapshot, "tasks", ())
        for pending_interrupt in getattr(task, "interrupts", ())
    ]


def _interrupt_payload(pending_interrupt: Any) -> dict[str, Any]:
    return {
        "id": getattr(pending_interrupt, "id", None),
        "value": getattr(pending_interrupt, "value", pending_interrupt),
    }


def _thread_id(value: Any) -> str:
    if value is None:
        return str(uuid4())
    if not isinstance(value, str):
        raise ValueError("thread_id deve ser uma string.")
    if not value or len(value) > MAX_THREAD_ID_LENGTH:
        raise ValueError(
            f"thread_id deve possuir entre 1 e {MAX_THREAD_ID_LENGTH} caracteres."
        )
    return value


def _graph_input(payload: dict[str, Any]) -> dict[str, Any] | Command:
    has_message = "message" in payload
    has_resume = "resume" in payload
    if has_message == has_resume:
        raise ValueError("Informe exatamente um dos campos: message ou resume.")
    if has_resume:
        return Command(resume=payload["resume"])

    message = payload["message"]
    if not isinstance(message, str) or not message.strip():
        raise ValueError("message deve ser uma string não vazia.")
    if len(message) > MAX_MESSAGE_LENGTH:
        raise ValueError(f"message não pode exceder {MAX_MESSAGE_LENGTH} caracteres.")
    return {"messages": [HumanMessage(content=message)]}


def _agent_name(metadata: Mapping[str, Any]) -> str:
    agent_tags = [
        tag.removeprefix("agent:")
        for tag in metadata.get("tags", ())
        if isinstance(tag, str) and tag.startswith("agent:")
    ]
    for agent in agent_tags:
        if agent != "root":
            return agent
    if agent_tags:
        return "root"
    return "root"


def _error(code: str, message: str, status: int) -> tuple[Response, int]:
    return jsonify({"error": {"code": code, "message": message}}), status


def create_app(graph: Any | None = None) -> Flask:
    """Create a Flask API with one persistent SSE agent endpoint."""
    app = Flask(__name__, static_folder=None)
    agent_graph = graph if graph is not None else root_graph()

    @app.post("/api/v1/agent/stream")
    def stream_agent() -> Response | tuple[Response, int]:
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return _error("invalid_json", "Envie um objeto JSON válido.", 400)

        try:
            thread_id = _thread_id(payload.get("thread_id"))
            graph_input = _graph_input(payload)
        except ValueError as error:
            return _error("invalid_request", str(error), 400)

        config = {
            "configurable": {"thread_id": thread_id},
            "tags": ["agent:root"],
        }
        checkpoint_interrupts = _pending_interrupts(agent_graph.get_state(config))
        is_resume = isinstance(graph_input, Command)
        if is_resume and not checkpoint_interrupts:
            return _error(
                "checkpoint_not_interrupted",
                "A thread não possui uma interrupção pendente.",
                409,
            )
        if not is_resume and checkpoint_interrupts:
            return _error(
                "checkpoint_requires_resume",
                "A thread está interrompida; envie resume em vez de message.",
                409,
            )

        @stream_with_context
        def event_stream() -> Iterator[str]:
            last_values: dict[str, Any] = {}
            interrupts: list[Any] = []
            yield _sse({"type": "metadata", "thread_id": thread_id})

            try:
                for event in agent_graph.stream(
                    graph_input,
                    config,
                    stream_mode=["messages", "values"],
                    version="v2",
                    durability="sync",
                ):
                    if event["type"] == "messages":
                        message, metadata = event["data"]
                        agent = _agent_name(metadata)
                        if message.content and agent == "root":
                            yield _sse(
                                {
                                    "type": "token",
                                    "agent": agent,
                                    "node": metadata.get("langgraph_node"),
                                    "content": message.content,
                                }
                            )
                    elif event["type"] == "values":
                        last_values = event["data"]
                        interrupts = list(event.get("interrupts", ()))

                if interrupts:
                    status = "interrupted"
                    yield _sse(
                        {
                            "type": "interrupt",
                            "thread_id": thread_id,
                            "interrupts": [
                                _interrupt_payload(item) for item in interrupts
                            ],
                        }
                    )
                else:
                    status = "completed"
                    messages = last_values.get("messages", [])
                    if messages:
                        yield _sse(
                            {
                                "type": "final",
                                "thread_id": thread_id,
                                "message": _message_payload(messages[-1]),
                            }
                        )

                yield _sse({"type": "done", "status": status})
            except Exception:
                app.logger.exception("Agent failed for thread %s", thread_id)
                yield _sse(
                    {
                        "type": "error",
                        "code": "agent_execution_failed",
                        "message": "Falha ao executar o agente.",
                    }
                )
                yield _sse({"type": "done", "status": "failed"})

        response = Response(
            event_stream(),
            mimetype="text/event-stream",
            headers=SSE_HEADERS,
        )
        response.headers["X-Thread-ID"] = thread_id
        return response

    return app


def main() -> None:
    create_app().run(
        host=os.getenv("API_HOST", "127.0.0.1"),
        port=int(os.getenv("API_PORT", "5000")),
        threaded=True,
    )


if __name__ == "__main__":
    main()
