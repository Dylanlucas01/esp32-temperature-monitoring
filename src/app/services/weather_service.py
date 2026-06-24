from datetime import datetime, timedelta, timezone

from flask import current_app

from app.services.location_service import DEFAULT_LOCATION_NAME
from app.services.openweather import find_current_weather

WEATHER_CACHE_TTL_SECONDS = 300
_weather_cache = {}


def clear_weather_cache():
    _weather_cache.clear()


def get_weather_cache_key(location):
    return (location or DEFAULT_LOCATION_NAME).strip().lower()


def fetch_current_weather_for_location(location):
    normalized_location = location or DEFAULT_LOCATION_NAME
    cache_key = get_weather_cache_key(normalized_location)
    now = datetime.now(timezone.utc)
    cached_weather = _weather_cache.get(cache_key)
    if cached_weather and now - cached_weather["fetched_at"] < timedelta(seconds=WEATHER_CACHE_TTL_SECONDS):
        current_app.logger.info("Using cached current weather location=%s", normalized_location)
        return normalized_location, cached_weather["weather"]

    current_app.logger.info("Resolving current weather location=%s", normalized_location)
    current_weather = find_current_weather(normalized_location)
    if not current_weather:
        current_app.logger.info("No current weather found location=%s", normalized_location)
        return None, None

    _weather_cache[cache_key] = {
        "fetched_at": now,
        "weather": current_weather,
    }
    return normalized_location, current_weather
