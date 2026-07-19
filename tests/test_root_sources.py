import unittest
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.utils.sources import ensure_sources_section
from graph.root.nodes.llm_node import _extract_search_sources, llm_call


class RootSourceFormattingTests(unittest.TestCase):
    def test_uses_sources_only_from_latest_user_question(self) -> None:
        messages = [
            HumanMessage(content="Pergunta antiga"),
            ToolMessage(
                name="call_search_agent",
                tool_call_id="old-tool-call",
                content=(
                    "Resposta antiga.\n\nSources\n\n"
                    "- Fonte antiga — https://example.com/old"
                ),
            ),
            AIMessage(content="Resposta antiga concluída"),
            HumanMessage(content="Pergunta atual"),
            ToolMessage(
                name="call_search_agent",
                tool_call_id="current-tool-call",
                content=(
                    "Resposta atual.\n\nSources\n\n"
                    "- Fonte atual — https://example.com/current"
                ),
            ),
        ]

        sources = _extract_search_sources(messages)

        self.assertEqual(
            sources,
            [("Fonte atual", "https://example.com/current")],
        )

    def test_replaces_markdown_fontes_and_duplicate_sources(self) -> None:
        model_content = """A resposta baseada na pesquisa.

**Fontes:**

Cartacapital — [**https://example.com/a**](https://example.com/a)
↗
Band — [**https://example.com/b**](https://example.com/b)
↗
Sources

- Resultado duplicado — https://example.com/a"""

        result = ensure_sources_section(
            model_content,
            [
                ("Cartacapital", "https://example.com/a"),
                ("Cartacapital duplicada", "https://example.com/a"),
                ("Band", "https://example.com/b"),
            ],
        )

        self.assertNotIn("Fontes", result)
        self.assertEqual(result.count("Sources"), 1)
        self.assertEqual(result.count("https://example.com/a"), 1)
        self.assertEqual(result.count("https://example.com/b"), 1)
        self.assertTrue(result.startswith("A resposta baseada na pesquisa."))

    def test_recognizes_singular_and_inline_markdown_headings(self) -> None:
        for heading in (
            "Source:",
            "**Fonte:**",
            "### Sources",
            "_Fontes_:",
            "**Font:** primeira fonte",
        ):
            with self.subTest(heading=heading):
                result = ensure_sources_section(
                    f"Resposta principal.\n\n{heading}\nconteúdo antigo",
                    [("Fonte única", "https://example.com/source")],
                )

                self.assertEqual(result.count("https://example.com/source"), 1)
                self.assertNotIn("conteúdo antigo", result)
                self.assertTrue(result.startswith("Resposta principal."))

    @patch(
        "graph.root.nodes.llm_node.fit_messages_to_context",
        side_effect=lambda messages, _tools: messages,
    )
    @patch("graph.root.nodes.llm_node.root_agent")
    def test_root_node_returns_only_one_verified_source_section(
        self,
        root_agent: MagicMock,
        _fit_messages: MagicMock,
    ) -> None:
        root_agent.return_value.invoke.return_value = AIMessage(
            content=(
                "A resposta baseada na pesquisa.\n\n"
                "**Fontes:**\n\n"
                "Fonte formatada — [link](https://example.com/a)"
            )
        )
        state = {
            "messages": [
                HumanMessage(content="Qual é a resposta?"),
                ToolMessage(
                    name="call_search_agent",
                    tool_call_id="tool-call-1",
                    content=(
                        "Resposta pesquisada.\n\nSources\n\n"
                        "- Fonte A — https://example.com/a\n"
                        "- Fonte A duplicada — https://example.com/a\n"
                        "- Fonte B — https://example.com/b"
                    ),
                ),
            ]
        }

        result = llm_call(state)["messages"][0].content

        self.assertNotIn("Fontes", result)
        self.assertEqual(result.count("Sources"), 1)
        self.assertEqual(result.count("https://example.com/a"), 1)
        self.assertEqual(result.count("https://example.com/b"), 1)


if __name__ == "__main__":
    unittest.main()
