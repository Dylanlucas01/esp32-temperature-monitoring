import requests
from flask import Blueprint, current_app, jsonify, request

from services.openweather import OpenWeatherConfigError
from services.reading_service import (
    DEFAULT_LOCATION_NAME,
    create_reading,
    fetch_current_weather_for_location,
    get_latest_reading_data,
    get_paginated_reading_data,
    get_reading_history_data,
    serialize_reading,
)

sensor_data_bp = Blueprint("sensor_data", __name__)

@sensor_data_bp.get("/api/outdoor/current")
def get_outdoor_current():
    location = request.args.get("location", DEFAULT_LOCATION_NAME)
    current_app.logger.info("Fetching outdoor weather location=%s", location)

    try:
        normalized_location, current_weather = fetch_current_weather_for_location(location)
    except OpenWeatherConfigError as error:
        return weather_config_error_response(error)
    except requests.RequestException as error:
        return weather_fetch_error_response(error)

    if not normalized_location:
        current_app.logger.info("Outdoor weather location not found location=%s", location)
        return jsonify({"error": f"Could not find weather for {location}"}), 400

    current_app.logger.info(
        "Fetched outdoor weather location=%s temperature=%s humidity=%s",
        normalized_location,
        current_weather["temp_f"],
        current_weather["humidity"],
    )
    return jsonify({
        "location": normalized_location,
        "temperature": current_weather["temp_f"],
        "humidity": current_weather["humidity"],
    })

@sensor_data_bp.get("/api/readings/latest")
def get_latest_reading():
    current_app.logger.info("Fetching latest reading")
    latest_reading_data = get_latest_reading_data()
    current_app.logger.info(
        "Fetched latest reading has_reading=%s",
        latest_reading_data["reading"] is not None,
    )
    return jsonify(latest_reading_data)

@sensor_data_bp.get("/api/readings/history")
def get_reading_history():
    try:
        hours = int(request.args.get("hours", 12))
    except ValueError:
        current_app.logger.info(
            "Invalid reading history hours value=%s",
            request.args.get("hours"),
        )
        return jsonify({"error": "hours must be a number"}), 400

    current_app.logger.info("Fetching reading history requested_hours=%s", hours)
    reading_history_data = get_reading_history_data(hours)
    current_app.logger.info(
        "Fetched reading history hours=%s count=%s",
        reading_history_data["hours"],
        len(reading_history_data["readings"]),
    )
    return jsonify(reading_history_data)

@sensor_data_bp.get("/api/readings")
def get_readings():
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 10))
    except ValueError:
        current_app.logger.info(
            "Invalid readings pagination page=%s per_page=%s",
            request.args.get("page"),
            request.args.get("per_page"),
        )
        return jsonify({"error": "page and per_page must be numbers"}), 400

    sort_by = request.args.get("sort_by", "recorded_at")
    sort_dir = request.args.get("sort_dir", "desc")
    current_app.logger.info(
        "Fetching readings page=%s per_page=%s sort_by=%s sort_dir=%s",
        page,
        per_page,
        sort_by,
        sort_dir,
    )

    reading_data, error = get_paginated_reading_data(page, per_page, sort_by, sort_dir)
    if error:
        current_app.logger.info(
            "Invalid readings query page=%s per_page=%s sort_by=%s sort_dir=%s error=%s",
            page,
            per_page,
            sort_by,
            sort_dir,
            error,
        )
        return jsonify({"error": error}), 400

    current_app.logger.info(
        "Fetched readings page=%s per_page=%s total=%s returned=%s",
        reading_data["page"],
        reading_data["per_page"],
        reading_data["total"],
        len(reading_data["readings"]),
    )
    return jsonify(reading_data)

@sensor_data_bp.post("/api/indoor")
def create_weather_reading():
    data = request.get_json(silent=True) or {}
    location = data.get("location")

    if not location:
        current_app.logger.info("Rejected indoor reading missing location")
        return jsonify({"error": "location is required"}), 400

    inside_temp_f = data.get("temperature")
    inside_humidity = data.get("humidity")
    current_app.logger.info(
        "Creating indoor reading location=%s inside_temp_f=%s inside_humidity=%s",
        location,
        inside_temp_f,
        inside_humidity,
    )

    try:
        reading = create_reading(location, inside_temp_f, inside_humidity)
    except OpenWeatherConfigError as error:
        return weather_config_error_response(error)
    except requests.RequestException as error:
        return weather_fetch_error_response(error)

    if not reading:
        current_app.logger.info("Indoor reading location not found location=%s", location)
        return jsonify({"error": f"Could not find weather for {location}"}), 400

    current_app.logger.info(
        "Created indoor reading id=%s location=%s",
        reading.id,
        reading.location,
    )
    return jsonify(serialize_reading(reading)), 201

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
