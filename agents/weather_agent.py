import os

from app.utils.load_llm import load_llm
from tools.weather.weather_tools import get_weather_tools


def weather_agent():
    model = os.getenv("WEATHER_AGENT_MODEL")

    llm = load_llm(model)

    tools = get_weather_tools()

    llm_with_tools = llm.bind_tools(tools)

    return llm_with_tools
