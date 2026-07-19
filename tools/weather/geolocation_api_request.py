import os

import requests
from langchain_core.tools import tool


@tool
def convert_address_to_coordinates(address: str):
    """Search for geographic coordinates matching a city or location.

    Args:
        address: City or location to search for. It may include the state and
            ISO 3166 country code, separated by commas.
    Return:
        locations: str. Up to five matching locations containing name, state,
            country, latitude, and longitude. Choose the result that best fits
            the requested city.
    """
    api_url = "http://api.openweathermap.org/geo/1.0/direct"

    api_key = os.getenv("OPENWEATHER_API_KEY")

    if api_key is None or not api_key.strip():
        raise ValueError(
            "The OPENWEATHER_API_KEY environment variable is not set."
        )

    params = {"q": address, "limit": 5, "appid": api_key}

    try:
        response = requests.get(api_url, params=params)

        if response.status_code != 200:
            return (
                f"API request failed: {response.status_code} - {response.text}"
            )

        data = response.json()

        if not data:
            return f"No locations found for: {address}"

        locations_string = "\n".join(
            [
                f"Name: {location.get('name')}, "
                f"State: {location.get('state')}, "
                f"Country: {location.get('country')}, "
                f"Latitude: {location.get('lat')}, Longitude: {location.get('lon')}"
                for location in data
            ]
        )

        return f"Locations found for '{address}':\n{locations_string}"

    except requests.exceptions.RequestException as e:
        print(f"An error occurred while making the API request: {e}")
        return "The API request failed. Please try again later."
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return "An unexpected error occurred. Please try again later."
    
    
