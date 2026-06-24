import pytest

from app.services.openweather import (
    OPEN_WEATHER_URL,
    OpenWeatherConfigError,
    find_current_weather,
    get_openweather_api_key,
)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


def test_get_openweather_api_key_requires_configuration(app):
    app.config["OPENWEATHER_API_KEY"] = None

    with app.app_context(), pytest.raises(OpenWeatherConfigError):
        get_openweather_api_key()


def test_find_current_weather_uses_openweather_params(app, monkeypatch):
    captured = {}

    def fake_get(url, params, timeout):
        captured["url"] = url
        captured["params"] = params
        captured["timeout"] = timeout
        return FakeResponse({"list": [{"main": {"temp": 69.2, "humidity": 55}}]})

    monkeypatch.setattr("app.services.openweather.requests.get", fake_get)

    with app.app_context():
        weather = find_current_weather("Redwood City")

    assert weather == {"temp_f": 69.2, "humidity": 55}
    assert captured["url"] == OPEN_WEATHER_URL
    assert captured["params"] == {
        "q": "Redwood City",
        "units": "imperial",
        "type": "accurate",
        "appid": "test-api-key",
    }
    assert captured["timeout"] == 10


def test_find_current_weather_returns_none_for_no_results(app, monkeypatch):
    monkeypatch.setattr(
        "app.services.openweather.requests.get",
        lambda url, params, timeout: FakeResponse({"list": []}),
    )

    with app.app_context():
        weather = find_current_weather("Missing Place")

    assert weather is None
