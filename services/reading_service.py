from datetime import datetime, timedelta, timezone

from flask import current_app
from sqlalchemy.exc import SQLAlchemyError

from extensions import db
from models import Reading
from services.openweather import find_current_weather

DEFAULT_LOCATION_NAME = "Redwood City"

READING_COLUMNS = {
    "id": Reading.id,
    "recorded_at": Reading.recorded_at,
    "inside_temp_f": Reading.inside_temp_f,
    "inside_humidity": Reading.inside_humidity,
    "outside_temp_f": Reading.outside_temp_f,
    "outside_humidity": Reading.outside_humidity,
}

def ensure_schema():
    current_app.logger.debug("Ensuring database schema")
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
    normalized_location = location or DEFAULT_LOCATION_NAME
    current_app.logger.info("Resolving current weather location=%s", normalized_location)
    current_weather = find_current_weather(normalized_location)
    if not current_weather:
        current_app.logger.info("No current weather found location=%s", normalized_location)
        return None, None

    return normalized_location, current_weather

def get_latest_reading_data():
    ensure_schema()
    reading = Reading.query.order_by(Reading.recorded_at.desc()).first()

    if not reading:
        current_app.logger.info("No latest reading found")
        return {
            "location": DEFAULT_LOCATION_NAME,
            "reading": None,
        }

    current_app.logger.info("Latest reading found id=%s location=%s", reading.id, reading.location)
    return {
        "location": reading.location,
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

def get_paginated_reading_data(page, per_page, sort_by, sort_dir):
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
        "readings": [serialize_reading(reading) for reading in readings],
    }, None

def create_reading(location, inside_temp_f, inside_humidity):
    normalized_location, current_weather = fetch_current_weather_for_location(location)
    if not normalized_location:
        return None

    current_app.logger.info(
        "Building reading location=%s inside_temp_f=%s inside_humidity=%s outside_temp_f=%s outside_humidity=%s",
        normalized_location,
        inside_temp_f,
        inside_humidity,
        current_weather["temp_f"],
        current_weather["humidity"],
    )
    reading = Reading(
        location=normalized_location,
        outside_temp_f=current_weather["temp_f"],
        outside_humidity=current_weather["humidity"],
        inside_temp_f=inside_temp_f,
        inside_humidity=inside_humidity,
    )

    ensure_schema()
    try:
        db.session.add(reading)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Failed to save reading location=%s", normalized_location)
        raise

    current_app.logger.info("Saved reading id=%s location=%s", reading.id, normalized_location)
    return reading
