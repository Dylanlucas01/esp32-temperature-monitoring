import os
import logging
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from flask import Flask, send_file

from config import Config
from extensions import db
from routes.sensor_data import sensor_data_bp

def describe_database_uri(database_uri):
    parsed_uri = urlsplit(database_uri)
    if not parsed_uri.netloc:
        return parsed_uri.scheme

    host = parsed_uri.hostname or "unknown-host"
    if parsed_uri.port:
        host = f"{host}:{parsed_uri.port}"

    return urlunsplit((parsed_uri.scheme, host, "", "", ""))

def configure_logging(app):
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    app.logger.setLevel(getattr(logging, log_level, logging.INFO))

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    configure_logging(app)

    db.init_app(app)
    app.register_blueprint(sensor_data_bp)

    @app.route("/")
    def home():
        return send_file(Path(__file__).with_name("dashboard.html"))

    @app.route("/readings")
    def readings():
        return send_file(Path(__file__).with_name("readings.html"))

    @app.route("/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", "5000")))
