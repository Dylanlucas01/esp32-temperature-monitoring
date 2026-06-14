import requests
from flask import Blueprint, current_app, jsonify, request

from extensions import db
from models import Reading
from services.openweather import (
    OpenWeatherConfigError,
    get_current_weather,
)


readings_bp = Blueprint("readings", __name__)
DEFAULT_LOCATION_NAME = "Redwood City, CA, US"
DEFAULT_LAT = 37.49
DEFAULT_LON = -122.23


def ensure_schema():
    db.create_all()


def serialize_reading(reading):
    return {
        "id": reading.id,
        "recorded_at": reading.recorded_at.isoformat(),
        "location": reading.location,
        "outside_temp_f": reading.outside_temp_f,
        "outside_humidity": reading.outside_humidity,
        "inside_temp_f": reading.inside_temp_f,
        "inside_humidity": reading.inside_humidity,
    }


def fetch_current_weather_for_location(location):
    # Geocoding is intentionally bypassed; use fixed coordinates for now.
    current_weather = get_current_weather(DEFAULT_LAT, DEFAULT_LON)
    normalized_location = location or DEFAULT_LOCATION_NAME

    return normalized_location, current_weather


def weather_config_error_response(error):
    current_app.logger.error("OpenWeather configuration error: %s", error)
    return jsonify({
        "error": "Weather service is not configured",
    }), 503


def weather_fetch_error_response(error):
    current_app.logger.warning(
        "OpenWeather request failed: %s",
        error.__class__.__name__,
    )
    return jsonify({
        "error": "Could not fetch current weather",
    }), 502


@readings_bp.get("/api/outdoor/current")
def get_outdoor_current():
    location = request.args.get("location", DEFAULT_LOCATION_NAME)

    try:
        normalized_location, current_weather = fetch_current_weather_for_location(location)
    except OpenWeatherConfigError as error:
        return weather_config_error_response(error)
    except requests.RequestException as error:
        return weather_fetch_error_response(error)

    if not normalized_location:
        return jsonify({"error": f"Could not find coordinates for {location}"}), 400

    return jsonify({
        "location": normalized_location,
        "temperature": current_weather["temp_f"],
        "humidity": current_weather["humidity"],
    })


def create_reading_response():
    data = request.get_json(silent=True) or {}
    location = data.get("location")

    if not location:
        return jsonify({"error": "location is required"}), 400

    inside_temp_f = data.get("temperature")
    inside_humidity = data.get("humidity")

    try:
        normalized_location, current_weather = fetch_current_weather_for_location(location)
    except OpenWeatherConfigError as error:
        return weather_config_error_response(error)
    except requests.RequestException as error:
        return weather_fetch_error_response(error)

    if not normalized_location:
        return jsonify({"error": f"Could not find coordinates for {location}"}), 400

    reading = Reading(
        location=normalized_location,
        outside_temp_f=current_weather["temp_f"],
        outside_humidity=current_weather["humidity"],
        inside_temp_f=inside_temp_f,
        inside_humidity=inside_humidity,
    )

    ensure_schema()
    db.session.add(reading)
    db.session.commit()

    return jsonify(serialize_reading(reading)), 201


@readings_bp.post("/api/indoor")
def create_indoor_reading():
    return create_reading_response()


@readings_bp.post("/api/readings")
def create_reading():
    return create_reading_response()
