import requests
from flask import Blueprint, current_app, jsonify, request

from app.services.openweather import OpenWeatherConfigError
from app.services.location_service import (
    DEFAULT_LOCATION_NAME,
    create_location,
    delete_location,
    get_active_location,
    get_locations_data,
    serialize_location,
    set_active_location,
)
from app.services.reading_service import (
    create_reading,
    get_latest_reading_data,
    get_paginated_reading_data,
    get_reading_history_data,
)
from app.services.weather_service import fetch_current_weather_for_location

sensor_data_bp = Blueprint("sensor_data", __name__)

@sensor_data_bp.get("/api/outdoor/current")
def get_outdoor_current():
    active_location = get_active_location()
    location = request.args.get("location", active_location.location if active_location else DEFAULT_LOCATION_NAME)
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

@sensor_data_bp.get("/api/locations")
def get_locations():
    current_app.logger.info("Fetching locations")
    return jsonify(get_locations_data())

@sensor_data_bp.post("/api/locations")
def post_location():
    data = request.get_json(silent=True) or {}
    location, error = create_location(data.get("nickname"), data.get("location"))
    if error:
        current_app.logger.info("Rejected location create error=%s", error)
        return jsonify({"error": error}), 400

    current_app.logger.info("Created location id=%s nickname=%s", location["id"], location["nickname"])
    return jsonify(location), 201

@sensor_data_bp.delete("/api/locations/<int:location_id>")
def delete_saved_location(location_id):
    data, error, status_code = delete_location(location_id)
    if error:
        current_app.logger.info("Rejected location delete id=%s error=%s", location_id, error)
        return jsonify({"error": error}), status_code

    current_app.logger.info("Deleted location id=%s", location_id)
    return jsonify(data)

@sensor_data_bp.put("/api/locations/active")
def put_active_location():
    data = request.get_json(silent=True) or {}
    location_id = data.get("location_id")
    try:
        location_id = int(location_id)
    except (TypeError, ValueError):
        return jsonify({"error": "location_id must be a number"}), 400

    location = set_active_location(location_id)
    if not location:
        return jsonify({"error": "location was not found"}), 404

    current_app.logger.info("Activated location id=%s nickname=%s", location.id, location.nickname)
    location_data = serialize_location(location)
    location_data["outdoor_current"] = get_outdoor_current_payload(location.location)
    return jsonify(location_data)

def get_outdoor_current_payload(location):
    try:
        normalized_location, current_weather = fetch_current_weather_for_location(location)
    except OpenWeatherConfigError as error:
        current_app.logger.warning("Skipping live outdoor weather payload: %s", error)
        return None
    except requests.RequestException as error:
        current_app.logger.warning(
            "Skipping live outdoor weather payload: %s",
            error.__class__.__name__,
        )
        return None

    if not normalized_location:
        return None

    return {
        "location": normalized_location,
        "temperature": current_weather["temp_f"],
        "humidity": current_weather["humidity"],
    }

def serialize_esp32_reading_response(reading):
    return {
        "nickname": reading.location.nickname,
        "location": reading.location.location,
        "outside_temperature": reading.outside_temperature,
        "outside_humidity": reading.outside_humidity,
    }

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
    location_id = request.args.get("location_id")
    if location_id:
        try:
            location_id = int(location_id)
        except ValueError:
            current_app.logger.info("Invalid readings location_id value=%s", request.args.get("location_id"))
            return jsonify({"error": "location_id must be a number"}), 400
    else:
        location_id = None

    current_app.logger.info(
        "Fetching readings page=%s per_page=%s sort_by=%s sort_dir=%s location_id=%s",
        page,
        per_page,
        sort_by,
        sort_dir,
        location_id,
    )

    reading_data, error = get_paginated_reading_data(page, per_page, sort_by, sort_dir, location_id)
    if error:
        current_app.logger.info(
            "Invalid readings query page=%s per_page=%s sort_by=%s sort_dir=%s location_id=%s error=%s",
            page,
            per_page,
            sort_by,
            sort_dir,
            location_id,
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
    inside_temperature = data.get("temperature")
    inside_humidity = data.get("humidity")
    current_app.logger.info(
        "Creating indoor reading inside_temperature=%s inside_humidity=%s",
        inside_temperature,
        inside_humidity,
    )

    try:
        reading = create_reading(inside_temperature, inside_humidity)
    except OpenWeatherConfigError as error:
        return weather_config_error_response(error)
    except requests.RequestException as error:
        return weather_fetch_error_response(error)

    if not reading:
        current_app.logger.info("Indoor reading active location weather not found")
        return jsonify({"error": "Could not find weather for the active location"}), 400

    current_app.logger.info(
        "Created indoor reading id=%s location=%s",
        reading.id,
        reading.location.location,
    )
    return jsonify(serialize_esp32_reading_response(reading)), 201

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
