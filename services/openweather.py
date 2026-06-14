import requests
from flask import current_app


GEOCODING_URL = "https://api.openweathermap.org/geo/1.0/direct"
CURRENT_URL = "https://api.openweathermap.org/data/2.5/weather"


def get_openweather_api_key():
    api_key = current_app.config.get("OPENWEATHER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENWEATHER_API_KEY is not configured")

    return api_key


def geocode_location(location):
    response = requests.get(
        GEOCODING_URL,
        params={
            "q": f"{location},CA,US",
            "limit": 1,
            "appid": get_openweather_api_key(),
        },
        timeout=10,
    )
    response.raise_for_status()

    matches = response.json()
    if not matches:
        return None

    match = matches[0]
    return {
        "name": match.get("name", location),
        "state": match.get("state"),
        "country": match.get("country"),
        "lat": match["lat"],
        "lon": match["lon"],
    }


def get_current_weather(lat, lon):
    response = requests.get(
        CURRENT_URL,
        params={
            "lat": lat,
            "lon": lon,
            "appid": get_openweather_api_key(),
            "units": "imperial",
        },
        timeout=10,
    )
    response.raise_for_status()

    weather = response.json()
    main = weather.get("main", {})

    return {
        "temp_f": main.get("temp"),
        "humidity": main.get("humidity"),
    }
