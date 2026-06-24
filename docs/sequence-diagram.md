# Sequence Diagram

## ESP32 Sensor Data Flow

```mermaid
sequenceDiagram
    participant ESP32 as ESP32 firmware
    participant Routes as src/app/routes/sensor_data.py
    participant Reading as src/app/services/reading_service.py
    participant Location as src/app/services/location_service.py
    participant WeatherService as src/app/services/weather_service.py
    participant Weather as OpenWeather
    participant DB as Database

    ESP32->>ESP32: Read DHT11
    ESP32->>ESP32: Queue latest reading every 5 minutes
    ESP32->>Routes: POST /api/indoor
    ESP32->>Routes: { temperature, humidity }
    Routes->>Routes: Parse indoor sensor values
    Routes->>Reading: create_reading()
    Reading->>Location: Get active location
    Location->>DB: SELECT active location
    DB-->>Location: Active locations row
    Location-->>Reading: Active location
    Reading->>WeatherService: Fetch current weather
    WeatherService->>Weather: GET current weather when cache misses
    Weather-->>WeatherService: Weather data
    WeatherService-->>Reading: Current weather
    Reading->>DB: Store temperature_readings entry with location_id
    Reading-->>Routes: Saved reading with location and outdoor weather
    Routes-->>ESP32: 201 saved reading JSON
    ESP32->>ESP32: Update LCD
```

## Dashboard Load And Refresh

```mermaid
sequenceDiagram
    participant Browser
    participant Flask as Flask app
    participant Routes as src/app/routes/sensor_data.py
    participant Location as src/app/services/location_service.py
    participant Reading as src/app/services/reading_service.py
    participant DB as Database

    Browser->>Flask: GET /
    Flask-->>Browser: dashboard.html
    Browser->>Flask: GET /static/dashboard.css
    Browser->>Flask: GET /static/dashboard.js

    Browser->>Routes: GET /api/locations
    Routes->>Location: Get saved locations
    Location->>DB: SELECT locations
    DB-->>Location: Active and saved locations
    Location-->>Routes: Locations data
    Routes-->>Browser: Locations JSON

    Browser->>Routes: GET /api/readings/latest
    Routes->>Reading: Get latest reading
    Reading->>DB: SELECT newest reading
    DB-->>Reading: Latest reading or none
    Reading-->>Routes: Latest reading data
    Routes-->>Browser: Latest reading JSON

    Browser->>Routes: GET /api/readings/history?hours=12
    Routes->>Reading: Get reading history
    Reading->>DB: SELECT readings newer than cutoff
    DB-->>Reading: Time-ordered readings
    Reading-->>Routes: History data
    Routes-->>Browser: History JSON

    Browser->>Browser: Render metric cards and canvas chart
```



## Error Responses

The API uses compact JSON error responses:

| Scenario | Status | Response |
| --- | ---: | --- |
| Missing location nickname/value | `400` | `{ "error": "nickname is required" }` or `{ "error": "location is required" }` |
| Unknown active weather location | `400` | `{ "error": "Could not find weather for the active location" }` |
| Unsupported `sort_by` | `400` | `{ "error": "sort_by is not supported" }` |
| Invalid `sort_dir` | `400` | `{ "error": "sort_dir must be asc or desc" }` |
| Invalid history `hours` | `400` | `{ "error": "hours must be a number" }` |
| OpenWeather key missing | `503` | `{ "error": "Weather service is not configured" }` |
| OpenWeather request failure | `502` | `{ "error": "Could not fetch current weather" }` |
