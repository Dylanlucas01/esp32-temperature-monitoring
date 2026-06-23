# Sequence Diagram

## ESP32 Sensor Data Flow

```mermaid
sequenceDiagram
    participant ESP32 as ESP32 firmware
    participant Routes as routes/sensor_data.py
    participant Service as services/reading_service.py
    participant Weather as OpenWeather
    participant DB as Database

    ESP32->>ESP32: Read DHT11
    ESP32->>Routes: POST /api/indoor
    ESP32->>Routes: { temperature, humidity }
    Routes->>Routes: Parse indoor sensor values
    Routes->>Service: Create reading
    Service->>DB: SELECT active location
    DB-->>Service: Active locations row
    Service->>Weather: GET current weather for active location
    Weather-->>Service: Weather data
    Service->>DB: Store temperature_readings entry with location_id
    Service-->>Routes: Saved reading with location and outdoor weather
    Routes-->>ESP32: 201 saved reading JSON
    ESP32->>ESP32: Update LCD
```

## Dashboard Load And Refresh

```mermaid
sequenceDiagram
    participant Browser
    participant Flask as Flask app
    participant Routes as routes/sensor_data.py
    participant Service as services/reading_service.py
    participant DB as Database

    Browser->>Flask: GET /
    Flask-->>Browser: dashboard.html
    Browser->>Flask: GET /static/dashboard.css
    Browser->>Flask: GET /static/dashboard.js

    Browser->>Routes: GET /api/locations
    Routes->>Service: Get saved locations
    Service->>DB: SELECT locations
    DB-->>Service: Active and saved locations
    Service-->>Routes: Locations data
    Routes-->>Browser: Locations JSON

    Browser->>Routes: GET /api/readings/latest
    Routes->>Service: Get latest reading
    Service->>DB: SELECT newest reading
    DB-->>Service: Latest reading or none
    Service-->>Routes: Latest reading data
    Routes-->>Browser: Latest reading JSON

    Browser->>Routes: GET /api/readings/history?hours=12
    Routes->>Service: Get reading history
    Service->>DB: SELECT readings newer than cutoff
    DB-->>Service: Time-ordered readings
    Service-->>Routes: History data
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
