from datetime import datetime, timedelta, timezone

import requests

from extensions import db
from models import Reading
from services.openweather import OpenWeatherConfigError


def add_reading(
    location="Redwood City",
    recorded_at=None,
    inside_temp_f=72.0,
    inside_humidity=44.0,
    outside_temp_f=65.0,
    outside_humidity=70.0,
):
    reading = Reading(
        location=location,
        recorded_at=recorded_at or datetime.now(timezone.utc),
        inside_temp_f=inside_temp_f,
        inside_humidity=inside_humidity,
        outside_temp_f=outside_temp_f,
        outside_humidity=outside_humidity,
    )
    db.session.add(reading)
    db.session.commit()
    return reading


def test_health_check(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_create_indoor_reading_saves_weather_data(client, monkeypatch):
    monkeypatch.setattr(
        "services.reading_service.find_current_weather",
        lambda location: {"temp_f": 68.5, "humidity": 62},
    )

    response = client.post(
        "/api/indoor",
        json={
            "location": "Redwood City",
            "temperature": 72.4,
            "humidity": 45.8,
        },
    )

    assert response.status_code == 201
    data = response.get_json()
    assert data["id"] == 1
    assert data["location"] == "Redwood City"
    assert data["inside_temp_f"] == 72.4
    assert data["inside_humidity"] == 45.8
    assert data["outside_temp_f"] == 68.5
    assert data["outside_humidity"] == 62


def test_create_indoor_reading_requires_location(client):
    response = client.post("/api/indoor", json={"temperature": 72.4, "humidity": 45.8})

    assert response.status_code == 400
    assert response.get_json() == {"error": "location is required"}


def test_create_indoor_reading_handles_unknown_weather_location(client, monkeypatch):
    monkeypatch.setattr("services.reading_service.find_current_weather", lambda location: None)

    response = client.post(
        "/api/indoor",
        json={"location": "Nowhere", "temperature": 72.4, "humidity": 45.8},
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "Could not find weather for Nowhere"}


def test_create_indoor_reading_handles_weather_config_error(client, monkeypatch):
    def raise_config_error(location):
        raise OpenWeatherConfigError("missing key")

    monkeypatch.setattr("services.reading_service.find_current_weather", raise_config_error)

    response = client.post(
        "/api/indoor",
        json={"location": "Redwood City", "temperature": 72.4, "humidity": 45.8},
    )

    assert response.status_code == 503
    assert response.get_json() == {"error": "Weather service is not configured"}


def test_outdoor_current_handles_weather_request_error(client, monkeypatch):
    def raise_request_error(location):
        raise requests.Timeout("timed out")

    monkeypatch.setattr("services.reading_service.find_current_weather", raise_request_error)

    response = client.get("/api/outdoor/current?location=Redwood%20City")

    assert response.status_code == 502
    assert response.get_json() == {"error": "Could not fetch current weather"}


def test_latest_reading_returns_most_recent(app, client):
    older = datetime.now(timezone.utc) - timedelta(hours=2)
    newer = datetime.now(timezone.utc)
    with app.app_context():
        add_reading(location="Older", recorded_at=older)
        add_reading(location="Newer", recorded_at=newer, inside_temp_f=73.0)

    response = client.get("/api/readings/latest")

    assert response.status_code == 200
    data = response.get_json()
    assert data["location"] == "Newer"
    assert data["reading"]["inside_temp_f"] == 73.0


def test_reading_history_rejects_non_numeric_hours(client):
    response = client.get("/api/readings/history?hours=soon")

    assert response.status_code == 400
    assert response.get_json() == {"error": "hours must be a number"}


def test_reading_history_clamps_hours_and_returns_matching_readings(app, client):
    now = datetime.now(timezone.utc)
    with app.app_context():
        add_reading(recorded_at=now - timedelta(hours=2))
        add_reading(recorded_at=now - timedelta(days=10))

    response = client.get("/api/readings/history?hours=999")

    assert response.status_code == 200
    data = response.get_json()
    assert data["hours"] == 168
    assert len(data["readings"]) == 1


def test_paginated_readings_sorts_and_clamps_page_size(app, client):
    with app.app_context():
        add_reading(location="First", inside_temp_f=70.0)
        add_reading(location="Second", inside_temp_f=75.0)

    response = client.get(
        "/api/readings?page=-10&per_page=999&sort_by=inside_temp_f&sort_dir=desc"
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["page"] == 1
    assert data["per_page"] == 100
    assert data["total"] == 2
    assert [reading["location"] for reading in data["readings"]] == ["Second", "First"]


def test_paginated_readings_rejects_invalid_sort(client):
    response = client.get("/api/readings?sort_by=location")

    assert response.status_code == 400
    assert response.get_json() == {"error": "sort_by is not supported"}
