import importlib
import os
import sys

import pytest


@pytest.fixture
def app(tmp_path, monkeypatch):
    database_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database_path}")
    monkeypatch.setenv("OPENWEATHER_API_KEY", "test-api-key")
    monkeypatch.setenv("LOG_LEVEL", "CRITICAL")

    for module_name in ("config", "server"):
        if module_name in sys.modules:
            importlib.reload(sys.modules[module_name])

    from extensions import db
    from server import create_app

    test_app = create_app()
    test_app.config.update(TESTING=True)

    with test_app.app_context():
        db.drop_all()
        db.create_all()

    yield test_app

    with test_app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()
