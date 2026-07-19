import json
import os

import requests
from langchain_core.tools import tool


@tool
def weather_api_request(lat: float, lon: float) -> str:
    """Get the current weather for a location using geographic coordinates.

    Args:
        lat: Latitude of the location, in decimal degrees.
        lon: Longitude of the location, in decimal degrees.
    Return:
        weather_data: str. Current weather data in JSON format, including the
            weather condition, temperature in Celsius, feels-like temperature,
            humidity, pressure, visibility, wind, clouds, and location details.
    """
    api_url = "https://api.openweathermap.org/data/2.5/weather"
    api_key = os.getenv("OPENWEATHER_API_KEY")

    if api_key is None or not api_key.strip():
        raise ValueError(
            "The OPENWEATHER_API_KEY environment variable is not set."
        )

    params = {"lat": lat, "lon": lon, "appid": api_key, "units": "metric"}

    try:
        response = requests.get(api_url, params=params)
        if response.status_code != 200:
            return (
                f"API request failed: {response.status_code} - {response.text}"
            )

        data = response.json()

        if not data:
            return (
                f"No weather data found for latitude {lat} and longitude {lon}."
            )
        
        return json.dumps(data, indent=4)
    except requests.exceptions.RequestException as e:
        print(f"An error occurred while making the API request: {e}")
        return "The API request failed. Please try again later."
