import os
import unittest
from unittest.mock import patch

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.messages.utils import count_tokens_approximately

from app.utils.context_window import fit_messages_to_context, get_context_window


class ContextWindowTests(unittest.TestCase):
    def test_reads_context_and_response_reserve_from_environment(self) -> None:
        with patch.dict(
            os.environ,
            {
                "LLM_CONTEXT_WINDOW": "1200",
                "LLM_RESPONSE_TOKEN_RESERVE": "200",
            },
        ):
            context = get_context_window()

        self.assertEqual(context.total_tokens, 1200)
        self.assertEqual(context.response_tokens, 200)
        self.assertEqual(context.input_tokens, 1000)

    def test_drops_old_turns_but_keeps_system_and_latest_request(self) -> None:
        latest_request = HumanMessage(content="latest request")
        messages = [
            SystemMessage(content="system instruction"),
            HumanMessage(content="old request " * 300),
            AIMessage(content="old answer " * 300),
            latest_request,
        ]
        with patch.dict(
            os.environ,
            {
                "LLM_CONTEXT_WINDOW": "300",
                "LLM_RESPONSE_TOKEN_RESERVE": "100",
            },
        ):
            fitted = fit_messages_to_context(messages)

        self.assertIsInstance(fitted[0], SystemMessage)
        self.assertIn(latest_request, fitted)
        self.assertNotIn(messages[1], fitted)

    def test_compacts_large_tool_result_without_breaking_tool_pair(self) -> None:
        tool_call = AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "search_web",
                    "args": {"query": "fact"},
                    "id": "tool-call-1",
                    "type": "tool_call",
                }
            ],
        )
        tool_result = ToolMessage(
            content="important evidence " * 500,
            tool_call_id="tool-call-1",
            name="search_web",
        )
        messages = [
            SystemMessage(content="system instruction"),
            HumanMessage(content="find the latest fact"),
            tool_call,
            tool_result,
        ]
        with patch.dict(
            os.environ,
            {
                "LLM_CONTEXT_WINDOW": "500",
                "LLM_RESPONSE_TOKEN_RESERVE": "100",
            },
        ):
            fitted = fit_messages_to_context(messages)

        fitted_ai = next(
            message for message in fitted if isinstance(message, AIMessage)
        )
        fitted_tool = next(
            message for message in fitted if isinstance(message, ToolMessage)
        )
        self.assertEqual(fitted_ai.tool_calls[0]["id"], fitted_tool.tool_call_id)
        self.assertLess(len(fitted_tool.content), len(tool_result.content))
        self.assertLessEqual(
            count_tokens_approximately(fitted, chars_per_token=3.0),
            400,
        )

    def test_rejects_reserve_that_consumes_entire_window(self) -> None:
        with (
            patch.dict(
                os.environ,
                {
                    "LLM_CONTEXT_WINDOW": "100",
                    "LLM_RESPONSE_TOKEN_RESERVE": "100",
                },
            ),
            self.assertRaises(ValueError),
        ):
            get_context_window()


if __name__ == "__main__":
    unittest.main()
