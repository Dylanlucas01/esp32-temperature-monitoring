# ESP32 Temperature Monitoring

A small Flask web app for collecting indoor temperature and humidity readings from an ESP32, pairing each reading with current outdoor weather from OpenWeather, and displaying the results in a browser dashboard.

## Features

- Dashboard at `/` with latest indoor/outdoor readings and a 12-hour temperature chart
- Saved locations with an active spot selector for portable ESP32 use
- Weather history table at `/weather-history` with pagination and sortable columns
- JSON API for posting ESP32 sensor readings
- OpenWeather integration for outdoor temperature and humidity
- SQL database storage with local SQLite by default and PostgreSQL support through `DATABASE_URL`
- Backend logging for request flow, weather lookups, validation failures, and database writes
- Python test suite for routes, services, and configuration helpers

## Documentation

Additional project documentation can be found in the [`docs`](docs) directory:

- [Documentation Index](docs/index.md)
- [API and Data Flow](docs/api-flow.md)
- [Sequence Diagram](docs/sequence-diagram.md)
- [Database Design](docs/database-design.md)
- [Firmware Architecture](docs/firmware-architecture.md)
- [Hardware and Wiring](docs/hardware.md)
- [Engineering Decisions](docs/tradeoffs-and-decisions.md)

## Project Structure

- `src/app/server.py` creates the Flask app, registers blueprints, and serves the static pages.
- `src/app/routes/sensor_data.py` defines the sensor and readings API routes.
- `src/app/services/location_service.py` handles saved locations, active location selection, and default locations.
- `src/app/services/reading_service.py` handles reading serialization, database queries, and reading creation.
- `src/app/services/weather_service.py` handles cached weather lookups for app workflows.
- `src/app/services/openweather.py` handles OpenWeather API calls.
- `src/app/models.py` defines the SQLAlchemy `Location` and `Reading` models.
- `tests/unit/` contains direct helper and service tests.
- `tests/integration/` contains Flask route tests using a temporary database.
- `Makefile` wraps common local development commands.

## Local Setup

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
make install
```

Create a `.env` file:

```bash
OPENWEATHER_API_KEY=your_openweather_api_key
```

Run the app:

```bash
make run
```

Open <http://localhost:5001>.

By default, the app uses SQLite at `/tmp/esp32_temperature.db`. The database tables are created automatically the first time an API route needs them.

You can still run the commands directly if needed:

```bash
pip install -r requirements.txt
PYTHONPATH=src python -m app.server
```

## Development Commands

The Makefile defaults to `.venv/bin/python` and `.venv/bin/pip`.

| Command | Purpose |
| --- | --- |
| `make help` | Show available Makefile targets. |
| `make install` | Install Python dependencies from `requirements.txt`. |
| `make run` | Start the Flask app on port `5001`. |
| `make run PORT=8000` | Start the app on a custom port. |
| `make test` | Run the pytest suite. |
| `make test-unit` | Run only unit tests. |
| `make test-integration` | Run only integration tests. |
| `make check` | Compile Python files and run tests. |
| `make clean` | Remove Python cache and pytest cache directories. |

## Environment Variables

| Variable | Required | Description |
| --- | --- | --- |
| `OPENWEATHER_API_KEY` | Yes | API key used to fetch current outdoor weather. |
| `DATABASE_URL` | No | Database connection string. Defaults to local SQLite. `postgres://` URLs are automatically converted for `psycopg`. |
| `LOG_LEVEL` | No | Python logging level. Defaults to `INFO`. Use `DEBUG` for schema-check logs or `WARNING` to reduce normal request logs. |
| `PORT` | No | Port used by `src/app/server.py`. Defaults to `5001`. |

## Testing

Run the backend tests with:

```bash
make test
```

The tests are split by scope:

- unit test covers direct helpers and service behavior with mocked dependencies.
- integration test covers Flask routes, SQLAlchemy, and the reading service working together with a temporary SQLite database.

OpenWeather responses are mocked, so tests do not require network access or a real OpenWeather API key.

You can run each group separately:

```bash
make test-unit
make test-integration
```

For a fuller local verification pass, run:

```bash
make check
```

## API Endpoints

### Health Check

```http
GET /health
```

Returns:

```json
{ "status": "ok" }
```

### Current Outdoor Weather

```http
GET /api/outdoor/current?location=Redwood%20City
```

Returns current outdoor temperature and humidity from OpenWeather. If `location` is omitted, the server uses the active saved location.

### Locations

```http
GET /api/locations
```

Returns saved locations and the active location used for future ESP32 readings.

```http
POST /api/locations
Content-Type: application/json

{
  "nickname": "Desk",
  "location": "Redwood City"
}
```

Creates a saved location and makes it active.

```http
PUT /api/locations/active
Content-Type: application/json

{
  "location_id": 1
}
```

Makes an existing location active.

### Latest Reading

```http
GET /api/readings/latest
```

Returns the latest saved indoor/outdoor reading, or `reading: null` if no readings exist.

### Reading History

```http
GET /api/readings/history?hours=12
```

Returns readings from the last `1` to `168` hours. The default is `12`.

### Paginated Readings

```http
GET /api/readings?page=1&per_page=10&sort_by=recorded_at&sort_dir=desc
```

Supported `sort_by` values:

- `id`
- `recorded_at`
- `inside_temperature`
- `inside_humidity`
- `outside_temperature`
- `outside_humidity`

### Create a Reading

```http
POST /api/indoor
Content-Type: application/json

{
  "temperature": 72.4,
  "humidity": 45.8
}
```

## ESP32 Request Example

Your ESP32 should send JSON like this:

```json
{
  "temperature": 72.4,
  "humidity": 45.8
}
```

The API expects:

- `temperature`: indoor temperature in Fahrenheit
- `humidity`: indoor relative humidity percentage

The server uses the active saved location from the web app for OpenWeather lookup. Successful requests save the full reading and return a compact response for the ESP32 LCD. The ESP32 can update the LCD from this POST response instead of making a separate display refresh GET.

Example success response:

```json
{
  "nickname": "Home",
  "location": "Redwood City",
  "outside_temperature": 68.2,
  "outside_humidity": 62
}
```

The firmware requires `outside_temperature` and can use `location` when present. It can ignore `nickname` and `outside_humidity` if the LCD flow does not need them.

The server caches OpenWeather results for five minutes per location. Each POST still saves a reading, but repeated posts within that cache window reuse the cached outdoor temperature and humidity.

## Deployment

This project includes a `Procfile` for platforms that run Gunicorn:

```bash
web: gunicorn --pythonpath src app.server:app
```

For production, set:

```bash
OPENWEATHER_API_KEY=your_openweather_api_key
DATABASE_URL=your_database_url
LOG_LEVEL=INFO
```

## Notes

- The default saved location is `Home`, using `Redwood City`.
- Unknown active weather locations return `400`.
- OpenWeather configuration errors return `503`.
- OpenWeather request failures return `502`.
- Logs intentionally avoid printing API keys and database credentials.
- The local SQLite database path is under `/tmp`, so local data may be temporary depending on your system cleanup behavior.
