import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from graph.search.nodes.llm_node import SEARCH_RESULT_INSTRUCTION, llm_call
from graph.search.nodes.tool_node import tool_node

SEARCH_RESULT = """Search results:

Title: Example report
URL: https://example.com/report
Content: The report confirms the requested fact happened in July 2026.

Source URLs returned by the search tool:
- Example report — https://example.com/report"""


class SearchToolNodeTests(unittest.TestCase):
    @patch("graph.search.nodes.tool_node.get_search_tools")
    def test_identifies_search_tool_in_tool_message(
        self, get_search_tools: MagicMock
    ) -> None:
        tool = MagicMock()
        tool.name = "search_web"
        tool.invoke.return_value = SEARCH_RESULT
        get_search_tools.return_value = [tool]
        state = {
            "messages": [
                SimpleNamespace(
                    tool_calls=[
                        {
                            "name": "search_web",
                            "args": {"query": "requested fact"},
                            "id": "tool-call-1",
                        }
                    ]
                )
            ]
        }

        result = tool_node(state)

        self.assertEqual(result["messages"][0].name, "search_web")
        self.assertEqual(result["messages"][0].content, SEARCH_RESULT)


class SearchLLMNodeTests(unittest.TestCase):
    @patch("graph.search.nodes.llm_node.search_agent")
    def test_falls_back_to_real_tool_result_when_model_ignores_it(
        self, search_agent: MagicMock
    ) -> None:
        model = search_agent.return_value
        model.invoke.return_value = AIMessage(
            content="Não tenho acesso aos resultados da pesquisa."
        )
        state = {
            "messages": [
                HumanMessage(content="Pesquise sobre o fato solicitado"),
                ToolMessage(
                    content=SEARCH_RESULT,
                    tool_call_id="tool-call-1",
                    name="search_web",
                ),
            ]
        }

        result = llm_call(state)

        content = result["messages"][0].content
        self.assertIn("The report confirms", content)
        self.assertNotIn("Não tenho acesso", content)
        self.assertTrue(
            content.endswith("- Example report — https://example.com/report")
        )
        invoked_messages = model.invoke.call_args.args[0]
        self.assertTrue(
            any(
                isinstance(message, SystemMessage)
                and SEARCH_RESULT_INSTRUCTION in message.content
                for message in invoked_messages
            )
        )

    @patch("graph.search.nodes.llm_node.search_agent")
    def test_keeps_grounded_answer_and_appends_verified_source(
        self, search_agent: MagicMock
    ) -> None:
        model = search_agent.return_value
        model.invoke.return_value = AIMessage(
            content="O relatório confirma que o fato ocorreu em julho de 2026."
        )
        state = {
            "messages": [
                HumanMessage(content="Quando ocorreu o fato?"),
                ToolMessage(
                    content=SEARCH_RESULT,
                    tool_call_id="tool-call-1",
                    name="search_web",
                ),
            ]
        }

        result = llm_call(state)

        content = result["messages"][0].content
        self.assertIn("julho de 2026", content)
        self.assertTrue(
            content.endswith("- Example report — https://example.com/report")
        )


if __name__ == "__main__":
    unittest.main()
