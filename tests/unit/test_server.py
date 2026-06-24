import logging

from app.server import configure_logging, describe_database_uri


def test_describe_database_uri_hides_credentials():
    database_uri = "postgresql+psycopg://user:secret@example.com:5432/weather"

    assert describe_database_uri(database_uri) == "postgresql+psycopg://example.com:5432"


def test_describe_database_uri_handles_sqlite_paths():
    assert describe_database_uri("sqlite:////tmp/esp32_temperature.db") == "sqlite"


def test_configure_logging_falls_back_to_info_for_unknown_level(app, monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "LOUD")

    configure_logging(app)

    assert app.logger.level == logging.INFO
