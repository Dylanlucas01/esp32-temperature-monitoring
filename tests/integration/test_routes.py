from datetime import datetime, timedelta, timezone

import requests

from extensions import db
from models import Location, Reading
from services.openweather import OpenWeatherConfigError


def add_location(nickname="Home", location="Redwood City", is_active=True):
    if is_active:
        Location.query.update({Location.is_active: False})
    location_row = Location(nickname=nickname, location=location, is_active=is_active)
    db.session.add(location_row)
    db.session.commit()
    return location_row


def add_reading(
    location=None,
    recorded_at=None,
    inside_temperature=72.0,
    inside_humidity=44.0,
    outside_temperature=65.0,
    outside_humidity=70.0,
):
    location_row = location or Location.query.filter_by(is_active=True).first() or add_location()
    reading = Reading(
        location=location_row,
        recorded_at=recorded_at or datetime.now(timezone.utc),
        inside_temperature=inside_temperature,
        inside_humidity=inside_humidity,
        outside_temperature=outside_temperature,
        outside_humidity=outside_humidity,
    )
    db.session.add(reading)
    db.session.commit()
    return reading


def test_health_check(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_weather_history_page(client):
    response = client.get("/weather-history")

    assert response.status_code == 200
    assert b"Sensor Readings" in response.data


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
    assert response.get_json() == {
        "nickname": "Home",
        "location": "Redwood City",
        "outside_temperature": 68.5,
        "outside_humidity": 62,
    }


def test_create_indoor_reading_uses_active_location(client, monkeypatch):
    monkeypatch.setattr(
        "services.reading_service.find_current_weather",
        lambda location: {"temp_f": 68.5, "humidity": 62},
    )

    response = client.post("/api/indoor", json={"temperature": 72.4, "humidity": 45.8})

    assert response.status_code == 201
    data = response.get_json()
    assert data["nickname"] == "Home"
    assert data["location"] == "Redwood City"


def test_create_indoor_reading_reuses_cached_weather(app, client, monkeypatch):
    requested_locations = []

    def fake_current_weather(location):
        requested_locations.append(location)
        return {"temp_f": 68.5, "humidity": 62}

    monkeypatch.setattr("services.reading_service.find_current_weather", fake_current_weather)

    first_response = client.post("/api/indoor", json={"temperature": 72.4, "humidity": 45.8})
    second_response = client.post("/api/indoor", json={"temperature": 72.6, "humidity": 46.0})

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    assert requested_locations == ["Redwood City"]
    with app.app_context():
        assert Reading.query.count() == 2


def test_create_indoor_reading_handles_unknown_weather_location(client, monkeypatch):
    monkeypatch.setattr("services.reading_service.find_current_weather", lambda location: None)

    response = client.post(
        "/api/indoor",
        json={"location": "Nowhere", "temperature": 72.4, "humidity": 45.8},
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "Could not find weather for the active location"}


def test_locations_can_be_created_and_activated(client):
    response = client.post(
        "/api/locations",
        json={"nickname": "Workshop", "location": "San Francisco"},
    )

    assert response.status_code == 201
    created = response.get_json()
    assert created["nickname"] == "Workshop"
    assert created["location"] == "San Francisco"
    assert created["is_active"] is True

    response = client.get("/api/locations")

    assert response.status_code == 200
    data = response.get_json()
    assert data["active_location"]["nickname"] == "Workshop"
    assert [location["nickname"] for location in data["locations"]] == ["Exploring", "Home", "Roaming", "Workshop"]


def test_activating_location_returns_current_outdoor_weather(client, monkeypatch):
    requested_locations = []

    def fake_current_weather(location):
        requested_locations.append(location)
        return {"temp_f": 71.5, "humidity": 54}

    monkeypatch.setattr("services.reading_service.find_current_weather", fake_current_weather)
    locations_response = client.get("/api/locations")
    roaming = next(
        location
        for location in locations_response.get_json()["locations"]
        if location["nickname"] == "Roaming"
    )

    response = client.put("/api/locations/active", json={"location_id": roaming["id"]})

    assert response.status_code == 200
    data = response.get_json()
    assert data["nickname"] == "Roaming"
    assert data["location"] == "San Diego"
    assert data["outdoor_current"] == {
        "location": "San Diego",
        "temperature": 71.5,
        "humidity": 54,
    }
    assert requested_locations == ["San Diego"]


def test_built_in_locations_are_created_and_protected(client):
    response = client.get("/api/locations")

    assert response.status_code == 200
    data = response.get_json()
    assert data["active_location"]["nickname"] == "Home"
    assert [
        (location["nickname"], location["location"], location["is_protected"])
        for location in data["locations"]
    ] == [
        ("Exploring", "Redwood City", True),
        ("Home", "Redwood City", True),
        ("Roaming", "San Diego", True),
    ]


def test_locations_can_be_deleted(app, client):
    client.get("/api/locations")
    with app.app_context():
        workshop = add_location(nickname="Workshop", location="San Francisco", is_active=True)
        workshop_id = workshop.id
        add_reading(location=workshop)

    response = client.delete(f"/api/locations/{workshop_id}")

    assert response.status_code == 200
    data = response.get_json()
    assert data["active_location"]["nickname"] == "Exploring"
    assert [location["nickname"] for location in data["locations"]] == ["Exploring", "Home", "Roaming"]
    with app.app_context():
        assert Location.query.filter_by(nickname="Workshop").first() is None
        assert Reading.query.filter_by(location_id=workshop_id).count() == 0


def test_built_in_locations_cannot_be_deleted(app, client):
    client.get("/api/locations")
    with app.app_context():
        home_id = Location.query.filter_by(nickname="Home").first().id
        roaming_id = Location.query.filter_by(nickname="Roaming").first().id
        exploring_id = Location.query.filter_by(nickname="Exploring").first().id

    response = client.delete(f"/api/locations/{home_id}")

    assert response.status_code == 400
    assert response.get_json() == {"error": "built-in spots cannot be deleted"}

    response = client.delete(f"/api/locations/{roaming_id}")

    assert response.status_code == 400
    assert response.get_json() == {"error": "built-in spots cannot be deleted"}

    response = client.delete(f"/api/locations/{exploring_id}")

    assert response.status_code == 400
    assert response.get_json() == {"error": "built-in spots cannot be deleted"}
    with app.app_context():
        assert Location.query.count() == 3


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
        older_location = add_location(nickname="Older", location="Palo Alto")
        newer_location = add_location(nickname="Newer", location="Redwood City")
        add_reading(location=older_location, recorded_at=older)
        add_reading(location=newer_location, recorded_at=newer, inside_temperature=73.0)

    response = client.get("/api/readings/latest")

    assert response.status_code == 200
    data = response.get_json()
    assert data["active_location"]["nickname"] == "Newer"
    assert data["reading"]["inside_temperature"] == 73.0


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
        first_location = add_location(nickname="First", location="Palo Alto")
        second_location = add_location(nickname="Second", location="Redwood City")
        add_reading(location=first_location, inside_temperature=70.0)
        add_reading(location=second_location, inside_temperature=75.0)

    response = client.get(
        "/api/readings?page=-10&per_page=999&sort_by=inside_temperature&sort_dir=desc"
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["page"] == 1
    assert data["per_page"] == 100
    assert data["total"] == 2
    assert [reading["location_nickname"] for reading in data["readings"]] == ["Second", "First"]


def test_paginated_readings_filters_by_location(app, client):
    with app.app_context():
        first_location = add_location(nickname="First", location="Palo Alto")
        second_location = add_location(nickname="Second", location="Redwood City")
        add_reading(location=first_location, inside_temperature=70.0)
        add_reading(location=second_location, inside_temperature=75.0)
        second_location_id = second_location.id

    response = client.get(f"/api/readings?location_id={second_location_id}")

    assert response.status_code == 200
    data = response.get_json()
    assert data["location_id"] == second_location_id
    assert data["total"] == 1
    assert data["readings"][0]["location_nickname"] == "Second"


def test_paginated_readings_rejects_invalid_location_id(client):
    response = client.get("/api/readings?location_id=soon")

    assert response.status_code == 400
    assert response.get_json() == {"error": "location_id must be a number"}


def test_paginated_readings_rejects_invalid_sort(client):
    response = client.get("/api/readings?sort_by=location")

    assert response.status_code == 400
    assert response.get_json() == {"error": "sort_by is not supported"}
