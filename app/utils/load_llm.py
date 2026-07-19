import os

from langchain.chat_models import BaseChatModel, init_chat_model

from app.utils.context_window import get_context_window


def load_llm(model: str | None = None) -> BaseChatModel:
    """Carrega o modelo de linguagem configurado.

    Args:
        model: Nome do modelo de linguagem. Quando omitido, usa o valor da
            variável de ambiente ``LLM_MODEL_DEFAULT``.

    Returns:
        Uma instância de ``ChatOpenAI`` pronta para processar mensagens.
    """

    if model is None:
        model = os.environ.get("LLM_MODEL_DEFAULT")

    if model is None or not model.strip():
        raise ValueError(
            "A variável de ambiente LLM_MODEL_DEFAULT não está definida e"
            " nenhum modelo foi informado."
        )

    base_url = os.environ.get("LLM_BASE_URL")
    if base_url is None or not base_url.strip():
        raise ValueError("A variável de ambiente LLM_BASE_URL não está definida.")

    api_key = os.environ.get("LLM_API_KEY")
    if api_key is None or not api_key.strip():
        raise ValueError("A variável de ambiente LLM_API_KEY não está definida.")

    temperature_value = os.environ.get("LLM_TEMPERATURE", "0.7")

    if temperature_value is None or not temperature_value.strip():
        raise ValueError("A variável de ambiente LLM_TEMPERATURE não pode estar vazia.")

    try:
        temperature = float(temperature_value)
    except ValueError as error:
        raise ValueError(
            "A variável de ambiente LLM_TEMPERATURE deve ser um número válido."
        ) from error

    context_window = get_context_window()
    model_options = {}
    if model.partition(":")[0].casefold() == "ollama":
        model_options = {
            "num_ctx": context_window.total_tokens,
            "num_predict": context_window.response_tokens,
        }

    try:
        return init_chat_model(
            model=model,
            base_url=base_url,
            api_key=api_key,
            temperature=temperature,
            **model_options,
        )
    except Exception as error:
        print(f"Erro ao carregar o modelo de linguagem: {error}")
        raise ConnectionError(
            "Não foi possível conectar ao modelo de linguagem."
        ) from error
