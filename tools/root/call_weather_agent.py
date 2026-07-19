from typing import Annotated

from langchain_core.messages import AnyMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

from graph.prompts.weather_prompt import system_prompt
from graph.weather.weather_grapy import weather_graph
from tools.root.delegation import invoke_specialist


@tool
def call_weather_agent(
    messages: Annotated[list[AnyMessage], InjectedState("messages")],
    config: RunnableConfig = None,
) -> str:
    """Delegate a current-weather request to the weather agent.

    Use this agent when the user asks for the current weather at a specific
    location. It resolves place names to coordinates and retrieves live weather
    conditions. It does not handle forecasts, historical weather, or unrelated
    subjects.

    Returns:
        The weather agent's final response.
    """
    graph = weather_graph()
    result = invoke_specialist(messages, graph, system_prompt, "weather", config)
    return str(result["messages"][-1].content)
