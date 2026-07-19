import os
import unittest
from unittest.mock import MagicMock, patch

from app.utils.load_embedding_model import load_embedding_model


class LoadEmbeddingModelTests(unittest.TestCase):
    @patch("app.utils.load_embedding_model.OllamaEmbeddings")
    def test_uses_ollama_by_default(self, ollama_embeddings: MagicMock) -> None:
        with patch.dict(
            os.environ,
            {
                "EMBEDDING_MODEL_DEFAULT": "qwen3-embedding:4b",
                "EMBEDDING_BASE_URL": "http://localhost:11434",
            },
            clear=True,
        ):
            embedding_model = load_embedding_model()

        self.assertIs(embedding_model, ollama_embeddings.return_value)
        ollama_embeddings.assert_called_once_with(
            model="qwen3-embedding:4b",
            base_url="http://localhost:11434",
        )

    @patch("app.utils.load_embedding_model.OpenAIEmbeddings")
    def test_uses_openai_when_selected(self, openai_embeddings: MagicMock) -> None:
        with patch.dict(
            os.environ,
            {
                "EMBEDDING_PROVIDER": "openai",
                "EMBEDDING_MODEL_DEFAULT": "text-embedding-3-small",
                "OPENAI_API_KEY": "test-key",
            },
            clear=True,
        ):
            embedding_model = load_embedding_model()

        self.assertIs(embedding_model, openai_embeddings.return_value)
        openai_embeddings.assert_called_once_with(model="text-embedding-3-small")

    def test_rejects_unknown_provider(self) -> None:
        with (
            patch.dict(
                os.environ,
                {"EMBEDDING_PROVIDER": "unknown"},
                clear=True,
            ),
            self.assertRaisesRegex(ValueError, "EMBEDDING_PROVIDER"),
        ):
            load_embedding_model()


if __name__ == "__main__":
    unittest.main()
