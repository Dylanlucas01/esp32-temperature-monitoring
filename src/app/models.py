from datetime import datetime, timezone

from app.extensions import db


class Location(db.Model):
    __tablename__ = "locations"

    id = db.Column(db.Integer, primary_key=True)
    nickname = db.Column(db.String(80), unique=True, nullable=False)
    location = db.Column(db.String(120), nullable=False)
    is_active = db.Column(db.Boolean, default=False, nullable=False)


class Reading(db.Model):
    __tablename__ = "temperature_readings"

    id = db.Column(db.Integer, primary_key=True)
    recorded_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    location_id = db.Column(db.Integer, db.ForeignKey("locations.id"), nullable=False)
    location = db.relationship("Location", backref="readings")

    outside_temperature = db.Column(db.Float)
    outside_humidity = db.Column(db.Float)

    inside_temperature = db.Column(db.Float)
    inside_humidity = db.Column(db.Float)
