import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def get_database_url():
    database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        return f"sqlite:///{Path('/tmp/esp32_temperature.db')}"

    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+psycopg://", 1)

    return database_url


class Config:
    SQLALCHEMY_DATABASE_URI = get_database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    OPENWEATHER_API_KEY = os.environ.get("OPENWEATHER_API_KEY")
