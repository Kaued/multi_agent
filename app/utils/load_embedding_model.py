import os

from langchain_core.embeddings import Embeddings
from langchain_ollama import OllamaEmbeddings
from langchain_openai import OpenAIEmbeddings


def load_embedding_model(model: str | None = None) -> Embeddings:
    """Carrega o modelo de embeddings configurado.

    Args:
        model: Nome do modelo de embeddings. Quando omitido, usa o valor da
            variável de ambiente ``EMBEDDING_MODEL_DEFAULT``.

    Returns:
        Uma instância de ``OllamaEmbeddings`` ou ``OpenAIEmbeddings``, conforme
        a variável de ambiente ``EMBEDDING_PROVIDER``.
    """

    provider = os.getenv("EMBEDDING_PROVIDER", "ollama").strip().lower()
    if provider not in {"ollama", "openai"}:
        raise ValueError(
            "A variável de ambiente EMBEDDING_PROVIDER deve ser 'ollama' ou 'openai'."
        )

    if model is None:
        model = os.getenv("EMBEDDING_MODEL_DEFAULT")

    if model is None or not model.strip():
        raise ValueError(
            "Nenhum modelo de embedding foi especificado e a variável de "
            "ambiente EMBEDDING_MODEL_DEFAULT não está definida."
        )

    if provider == "ollama":
        base_url = os.getenv("EMBEDDING_BASE_URL")
        if base_url is None or not base_url.strip():
            raise ValueError(
                "A variável de ambiente EMBEDDING_BASE_URL não está definida."
            )

    try:
        if provider == "openai":
            return OpenAIEmbeddings(model=model)

        return OllamaEmbeddings(model=model, base_url=base_url)
    except Exception as error:
        raise ConnectionError(
            f"Não foi possível configurar o provedor de embeddings {provider}."
        ) from error
