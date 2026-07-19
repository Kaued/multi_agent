import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from graph.postgres.nodes.tool_node import tool_node
from tools.postgres.posgresql_exec import execute_sql_safe


class PostgresToolNodeTests(unittest.TestCase):
    @patch("graph.postgres.nodes.tool_node.get_postgres_tools")
    def test_executes_tool_from_postgres_tool_registry(
        self, get_postgres_tools: MagicMock
    ) -> None:
        tool = MagicMock()
        tool.name = "execute_sql_safe"
        tool.invoke.return_value = '{"rows": []}'
        get_postgres_tools.return_value = [tool]
        state = {
            "messages": [
                SimpleNamespace(
                    tool_calls=[
                        {
                            "name": "execute_sql_safe",
                            "args": {"query": "SELECT id FROM customers"},
                            "id": "tool-call-1",
                        }
                    ]
                )
            ]
        }

        result = tool_node(state)

        get_postgres_tools.assert_called_once_with()
        tool.invoke.assert_called_once_with({"query": "SELECT id FROM customers"})
        self.assertEqual(result["messages"][0].content, '{"rows": []}')
        self.assertEqual(result["messages"][0].tool_call_id, "tool-call-1")

    @patch("graph.postgres.nodes.tool_node.get_postgres_tools")
    def test_returns_tool_message_for_invalid_params_instead_of_crashing(
        self, get_postgres_tools: MagicMock
    ) -> None:
        get_postgres_tools.return_value = [execute_sql_safe]
        state = {
            "messages": [
                SimpleNamespace(
                    tool_calls=[
                        {
                            "name": "execute_sql_safe",
                            "args": {
                                "query": "SELECT id FROM customers",
                                "params": "not-json",
                            },
                            "id": "tool-call-2",
                        }
                    ]
                )
            ]
        }

        result = tool_node(state)

        self.assertIn("Argumentos inválidos", result["messages"][0].content)
        self.assertEqual(result["messages"][0].tool_call_id, "tool-call-2")


if __name__ == "__main__":
    unittest.main()
