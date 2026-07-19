from tools.weather.geolocation_api_request import convert_address_to_coordinates
from tools.weather.weather_api_request import weather_api_request


def get_weather_tools():
    """Returns a list of weather tools."""
    return [
        weather_api_request,
        convert_address_to_coordinates,
    ]