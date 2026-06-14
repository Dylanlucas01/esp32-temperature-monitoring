import requests
from flask import Blueprint, jsonify, request

from extensions import db
from models import Reading
from services.openweather import geocode_location, get_current_weather


readings_bp = Blueprint("readings", __name__)


@readings_bp.post("/api/readings")
def create_reading():
    data = request.get_json(silent=True) or {}
    location = data.get("location")

    if not location:
        return jsonify({"error": "location is required"}), 400

    inside_temp_f = data.get("temperature")
    inside_humidity = data.get("humidity")

    try:
        geocoded_location = geocode_location(location)
        if not geocoded_location:
            return jsonify({"error": f"Could not find coordinates for {location}"}), 400

        current_weather = get_current_weather(
            geocoded_location["lat"],
            geocoded_location["lon"],
        )
    except RuntimeError as error:
        return jsonify({"error": str(error)}), 500
    except requests.RequestException as error:
        return jsonify({
            "error": "Could not fetch current weather",
            "details": str(error),
        }), 502

    location_parts = [
        geocoded_location["name"],
        geocoded_location.get("state"),
        geocoded_location.get("country"),
    ]
    normalized_location = ", ".join(part for part in location_parts if part)

    reading = Reading(
        location=normalized_location,
        outside_temp_f=current_weather["temp_f"],
        outside_humidity=current_weather["humidity"],
        inside_temp_f=inside_temp_f,
        inside_humidity=inside_humidity,
    )

    db.session.add(reading)
    db.session.commit()

    return jsonify({
        "id": reading.id,
        "recorded_at": reading.recorded_at.isoformat(),
        "location": reading.location,
        "outside_temp_f": reading.outside_temp_f,
        "outside_humidity": reading.outside_humidity,
        "inside_temp_f": reading.inside_temp_f,
        "inside_humidity": reading.inside_humidity,
    }), 201
