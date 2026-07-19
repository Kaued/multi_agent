import os

from langchain.tools import tool
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient

from app.utils.load_embedding_model import load_embedding_model


@tool
def search_vector(query: str) -> str:
    """Pesquisa informações sobre Python em um banco de dados vetorial.

    Args:
        query: A consulta usada para encontrar informações relevantes sobre Python.
    Returns:
        result: Os resultados mais relevantes encontrados no banco de dados vetorial.
    """
    
    qdrant_url = os.getenv("QDRANT_URL")

    if qdrant_url is None or not qdrant_url.strip():
        return "The QDRANT_URL environment variable is not set."
    
    collection_name = os.getenv("COLLECTION_NAME")

    if collection_name is None or not collection_name.strip():
        return "The COLLECTION_NAME environment variable is not set."
    
    client = QdrantClient(url=qdrant_url)

    embedding_model = load_embedding_model()

    qdrant_vector_store = QdrantVectorStore(
        client=client,
        collection_name=collection_name,
        embedding=embedding_model,
    )

    results = qdrant_vector_store.similarity_search(query, k=2)

    result_strings = [
        f"Question: {result.metadata.get('question')}, "
        f"Answer: {result.metadata.get('answer')}, "
        f"Row: {result.metadata.get('row')}"
        for result in results
    ]

    return "Search results:\n" + "\n".join(result_strings)
    
