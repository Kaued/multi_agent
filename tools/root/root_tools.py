from tools.root.call_postgre_agent import call_postgres_agent
from tools.root.call_search_agent import call_search_agent
from tools.root.call_vector_db_agent import call_vector_db_agent
from tools.root.call_weather_agent import call_weather_agent


def get_root_tools():
    """Return every specialized-agent delegation tool available to the root."""
    return [
        call_postgres_agent,
        call_weather_agent,
        call_vector_db_agent,
        call_search_agent,
    ]
