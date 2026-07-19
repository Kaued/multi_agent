from tools.vector_db.search_vector import search_vector


def get_vector_db_tools():
    """Returns a list of vector database tools."""
    return [
        search_vector,
    ]
