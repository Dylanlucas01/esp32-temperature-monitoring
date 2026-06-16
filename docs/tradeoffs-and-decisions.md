# Tradeoffs and Decisions

## Flask for the Backend

Flask keeps the application small and direct. The app only needs static page serving, a handful of JSON endpoints, environment-based configuration, and database access. A larger framework would add structure, but the current project size does not need it.

Tradeoff: Flask leaves more conventions to the project. As the API grows, validation, error handling, and app organization should become more formal.

## Static Frontend Instead of a Build System

The dashboard uses plain HTML, CSS, and JavaScript instead of using React and TypeScript. This avoids Node tooling and keeps deployment simple.

Tradeoff: As interactivity grows, state management and reusable UI patterns may become harder to maintain than they would be in a component framework.

## Server-Enriched Readings

The ESP32 sends only indoor readings. The server fetches outdoor weather at write time.

Benefits:

- Firmware stays simple.
- The OpenWeather API key remains on the server.
- Stored readings contain indoor and outdoor context from the same ingestion moment.

Tradeoffs:

- Every reading write depends on OpenWeather availability.
- Every stored reading can consume an OpenWeather API call.
- If the weather API fails, the indoor reading is not stored.

## Minimal Validation

The API currently requires `location`, validates pagination/sorting parameters, and passes sensor values through as floats or nullable values.

Tradeoff: This is forgiving for early firmware development, but it can store incomplete or unrealistic sensor values. Production should validate numeric ranges and reject malformed sensor payloads.

## Timestamp Generated On The Server

`recorded_at` is generated when the server persists a reading.

Benefits:

- Firmware does not need reliable clock sync.
- Stored timestamps are consistent from the server's perspective.

Tradeoff: If the ESP32 buffers readings while offline, delayed uploads will not reflect the original measurement time.

## Current Error Strategy

OpenWeather configuration errors return `503`; request failures return `502`; bad client inputs return `400`.

The backend logs request flow, validation failures, OpenWeather lookup outcomes, database query counts, and database commit failures. Startup logs include whether OpenWeather is configured and a sanitized database URI shape without credentials.

Tradeoff: The responses are simple and useful for firmware, and the logs provide useful operational breadcrumbs. Error handling is still route-local rather than centralized, and the log format is conventional text rather than full JSON structured logging.

## Makefile-Based Local Workflow

The project uses a small Makefile for common local tasks: installing dependencies, running the Flask app, running all tests, running unit or integration tests separately, running a fuller check, and cleaning Python cache files.

Benefit: Common commands are easy to discover and repeat locally or in CI.

Tradeoff: The Makefile assumes a local `.venv` by default. Developers using a different environment can override `PYTHON` and `PIP` when invoking `make`.

## Backend Test Suite

The backend tests use pytest, temporary SQLite databases, and mocked OpenWeather responses. They are split into unit and integration test.

Benefits:

- Tests run without network access or real API credentials.
- Unit tests cover direct helper and service behavior such as logging configuration, database URI sanitizing, OpenWeather configuration, and request parameter construction.
- Integration tests cover route behavior for success paths, validation failures, weather errors, pagination, sorting, and history queries.

Tradeoff: The tests focus on backend behavior and do not currently exercise the browser dashboard or ESP32 firmware.
