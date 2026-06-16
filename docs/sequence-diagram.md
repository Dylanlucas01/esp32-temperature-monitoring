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
    ESP32->>Routes: { location, temperature, humidity }
    Routes->>Routes: Validate location is present
    Routes->>Service: Create reading
    Service->>Weather: GET current weather for location
    Weather-->>Service: Weather data
    Service->>DB: Store readings entry
    Service-->>Routes: Saved reading
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
| Missing `location` on POST | `400` | `{ "error": "location is required" }` |
| Unknown weather location | `400` | `{ "error": "Could not find weather for <location>" }` |
| Unsupported `sort_by` | `400` | `{ "error": "sort_by is not supported" }` |
| Invalid `sort_dir` | `400` | `{ "error": "sort_dir must be asc or desc" }` |
| Invalid history `hours` | `400` | `{ "error": "hours must be a number" }` |
| OpenWeather key missing | `503` | `{ "error": "Weather service is not configured" }` |
| OpenWeather request failure | `502` | `{ "error": "Could not fetch current weather" }` |
