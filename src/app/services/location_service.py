from flask import current_app
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import Location, Reading

DEFAULT_LOCATION_NAME = "Redwood City"
DEFAULT_LOCATION_NICKNAME = "Home"
BUILT_IN_LOCATIONS = (
    {"nickname": DEFAULT_LOCATION_NICKNAME, "location": DEFAULT_LOCATION_NAME, "is_active": True},
    {"nickname": "Roaming", "location": "San Diego", "is_active": False},
    {"nickname": "Exploring", "location": "Redwood City", "is_active": False},
)
PROTECTED_LOCATION_NICKNAMES = {location["nickname"] for location in BUILT_IN_LOCATIONS}


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
