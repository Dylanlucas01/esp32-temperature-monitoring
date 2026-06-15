from datetime import datetime, timedelta, timezone

import requests
from flask import Blueprint, current_app, jsonify, request

from extensions import db
from models import Reading
from services.openweather import (
    OpenWeatherConfigError,
    find_current_weather,
)


readings_bp = Blueprint("readings", __name__)
DEFAULT_LOCATION_NAME = "Redwood City"


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


READING_COLUMNS = {
    "id": Reading.id,
    "recorded_at": Reading.recorded_at,
    "inside_temp_f": Reading.inside_temp_f,
    "inside_humidity": Reading.inside_humidity,
    "outside_temp_f": Reading.outside_temp_f,
    "outside_humidity": Reading.outside_humidity,
}


def fetch_current_weather_for_location(location):
    normalized_location = location or DEFAULT_LOCATION_NAME
    current_weather = find_current_weather(normalized_location)
    if not current_weather:
        return None, None

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
        return jsonify({"error": f"Could not find weather for {location}"}), 400

    return jsonify({
        "location": normalized_location,
        "temperature": current_weather["temp_f"],
        "humidity": current_weather["humidity"],
    })


@readings_bp.get("/api/readings/latest")
def get_latest_reading():
    ensure_schema()
    reading = Reading.query.order_by(Reading.recorded_at.desc()).first()

    if not reading:
        return jsonify({
            "location": DEFAULT_LOCATION_NAME,
            "reading": None,
        })

    return jsonify({
        "location": reading.location,
        "reading": serialize_reading(reading),
    })


@readings_bp.get("/api/readings/history")
def get_reading_history():
    ensure_schema()

    try:
        hours = int(request.args.get("hours", 12))
    except ValueError:
        return jsonify({"error": "hours must be a number"}), 400

    hours = max(1, min(hours, 168))
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    readings = (
        Reading.query
        .filter(Reading.recorded_at >= cutoff)
        .order_by(Reading.recorded_at.asc())
        .all()
    )

    return jsonify({
        "hours": hours,
        "readings": [serialize_reading(reading) for reading in readings],
    })


@readings_bp.get("/api/readings")
def get_readings():
    ensure_schema()

    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 10))
    except ValueError:
        return jsonify({"error": "page and per_page must be numbers"}), 400

    sort_by = request.args.get("sort_by", "recorded_at")
    sort_dir = request.args.get("sort_dir", "desc")

    if sort_by not in READING_COLUMNS:
        return jsonify({"error": "sort_by is not supported"}), 400

    if sort_dir not in {"asc", "desc"}:
        return jsonify({"error": "sort_dir must be asc or desc"}), 400

    per_page = max(1, min(per_page, 100))
    page = max(1, page)
    sort_column = READING_COLUMNS[sort_by]
    query = Reading.query.order_by(sort_column.desc() if sort_dir == "desc" else sort_column.asc())
    total = query.count()
    pages = max(1, (total + per_page - 1) // per_page)
    page = min(page, pages)
    readings = (
        query
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    return jsonify({
        "page": page,
        "per_page": per_page,
        "pages": pages,
        "total": total,
        "readings": [serialize_reading(reading) for reading in readings],
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
        return jsonify({"error": f"Could not find weather for {location}"}), 400

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
