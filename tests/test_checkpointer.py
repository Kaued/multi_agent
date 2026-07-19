import os
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.checkpoint.memory import InMemorySaver

from app.utils import checkpointer as checkpointer_module
from app.utils.checkpointer import _database_uri
from graph.postgres.postgres_graph import postgres_graph
from graph.root.root_graph import root_graph
from graph.search.search_graph import search_graph
from graph.vector_db.vector_db_graph import vector_db_graph
from graph.weather.weather_grapy import weather_graph
from tools.root.delegation import invoke_specialist, prepare_specialist_invocation


class CheckpointerTests(unittest.TestCase):
    def tearDown(self) -> None:
        checkpointer_module.close_checkpointer()

    def test_normalizes_sqlalchemy_database_url_for_psycopg(self) -> None:
        with patch.dict(
            os.environ,
            {"DATABASE_URL": ("postgresql+psycopg://postgres:secret@db:5432/agent_db")},
            clear=True,
        ):
            self.assertEqual(
                _database_uri(),
                "postgresql://postgres:secret@db:5432/agent_db",
            )

    @patch("app.utils.checkpointer.PostgresSaver")
    @patch("app.utils.checkpointer.ConnectionPool")
    def test_initializes_schema_once_and_reuses_pool(
        self,
        pool_class: MagicMock,
        saver_class: MagicMock,
    ) -> None:
        pool = pool_class.return_value
        saver = saver_class.return_value

        first = checkpointer_module.get_checkpointer()
        second = checkpointer_module.get_checkpointer()

        self.assertIs(first, saver)
        self.assertIs(second, saver)
        pool_class.assert_called_once()
        pool.wait.assert_called_once_with()
        saver.setup.assert_called_once_with()

    def test_every_graph_accepts_the_shared_checkpointer(self) -> None:
        for graph_factory in (
            root_graph,
            weather_graph,
            search_graph,
            vector_db_graph,
            postgres_graph,
        ):
            with self.subTest(graph=graph_factory.__name__):
                saver = InMemorySaver()

                graph = graph_factory(checkpointer=saver)

                self.assertIs(graph.checkpointer, saver)


class SpecialistPersistenceTests(unittest.TestCase):
    def test_specialist_uses_isolated_thread_and_only_new_turn(self) -> None:
        graph = MagicMock()
        graph.get_state.return_value = SimpleNamespace(
            values={"messages": [AIMessage(content="previous response")]}
        )
        old_user = HumanMessage(content="old request")
        latest_user = HumanMessage(content="follow-up request")

        messages, config = prepare_specialist_invocation(
            [old_user, AIMessage(content="old response"), latest_user],
            graph,
            "specialist prompt",
            "weather",
            {
                "configurable": {
                    "thread_id": "conversation-42",
                    "checkpoint_ns": "root-internal",
                }
            },
        )

        self.assertEqual(messages, [latest_user])
        self.assertEqual(
            config["configurable"]["thread_id"],
            "conversation-42:weather",
        )
        self.assertNotIn("checkpoint_ns", config["configurable"])

    def test_first_specialist_turn_stores_system_prompt(self) -> None:
        graph = MagicMock()
        graph.get_state.return_value = SimpleNamespace(values={})
        user_message = HumanMessage(content="first request")

        messages, _ = prepare_specialist_invocation(
            [user_message],
            graph,
            "specialist prompt",
            "postgres",
            {"configurable": {"thread_id": "conversation-1"}},
        )

        self.assertIsInstance(messages[0], SystemMessage)
        self.assertEqual(messages[0].content, "specialist prompt")
        self.assertIs(messages[1], user_message)

    @patch("tools.root.delegation.interrupt", return_value="sim")
    def test_pending_specialist_interrupt_is_resumed_through_root(
        self,
        root_interrupt: MagicMock,
    ) -> None:
        pending_interrupt = SimpleNamespace(
            id="interrupt-1",
            value="Confirma a alteração?",
        )
        graph = MagicMock()
        graph.get_state.return_value = SimpleNamespace(
            values={"messages": [AIMessage(content="pending")]},
            tasks=[SimpleNamespace(interrupts=[pending_interrupt])],
        )
        graph.invoke.return_value = {
            "messages": [AIMessage(content="alteração concluída")]
        }

        result = invoke_specialist(
            [HumanMessage(content="altere o pedido")],
            graph,
            "specialist prompt",
            "postgres",
            {"configurable": {"thread_id": "conversation-9"}},
        )

        root_interrupt.assert_called_once()
        command = graph.invoke.call_args.args[0]
        self.assertEqual(command.resume, "sim")
        self.assertEqual(result["messages"][-1].content, "alteração concluída")


if __name__ == "__main__":
    unittest.main()
