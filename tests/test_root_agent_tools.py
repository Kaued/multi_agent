import importlib
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage


class RootAgentToolTests(unittest.TestCase):
    tool_cases = (
        (
            "tools.root.call_weather_agent",
            "call_weather_agent",
            "weather_graph",
            "graph.prompts.weather_prompt",
        ),
        (
            "tools.root.call_search_agent",
            "call_search_agent",
            "search_graph",
            "graph.prompts.search_prompt",
        ),
        (
            "tools.root.call_vector_db_agent",
            "call_vector_db_agent",
            "vector_db_graph",
            "graph.prompts.vector_db_prompt",
        ),
        (
            "tools.root.call_postgre_agent",
            "call_postgres_agent",
            "postgres_graph",
            "graph.prompts.postgres_prompt",
        ),
    )

    def test_each_tool_adds_its_system_prompt_and_calls_its_agent_graph(self) -> None:
        for module_name, tool_name, graph_name, prompt_module_name in self.tool_cases:
            with self.subTest(tool=tool_name):
                module = importlib.import_module(module_name)
                tool = getattr(module, tool_name)
                system_prompt = importlib.import_module(
                    prompt_module_name
                ).system_prompt
                graph = MagicMock()
                graph.invoke.return_value = {
                    "messages": [AIMessage(content="agent response")]
                }
                original_messages = [HumanMessage(content="user request")]

                with patch.object(module, graph_name, return_value=graph):
                    response = tool.func(original_messages)

                delegated_messages = graph.invoke.call_args.args[0]["messages"]
                self.assertIsInstance(delegated_messages[0], SystemMessage)
                self.assertEqual(delegated_messages[0].content, system_prompt)
                self.assertIs(delegated_messages[1], original_messages[0])
                self.assertEqual(original_messages, [original_messages[0]])
                self.assertEqual(response, "agent response")

    def test_each_tool_does_not_duplicate_its_existing_system_prompt(self) -> None:
        for module_name, tool_name, graph_name, prompt_module_name in self.tool_cases:
            with self.subTest(tool=tool_name):
                module = importlib.import_module(module_name)
                tool = getattr(module, tool_name)
                system_prompt = importlib.import_module(
                    prompt_module_name
                ).system_prompt
                graph = MagicMock()
                graph.invoke.return_value = {
                    "messages": [AIMessage(content="agent response")]
                }
                messages = [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content="user request"),
                ]

                with patch.object(module, graph_name, return_value=graph):
                    tool.func(messages)

                delegated_messages = graph.invoke.call_args.args[0]["messages"]
                matching_prompts = [
                    message
                    for message in delegated_messages
                    if isinstance(message, SystemMessage)
                    and message.content == system_prompt
                ]
                self.assertEqual(len(matching_prompts), 1)

    def test_postgres_description_routes_commerce_entities(self) -> None:
        module = importlib.import_module("tools.root.call_postgre_agent")
        description = module.call_postgres_agent.description.lower()

        self.assertIn("commerce agent", description)
        self.assertIn("customers", description)
        self.assertIn("products", description)
        self.assertIn("orders", description)

    def test_conversation_messages_are_hidden_from_model_tool_schema(self) -> None:
        for module_name, tool_name, _, _ in self.tool_cases:
            with self.subTest(tool=tool_name):
                tool = getattr(importlib.import_module(module_name), tool_name)

                schema = tool.tool_call_schema.model_json_schema()

                self.assertNotIn("messages", schema.get("properties", {}))

    def test_runtime_config_is_forwarded_to_isolated_specialist_thread(
        self,
    ) -> None:
        module = importlib.import_module("tools.root.call_weather_agent")
        graph = MagicMock()
        graph.get_state.return_value = SimpleNamespace(values={})
        graph.invoke.return_value = {"messages": [AIMessage(content="agent response")]}

        with patch.object(module, "weather_graph", return_value=graph):
            module.call_weather_agent.invoke(
                {"messages": [HumanMessage(content="weather request")]},
                {
                    "configurable": {
                        "thread_id": "conversation-7",
                        "checkpoint_ns": "root-internal",
                    }
                },
            )

        specialist_config = graph.get_state.call_args.args[0]
        self.assertEqual(
            specialist_config["configurable"]["thread_id"],
            "conversation-7:weather",
        )
        self.assertNotIn(
            "checkpoint_ns",
            specialist_config["configurable"],
        )
        self.assertEqual(
            graph.invoke.call_args.args[1],
            specialist_config,
        )


if __name__ == "__main__":
    unittest.main()
