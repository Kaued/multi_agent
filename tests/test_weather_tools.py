import json
from unittest.mock import MagicMock

import pytest
import requests

from tools.weather import geolocation_api_request as geolocation_module
from tools.weather import weather_api_request as weather_module


@pytest.mark.parametrize(
    ("tool", "arguments"),
    [
        (weather_module.weather_api_request, {"lat": -23.55, "lon": -46.63}),
        (
            geolocation_module.convert_address_to_coordinates,
            {"address": "Sao Paulo"},
        ),
    ],
)
def test_weather_tools_require_an_api_key(monkeypatch, tool, arguments):
    monkeypatch.delenv("OPENWEATHER_API_KEY", raising=False)

    with pytest.raises(ValueError, match="OPENWEATHER_API_KEY"):
        tool.invoke(arguments)


def test_weather_api_returns_serialized_data(monkeypatch):
    monkeypatch.setenv("OPENWEATHER_API_KEY", "weather-key")
    response = MagicMock(status_code=200)
    response.json.return_value = {
        "name": "Sao Paulo",
        "main": {"temp": 21.5},
    }
    get = MagicMock(return_value=response)
    monkeypatch.setattr(weather_module.requests, "get", get)

    result = weather_module.weather_api_request.invoke(
        {"lat": -23.55, "lon": -46.63}
    )

    assert json.loads(result) == {
        "name": "Sao Paulo",
        "main": {"temp": 21.5},
    }
    get.assert_called_once_with(
        "https://api.openweathermap.org/data/2.5/weather",
        params={
            "lat": -23.55,
            "lon": -46.63,
            "appid": "weather-key",
            "units": "metric",
        },
    )


@pytest.mark.parametrize(
    ("status_code", "response_text", "expected"),
    [
        (401, "invalid key", "API request failed: 401 - invalid key"),
        (500, "server error", "API request failed: 500 - server error"),
    ],
)
def test_weather_api_reports_http_errors(
    monkeypatch, status_code, response_text, expected
):
    monkeypatch.setenv("OPENWEATHER_API_KEY", "weather-key")
    response = MagicMock(status_code=status_code, text=response_text)
    monkeypatch.setattr(
        weather_module.requests, "get", MagicMock(return_value=response)
    )

    result = weather_module.weather_api_request.invoke({"lat": 1.0, "lon": 2.0})

    assert result == expected


def test_weather_api_reports_empty_results(monkeypatch):
    monkeypatch.setenv("OPENWEATHER_API_KEY", "weather-key")
    response = MagicMock(status_code=200)
    response.json.return_value = {}
    monkeypatch.setattr(
        weather_module.requests, "get", MagicMock(return_value=response)
    )

    result = weather_module.weather_api_request.invoke({"lat": 1.0, "lon": 2.0})

    assert result == "No weather data found for latitude 1.0 and longitude 2.0."


def test_weather_api_handles_request_errors(monkeypatch):
    monkeypatch.setenv("OPENWEATHER_API_KEY", "weather-key")
    monkeypatch.setattr(
        weather_module.requests,
        "get",
        MagicMock(side_effect=requests.RequestException("connection failed")),
    )

    result = weather_module.weather_api_request.invoke({"lat": 1.0, "lon": 2.0})

    assert result == "The API request failed. Please try again later."


def test_geolocation_returns_formatted_locations(monkeypatch):
    monkeypatch.setenv("OPENWEATHER_API_KEY", "weather-key")
    response = MagicMock(status_code=200)
    response.json.return_value = [
        {
            "name": "Sao Paulo",
            "state": "SP",
            "country": "BR",
            "lat": -23.55,
            "lon": -46.63,
        },
        {
            "name": "Sao Paulo do Potengi",
            "country": "BR",
            "lat": -5.9,
            "lon": -35.76,
        },
    ]
    get = MagicMock(return_value=response)
    monkeypatch.setattr(geolocation_module.requests, "get", get)

    result = geolocation_module.convert_address_to_coordinates.invoke(
        {"address": "Sao Paulo, BR"}
    )

    assert result == (
        "Locations found for 'Sao Paulo, BR':\n"
        "Name: Sao Paulo, State: SP, Country: BR, Latitude: -23.55, "
        "Longitude: -46.63\n"
        "Name: Sao Paulo do Potengi, State: None, Country: BR, Latitude: -5.9, "
        "Longitude: -35.76"
    )
    get.assert_called_once_with(
        "http://api.openweathermap.org/geo/1.0/direct",
        params={"q": "Sao Paulo, BR", "limit": 5, "appid": "weather-key"},
    )


def test_geolocation_reports_empty_results(monkeypatch):
    monkeypatch.setenv("OPENWEATHER_API_KEY", "weather-key")
    response = MagicMock(status_code=200)
    response.json.return_value = []
    monkeypatch.setattr(
        geolocation_module.requests, "get", MagicMock(return_value=response)
    )

    result = geolocation_module.convert_address_to_coordinates.invoke(
        {"address": "Unknown place"}
    )

    assert result == "No locations found for: Unknown place"


def test_geolocation_handles_request_errors(monkeypatch):
    monkeypatch.setenv("OPENWEATHER_API_KEY", "weather-key")
    monkeypatch.setattr(
        geolocation_module.requests,
        "get",
        MagicMock(side_effect=requests.RequestException("connection failed")),
    )

    result = geolocation_module.convert_address_to_coordinates.invoke(
        {"address": "Sao Paulo"}
    )

    assert result == "The API request failed. Please try again later."
