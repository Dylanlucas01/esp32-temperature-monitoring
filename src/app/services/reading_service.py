from datetime import datetime, timedelta, timezone

from flask import current_app
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import Location, Reading
from app.services.location_service import (
    ensure_schema,
    get_active_location,
    serialize_location,
)
from app.services.weather_service import fetch_current_weather_for_location

READING_COLUMNS = {
    "id": Reading.id,
    "recorded_at": Reading.recorded_at,
    "inside_temperature": Reading.inside_temperature,
    "inside_humidity": Reading.inside_humidity,
    "outside_temperature": Reading.outside_temperature,
    "outside_humidity": Reading.outside_humidity,
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
