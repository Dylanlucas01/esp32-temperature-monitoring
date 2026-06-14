import requests
from flask import Blueprint, jsonify, request

from extensions import db
from models import Reading
from services.openweather import geocode_location, get_current_weather


readings_bp = Blueprint("readings", __name__)


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
    geocoded_location = geocode_location(location)
    if not geocoded_location:
        return None, None

    current_weather = get_current_weather(
        geocoded_location["lat"],
        geocoded_location["lon"],
    )

    location_parts = [
        geocoded_location["name"],
        geocoded_location.get("state"),
        geocoded_location.get("country"),
    ]
    normalized_location = ", ".join(part for part in location_parts if part)

    return normalized_location, current_weather


@readings_bp.get("/api/outdoor/current")
def get_outdoor_current():
    location = request.args.get("location", "Redwood City")

    try:
        normalized_location, current_weather = fetch_current_weather_for_location(location)
    except RuntimeError as error:
        return jsonify({"error": str(error)}), 500
    except requests.RequestException as error:
        return jsonify({
            "error": "Could not fetch current weather",
            "details": str(error),
        }), 502

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
    except RuntimeError as error:
        return jsonify({"error": str(error)}), 500
    except requests.RequestException as error:
        return jsonify({
            "error": "Could not fetch current weather",
            "details": str(error),
        }), 502

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
