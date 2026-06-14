import requests
from flask import current_app


FIND_URL = "https://api.openweathermap.org/data/2.5/find"


class OpenWeatherConfigError(RuntimeError):
    pass


def get_openweather_api_key():
    api_key = current_app.config.get("OPENWEATHER_API_KEY")
    if not api_key:
        raise OpenWeatherConfigError("OPENWEATHER_API_KEY is not configured")

    return api_key


def find_current_weather(location):
    response = requests.get(
        FIND_URL,
        params={
            "q": location,
            "units": "imperial",
            "type": "accurate",
            "appid": get_openweather_api_key(),
        },
        timeout=10,
    )
    response.raise_for_status()

    results = response.json().get("list", [])
    if not results:
        return None

    main = results[0].get("main", {})
    return {
        "temp_f": main.get("temp"),
        "humidity": main.get("humidity"),
    }
