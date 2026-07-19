import json
import unittest
from types import SimpleNamespace

from langchain_core.messages import AIMessage, AIMessageChunk
from langgraph.types import Command

from app.api import create_app


class FakeGraph:
    def __init__(
        self,
        *,
        interrupted: bool = False,
        pending_checkpoint: bool = False,
    ) -> None:
        self.interrupted = interrupted
        self.pending_checkpoint = pending_checkpoint
        self.last_input = None
        self.last_config = None
        self.last_stream_kwargs = None

    def stream(self, graph_input, config, **kwargs):
        self.last_input = graph_input
        self.last_config = config
        self.last_stream_kwargs = kwargs
        yield {
            "type": "messages",
            "data": (
                AIMessageChunk(content="resultado interno com Sources"),
                {
                    "langgraph_node": "llm_node",
                    "tags": ["agent:root", "agent:search"],
                },
            ),
        }
        yield {
            "type": "messages",
            "data": (
                AIMessageChunk(content="Olá"),
                {"langgraph_node": "llm_node", "tags": ["agent:root"]},
            ),
        }
        yield {
            "type": "values",
            "data": {"messages": [AIMessage(content="Olá, resultado final")]},
            "interrupts": (
                (SimpleNamespace(id="interrupt-1", value="Confirmar?"),)
                if self.interrupted
                else ()
            ),
        }

    def get_state(self, _config):
        interrupts = (
            (SimpleNamespace(id="interrupt-1", value="Confirmar?"),)
            if self.pending_checkpoint
            else ()
        )
        return SimpleNamespace(tasks=[SimpleNamespace(interrupts=interrupts)])


def parse_sse(response_data: bytes) -> list[dict]:
    return [
        json.loads(block.removeprefix("data: "))
        for block in response_data.decode().strip().split("\n\n")
    ]


class AgentAPITests(unittest.TestCase):
    def setUp(self) -> None:
        self.graph = FakeGraph()
        self.app = create_app(self.graph)
        self.app.testing = True
        self.client = self.app.test_client()

    def test_exposes_only_the_agent_stream_route(self) -> None:
        routes = {
            (rule.rule, tuple(sorted(rule.methods - {"OPTIONS"})))
            for rule in self.app.url_map.iter_rules()
        }

        self.assertEqual(routes, {("/api/v1/agent/stream", ("POST",))})

    def test_streams_tokens_and_final_result_as_sse(self) -> None:
        response = self.client.post(
            "/api/v1/agent/stream",
            json={"message": "Olá", "thread_id": "conversation-1"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "text/event-stream")
        self.assertEqual(response.headers["X-Thread-ID"], "conversation-1")
        events = parse_sse(response.data)
        self.assertEqual(
            [event["type"] for event in events],
            ["metadata", "token", "final", "done"],
        )
        self.assertEqual(events[1]["content"], "Olá")
        self.assertNotIn("resultado interno", response.data.decode())
        self.assertEqual(
            events[2]["message"]["content"],
            "Olá, resultado final",
        )
        self.assertEqual(events[-1]["status"], "completed")
        self.assertEqual(self.graph.last_stream_kwargs["version"], "v2")
        self.assertEqual(self.graph.last_stream_kwargs["durability"], "sync")

    def test_generates_thread_id_when_client_omits_it(self) -> None:
        response = self.client.post(
            "/api/v1/agent/stream",
            json={"message": "Olá"},
        )

        events = parse_sse(response.data)
        self.assertEqual(
            events[0]["thread_id"],
            response.headers["X-Thread-ID"],
        )

    def test_resumes_same_checkpoint_thread(self) -> None:
        self.graph.pending_checkpoint = True
        response = self.client.post(
            "/api/v1/agent/stream",
            json={"resume": "sim", "thread_id": "conversation-1"},
        )
        _ = response.data

        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(self.graph.last_input, Command)
        self.assertEqual(self.graph.last_input.resume, "sim")
        self.assertEqual(
            self.graph.last_config["configurable"]["thread_id"],
            "conversation-1",
        )

    def test_rejects_resume_without_pending_checkpoint(self) -> None:
        response = self.client.post(
            "/api/v1/agent/stream",
            json={"resume": "sim", "thread_id": "conversation-1"},
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.json["error"]["code"],
            "checkpoint_not_interrupted",
        )

    def test_streams_interrupt_instead_of_final_result(self) -> None:
        client = create_app(FakeGraph(interrupted=True)).test_client()

        response = client.post(
            "/api/v1/agent/stream",
            json={"message": "Excluir pedido", "thread_id": "conversation-2"},
        )

        events = parse_sse(response.data)
        self.assertEqual(
            [event["type"] for event in events],
            ["metadata", "token", "interrupt", "done"],
        )
        self.assertEqual(events[2]["interrupts"][0]["value"], "Confirmar?")
        self.assertEqual(events[-1]["status"], "interrupted")

    def test_rejects_invalid_requests_before_opening_stream(self) -> None:
        for payload in ({}, {"message": ""}, {"message": "x", "resume": True}):
            with self.subTest(payload=payload):
                response = self.client.post(
                    "/api/v1/agent/stream",
                    json=payload,
                )

                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.mimetype, "application/json")


if __name__ == "__main__":
    unittest.main()
