from tools.postgres.postgres_tools import get_postgres_tools
from tools.root.root_tools import get_root_tools
from tools.search.search_tools import get_search_tools
from tools.weather.weather_tools import get_weather_tools


def test_root_tools_exposes_every_specialist():
    assert [tool.name for tool in get_root_tools()] == [
        "call_postgres_agent",
        "call_weather_agent",
        "call_vector_db_agent",
        "call_search_agent",
    ]


def test_postgres_tools_exposes_safe_sql_executor():
    assert [tool.name for tool in get_postgres_tools()] == ["execute_sql_safe"]


def test_weather_tools_exposes_weather_and_geolocation():
    assert [tool.name for tool in get_weather_tools()] == [
        "weather_api_request",
        "convert_address_to_coordinates",
    ]


def test_search_tools_exposes_web_search():
    assert [tool.name for tool in get_search_tools()] == ["search_web"]
