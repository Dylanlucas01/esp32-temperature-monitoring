from datetime import datetime, timedelta, timezone

from flask import current_app
from sqlalchemy.exc import SQLAlchemyError

from extensions import db
from models import Location, Reading
from services.openweather import find_current_weather

DEFAULT_LOCATION_NAME = "Redwood City"
DEFAULT_LOCATION_NICKNAME = "Home"
BUILT_IN_LOCATIONS = (
    {"nickname": DEFAULT_LOCATION_NICKNAME, "location": DEFAULT_LOCATION_NAME, "is_active": True},
    {"nickname": "Roaming", "location": "San Diego", "is_active": False},
    {"nickname": "Exploring", "location": "Redwood City", "is_active": False},
)
PROTECTED_LOCATION_NICKNAMES = {location["nickname"] for location in BUILT_IN_LOCATIONS}

READING_COLUMNS = {
    "id": Reading.id,
    "recorded_at": Reading.recorded_at,
    "inside_temperature": Reading.inside_temperature,
    "inside_humidity": Reading.inside_humidity,
    "outside_temperature": Reading.outside_temperature,
    "outside_humidity": Reading.outside_humidity,
}

def ensure_schema():
    current_app.logger.debug("Ensuring database schema")
    db.create_all()
    ensure_default_location()

def ensure_default_location():
    changed = False
    has_active_location = Location.query.filter_by(is_active=True).first() is not None

    for built_in_location in BUILT_IN_LOCATIONS:
        location = Location.query.filter_by(nickname=built_in_location["nickname"]).first()
        if location:
            if location.location != built_in_location["location"]:
                location.location = built_in_location["location"]
                changed = True
            if built_in_location["is_active"] and not has_active_location:
                location.is_active = True
                has_active_location = True
                changed = True
            continue

        current_app.logger.info(
            "Creating built-in location nickname=%s location=%s",
            built_in_location["nickname"],
            built_in_location["location"],
        )
        db.session.add(Location(
            nickname=built_in_location["nickname"],
            location=built_in_location["location"],
            is_active=built_in_location["is_active"] and not has_active_location,
        ))
        if built_in_location["is_active"] and not has_active_location:
            has_active_location = True
        changed = True

    if changed:
        db.session.commit()

def serialize_location(location):
    return {
        "id": location.id,
        "nickname": location.nickname,
        "location": location.location,
        "is_active": location.is_active,
        "is_protected": location.nickname in PROTECTED_LOCATION_NICKNAMES,
    }

def serialize_reading(reading):
    location = reading.location
    return {
        "id": reading.id,
        "recorded_at": reading.recorded_at.isoformat(),
        "location_id": location.id,
        "location_nickname": location.nickname,
        "location": location.location,
        "outside_temperature": reading.outside_temperature,
        "outside_humidity": reading.outside_humidity,
        "inside_temperature": reading.inside_temperature,
        "inside_humidity": reading.inside_humidity,
    }

def get_locations_data():
    ensure_schema()
    locations = Location.query.order_by(Location.nickname.asc()).all()
    active_location = get_active_location()
    return {
        "active_location": serialize_location(active_location),
        "locations": [serialize_location(location) for location in locations],
    }

def get_active_location():
    db.create_all()
    location = Location.query.filter_by(is_active=True).order_by(Location.id.asc()).first()
    if location:
        return location

    location = Location.query.order_by(Location.id.asc()).first()
    if location:
        location.is_active = True
        db.session.commit()
        return location

    ensure_default_location()
    return Location.query.filter_by(is_active=True).first()

def create_location(nickname, location):
    normalized_nickname = (nickname or "").strip()
    normalized_location = (location or "").strip()

    if not normalized_nickname:
        return None, "nickname is required"
    if not normalized_location:
        return None, "location is required"

    ensure_schema()
    if Location.query.filter_by(nickname=normalized_nickname).first():
        return None, "nickname must be unique"

    new_location = Location(
        nickname=normalized_nickname,
        location=normalized_location,
        is_active=False,
    )
    try:
        db.session.add(new_location)
        db.session.flush()
        set_active_location(new_location.id, commit=False)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Failed to create location nickname=%s", normalized_nickname)
        raise

    return serialize_location(new_location), None

def delete_location(location_id):
    ensure_schema()
    location = db.session.get(Location, location_id)
    if not location:
        return None, "location was not found", 404

    if Location.query.count() <= 1:
        return None, "at least one spot is required", 400

    if location.nickname in PROTECTED_LOCATION_NICKNAMES:
        return None, "built-in spots cannot be deleted", 400

    was_active = location.is_active

    try:
        Reading.query.filter_by(location_id=location.id).delete()
        db.session.delete(location)
        db.session.flush()

        if was_active:
            replacement = Location.query.order_by(Location.nickname.asc()).first()
            if replacement:
                replacement.is_active = True

        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Failed to delete location id=%s", location_id)
        raise

    return get_locations_data(), None, 200

def set_active_location(location_id, commit=True):
    location = db.session.get(Location, location_id)
    if not location:
        return None

    Location.query.update({Location.is_active: False})
    location.is_active = True
    if commit:
        db.session.commit()
    return location

def fetch_current_weather_for_location(location):
    normalized_location = location or DEFAULT_LOCATION_NAME
    current_app.logger.info("Resolving current weather location=%s", normalized_location)
    current_weather = find_current_weather(normalized_location)
    if not current_weather:
        current_app.logger.info("No current weather found location=%s", normalized_location)
        return None, None

    return normalized_location, current_weather

def get_latest_reading_data():
    ensure_schema()
    active_location = get_active_location()
    reading = Reading.query.order_by(Reading.recorded_at.desc()).first()

    if not reading:
        current_app.logger.info("No latest reading found")
        return {
            "location": active_location.location,
            "active_location": serialize_location(active_location),
            "reading": None,
        }

    current_app.logger.info("Latest reading found id=%s location=%s", reading.id, reading.location.location)
    return {
        "location": active_location.location,
        "active_location": serialize_location(active_location),
        "reading": serialize_reading(reading),
    }

def get_reading_history_data(hours):
    requested_hours = hours
    hours = max(1, min(hours, 168))
    if hours != requested_hours:
        current_app.logger.info(
            "Clamped reading history hours requested=%s clamped=%s",
            requested_hours,
            hours,
        )
    ensure_schema()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    readings = (
        Reading.query
        .filter(Reading.recorded_at >= cutoff)
        .order_by(Reading.recorded_at.asc())
        .all()
    )
    current_app.logger.info(
        "Reading history query complete hours=%s cutoff=%s count=%s",
        hours,
        cutoff.isoformat(),
        len(readings),
    )

    return {
        "hours": hours,
        "readings": [serialize_reading(reading) for reading in readings],
    }

def get_paginated_reading_data(page, per_page, sort_by, sort_dir, location_id=None):
    if sort_by not in READING_COLUMNS:
        current_app.logger.info("Unsupported readings sort_by=%s", sort_by)
        return None, "sort_by is not supported"

    if sort_dir not in {"asc", "desc"}:
        current_app.logger.info("Unsupported readings sort_dir=%s", sort_dir)
        return None, "sort_dir must be asc or desc"

    ensure_schema()
    requested_page = page
    requested_per_page = per_page
    per_page = max(1, min(per_page, 100))
    page = max(1, page)
    if page != requested_page or per_page != requested_per_page:
        current_app.logger.info(
            "Clamped readings pagination requested_page=%s page=%s requested_per_page=%s per_page=%s",
            requested_page,
            page,
            requested_per_page,
            per_page,
        )
    sort_column = READING_COLUMNS[sort_by]
    query = Reading.query
    if location_id is not None:
        if not db.session.get(Location, location_id):
            return None, "location was not found"
        query = query.filter(Reading.location_id == location_id)

    query = query.order_by(sort_column.desc() if sort_dir == "desc" else sort_column.asc())
    total = query.count()
    pages = max(1, (total + per_page - 1) // per_page)
    page = min(page, pages)
    readings = (
        query
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    current_app.logger.info(
        "Paginated readings query complete page=%s per_page=%s pages=%s total=%s count=%s sort_by=%s sort_dir=%s",
        page,
        per_page,
        pages,
        total,
        len(readings),
        sort_by,
        sort_dir,
    )

    return {
        "page": page,
        "per_page": per_page,
        "pages": pages,
        "total": total,
        "location_id": location_id,
        "readings": [serialize_reading(reading) for reading in readings],
    }, None

def create_reading(inside_temperature, inside_humidity):
    ensure_schema()
    active_location = get_active_location()
    normalized_location, current_weather = fetch_current_weather_for_location(active_location.location)
    if not normalized_location:
        return None

    current_app.logger.info(
        "Building reading location=%s inside_temperature=%s inside_humidity=%s outside_temperature=%s outside_humidity=%s",
        normalized_location,
        inside_temperature,
        inside_humidity,
        current_weather["temp_f"],
        current_weather["humidity"],
    )
    reading = Reading(
        location=active_location,
        outside_temperature=current_weather["temp_f"],
        outside_humidity=current_weather["humidity"],
        inside_temperature=inside_temperature,
        inside_humidity=inside_humidity,
    )

    try:
        db.session.add(reading)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Failed to save reading location=%s", normalized_location)
        raise

    current_app.logger.info("Saved reading id=%s location=%s", reading.id, normalized_location)
    return reading
