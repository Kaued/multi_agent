from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.utils.checkpointer import get_checkpointer
from graph.states.weather_state import WeatherState
from graph.weather.nodes.llm_node import llm_call
from graph.weather.nodes.tool_node import tool_node
from graph.weather.utils.weather_decision import weather_decision


def weather_graph(
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph[WeatherState, None, WeatherState, WeatherState]:
    weather_agent = StateGraph(WeatherState)

    weather_agent.add_node("llm_node", llm_call)
    weather_agent.add_node("tool_node", tool_node)

    weather_agent.add_edge(START, "llm_node")
    weather_agent.add_conditional_edges(
        "llm_node", weather_decision, ["tool_node", END]
    )

    weather_agent.add_edge("tool_node", "llm_node")

    return weather_agent.compile(
        checkpointer=checkpointer if checkpointer is not None else get_checkpointer()
    )
