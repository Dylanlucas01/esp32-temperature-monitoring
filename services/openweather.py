import requests
from flask import current_app

OPEN_WEATHER_URL = "https://api.openweathermap.org/data/2.5/find"

class OpenWeatherConfigError(RuntimeError):
    pass

def get_openweather_api_key():
    api_key = current_app.config.get("OPENWEATHER_API_KEY")
    if not api_key:
        raise OpenWeatherConfigError("OPENWEATHER_API_KEY is not configured")

    return api_key

def find_current_weather(location):
    current_app.logger.info("Requesting OpenWeather current weather location=%s", location)
    response = requests.get(
        OPEN_WEATHER_URL,
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
        current_app.logger.info("OpenWeather returned no matches location=%s", location)
        return None

    main = results[0].get("main", {})
    current_app.logger.info(
        "OpenWeather returned matches location=%s count=%s temperature=%s humidity=%s",
        location,
        len(results),
        main.get("temp"),
        main.get("humidity"),
    )
    return {
        "temp_f": main.get("temp"),
        "humidity": main.get("humidity"),
    }
