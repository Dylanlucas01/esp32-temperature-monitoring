from flask import Flask

from config import Config
from extensions import db
from routes.readings import readings_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    app.register_blueprint(readings_bp)

    @app.route("/")
    def home():
        return "ESP32 Weather Station Running"

    @app.route("/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
