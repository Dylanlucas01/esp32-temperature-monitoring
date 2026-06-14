from datetime import datetime, timezone

from extensions import db


class Reading(db.Model):
    __tablename__ = "readings"

    id = db.Column(db.Integer, primary_key=True)
    recorded_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    location = db.Column(db.String(120), nullable=False)

    outside_temp_f = db.Column(db.Float)
    outside_humidity = db.Column(db.Float)

    inside_temp_f = db.Column(db.Float)
    inside_humidity = db.Column(db.Float)
