import os
import unittest
from unittest.mock import MagicMock, patch

from app.utils.load_llm import load_llm


class LoadLLMContextTests(unittest.TestCase):
    @patch("app.utils.load_llm.init_chat_model")
    def test_configures_ollama_context_and_response_size(
        self, init_chat_model: MagicMock
    ) -> None:
        with patch.dict(
            os.environ,
            {
                "LLM_BASE_URL": "http://localhost:11434",
                "LLM_API_KEY": "test",
                "LLM_CONTEXT_WINDOW": "8192",
                "LLM_RESPONSE_TOKEN_RESERVE": "1024",
            },
        ):
            model = load_llm("ollama:qwen")

        self.assertIs(model, init_chat_model.return_value)
        init_chat_model.assert_called_once_with(
            model="ollama:qwen",
            base_url="http://localhost:11434",
            api_key="test",
            temperature=0.7,
            num_ctx=8192,
            num_predict=1024,
        )


if __name__ == "__main__":
    unittest.main()
