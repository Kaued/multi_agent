import os

import dotenv
import pandas as pd
from langchain_core.documents import Document
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

from app.utils.load_embedding_model import load_embedding_model

dotenv.load_dotenv()


def load_csv(path: str, encoding: str = "cp1252") -> pd.DataFrame:
    """Load a CSV file into a pandas DataFrame.

    Args:
        path (str): The path to the CSV file.
        encoding (str): The character encoding used by the CSV file.

    Returns:
        pd.DataFrame: The loaded DataFrame.
    """

    df = pd.read_csv(path, encoding=encoding)
    return df


def create_document(dataframe: pd.DataFrame) -> list[Document]:
    """Create a list of documents from a DataFrame.

    Args:
        dataframe (pd.DataFrame): The DataFrame containing the data.

    Returns:
        list: A list of documents.
    """
    documents = []

    for index, row in dataframe.iterrows():
        document = Document(
            page_content=row["Questions"],
            metadata={
                "question": row["Questions"],
                "answer": row["Answers"],
                "row": index,
            },
        )
        documents.append(document)
    return documents


def ingest_vector_data() -> None:
    dataset_path = os.getenv("DATA_SET_PATH")

    if dataset_path is None or not dataset_path.strip():
        raise ValueError("A variável de ambiente DATA_SET_PATH não está definida.")

    df = load_csv(dataset_path)
    embedding_model = load_embedding_model()

    qdrant_url = os.getenv("QDRANT_URL")

    if qdrant_url is None or not qdrant_url.strip():
        raise ValueError("A variável de ambiente QDRANT_URL não está definida.")

    collection_name = os.getenv("COLLECTION_NAME")

    if collection_name is None or not collection_name.strip():
        raise ValueError("A variável de ambiente COLLECTION_NAME não está definida.")

    client = QdrantClient(url=qdrant_url)
    request = embedding_model.embed_query("test")
    vector_size = len(request)

    if client.collection_exists(collection_name):
        client.delete_collection(collection_name)

    client.recreate_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
    )

    vector_store = QdrantVectorStore(
        client=client,
        collection_name=collection_name,
        embedding=embedding_model,
    )

    documents = create_document(df)

    vector_store.add_documents(documents)

    print(f"{len(documents)} registros armazenados na coleção '{collection_name}'.")


if __name__ == "__main__":
    ingest_vector_data()
