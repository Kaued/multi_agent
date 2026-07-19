import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from langchain_core.messages import HumanMessage

from graph.root.nodes.tool_node import tool_node


class RootToolNodeTests(unittest.TestCase):
    @patch("graph.root.nodes.tool_node.get_root_tools")
    def test_injects_conversation_when_model_emits_empty_args(
        self, get_root_tools: MagicMock
    ) -> None:
        tool = MagicMock()
        tool.name = "call_postgres_agent"
        tool.invoke.return_value = "agent response"
        get_root_tools.return_value = [tool]
        user_message = HumanMessage(content="List customers")
        pending_call = SimpleNamespace(
            tool_calls=[
                {
                    "name": "call_postgres_agent",
                    "args": {},
                    "id": "tool-call-1",
                }
            ]
        )

        result = tool_node({"messages": [user_message, pending_call]})

        tool.invoke.assert_called_once_with({"messages": [user_message]})
        self.assertEqual(result["messages"][0].content, "agent response")
        self.assertEqual(result["messages"][0].tool_call_id, "tool-call-1")


if __name__ == "__main__":
    unittest.main()
