import json
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from agents.weather_agent import weather_agent
from app.utils.context_window import fit_messages_to_context
from graph.prompts.weather_prompt import system_prompt
from graph.states.weather_state import WeatherState
from tools.weather.weather_tools import get_weather_tools

PORTUGUESE_PATTERN = re.compile(
    r"\b(qual|clima|tempo|temperatura|hoje|agora|graus|cidade|em)\b",
    flags=re.IGNORECASE,
)
LOCATION_PATTERN = re.compile(
    r"Name:\s*([^,\n]+),\s*State:\s*([^,\n]+),\s*Country:\s*([^,\n]+)"
)


def _uses_portuguese(messages: list) -> bool:
    """Detect Portuguese in the latest user request for the emergency fallback."""
    for message in reversed(messages):
        if isinstance(message, HumanMessage) and isinstance(message.content, str):
            return bool(PORTUGUESE_PATTERN.search(message.content))
    return False


def _requested_location(messages: list, weather_data: dict[str, Any]) -> str:
    """Prefer the selected geocoding result over the API station name."""
    for message in reversed(messages):
        if not isinstance(message, ToolMessage) or not isinstance(message.content, str):
            continue
        if message.name not in (None, "convert_address_to_coordinates"):
            continue
        match = LOCATION_PATTERN.search(message.content)
        if match:
            name, state, country = match.groups()
            return f"{name}, {state}, {country}"

    return str(weather_data.get("name") or "requested location")


def _weather_data(messages: list) -> dict[str, Any] | None:
    """Return the latest valid current-weather JSON object from tool output."""
    for message in reversed(messages):
        if not isinstance(message, ToolMessage) or not isinstance(message.content, str):
            continue
        if message.name not in (None, "weather_api_request"):
            continue
        try:
            data = json.loads(message.content)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and isinstance(data.get("main"), dict):
            return data
    return None


def _format_number(value: Any) -> str:
    if isinstance(value, int | float):
        return f"{value:g}"
    return str(value)


def _fallback_weather_response(messages: list) -> str | None:
    """Build a non-empty answer using only fields returned by the weather tool."""
    data = _weather_data(messages)
    if data is None:
        return None

    portuguese = _uses_portuguese(messages)
    location = _requested_location(messages, data)
    main = data["main"]
    weather = data.get("weather")
    condition = None
    if isinstance(weather, list) and weather and isinstance(weather[0], dict):
        condition = weather[0].get("description") or weather[0].get("main")

    title = (
        f"Clima atual — {location}" if portuguese else f"Current weather — {location}"
    )
    labels = {
        "condition": "Condição" if portuguese else "Condition",
        "temperature": "Temperatura" if portuguese else "Temperature",
        "feels_like": "Sensação térmica" if portuguese else "Feels like",
        "humidity": "Umidade" if portuguese else "Humidity",
        "pressure": "Pressão" if portuguese else "Pressure",
        "visibility": "Visibilidade" if portuguese else "Visibility",
        "wind": "Vento" if portuguese else "Wind",
        "clouds": "Nuvens" if portuguese else "Cloud coverage",
    }
    lines = [title]
    if condition is not None:
        lines.append(f"- {labels['condition']}: {condition}")
    if main.get("temp") is not None:
        lines.append(f"- {labels['temperature']}: {_format_number(main['temp'])} °C")
    if main.get("feels_like") is not None:
        lines.append(
            f"- {labels['feels_like']}: {_format_number(main['feels_like'])} °C"
        )
    if main.get("humidity") is not None:
        lines.append(f"- {labels['humidity']}: {main['humidity']}%")
    if main.get("pressure") is not None:
        lines.append(f"- {labels['pressure']}: {main['pressure']} hPa")
    if data.get("visibility") is not None:
        lines.append(f"- {labels['visibility']}: {data['visibility']} m")
    wind = data.get("wind")
    if isinstance(wind, dict) and wind.get("speed") is not None:
        lines.append(f"- {labels['wind']}: {_format_number(wind['speed'])} m/s")
    clouds = data.get("clouds")
    if isinstance(clouds, dict) and clouds.get("all") is not None:
        lines.append(f"- {labels['clouds']}: {clouds['all']}%")
    return "\n\n".join((lines[0], "\n".join(lines[1:])))


def llm_call(state: WeatherState) -> WeatherState:
    messages = list(state["messages"])
    model_llm = weather_agent()

    if not any(
        isinstance(message, SystemMessage) and message.content == system_prompt
        for message in messages
    ):
        messages.insert(0, SystemMessage(content=system_prompt))

    model_messages = fit_messages_to_context(messages, get_weather_tools())
    response = model_llm.invoke(model_messages)

    if not response.tool_calls:
        has_content = isinstance(response.content, str) and response.content.strip()
        if not has_content:
            fallback = _fallback_weather_response(messages)
            if fallback is not None:
                response = response.model_copy(update={"content": fallback})

    return {
        "messages": [response],
    }
