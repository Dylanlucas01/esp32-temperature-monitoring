# Database Design

## Database Choice

I chose PostgreSQL for deployment, while local development defaults to SQLite at `/tmp/esp32_temperature.db` when `DATABASE_URL` is not set.
The application uses SQLAlchemy through Flask-SQLAlchemy as a wrapper to handle database calls.

## Schema

The current schema has two tables: `locations` and `temperature_readings`.

```mermaid
erDiagram
    locations ||--o{ temperature_readings : has

    locations {
        integer id PK
        string nickname UK
        string location
        boolean is_active
    }

    temperature_readings {
        integer id PK
        datetime recorded_at
        integer location_id FK
        float outside_temperature
        float outside_humidity
        float inside_temperature
        float inside_humidity
    }
```

## Table: `locations`

| Column | Type | Purpose |
| --- | --- | --- |
| `id` | Integer | Primary key. |
| `nickname` | String(80) | Unique human-friendly name for a spot, such as `Home`, `Desk`, or `Workshop`. |
| `location` | String(120) | City or location value used for OpenWeather lookup. |
| `is_active` | Boolean | Marks the current location used for new ESP32 readings. |

## Table: `temperature_readings`

| Column | Type | Purpose |
| --- | --- | --- |
| `id` | Integer | Primary key. |
| `recorded_at` | DateTime with timezone | Server-side timestamp created when the reading is saved. |
| `location_id` | Integer | Foreign key to the active `locations` row used when the reading was saved. |
| `outside_temperature` | Float | Outdoor temperature from OpenWeather in Fahrenheit. |
| `outside_humidity` | Float | Outdoor relative humidity percentage from OpenWeather. |
| `inside_temperature` | Float | Indoor temperature reported by the ESP32 in Fahrenheit. |
| `inside_humidity` | Float | Indoor relative humidity percentage reported by the ESP32. |

## Write Path

1. `POST /api/indoor` receives JSON from the ESP32.
2. `routes/sensor_data.py` parses the request body for indoor `temperature` and `humidity`.
3. `services/reading_service.py` loads the active `locations` row.
4. `services/reading_service.py` fetches current outdoor weather for the active location through `services/openweather.py`.
5. If the location cannot be resolved or OpenWeather fails, no database row is created.
6. When weather data is available, a `Reading` model instance is created with the active `location_id`, indoor sensor values, and outdoor weather values.
7. `ensure_schema()` calls `db.create_all()`.
8. The reading is added to the session and committed.
9. If the commit fails, the session is rolled back and the failure is logged.

The write path logs validation outcomes, weather lookup results, reading construction, successful saves, and database commit failures. Logs do not include API keys or database credentials.

## Read Patterns

`routes/sensor_data.py` parses request parameters, while `services/reading_service.py` handles the database queries for three main read patterns:

- Latest reading: `Reading.query.order_by(Reading.recorded_at.desc()).first()`
- Recent history: filter by `recorded_at >= cutoff`, ordered ascending
- Paginated table: count all rows, then apply order, offset, and limit
- Locations: list all saved spots, create a spot, or activate a spot for future ESP32 writes

Supported table sort columns:

- `id`
- `recorded_at`
- `inside_temperature`
- `inside_humidity`
- `outside_temperature`
- `outside_humidity`
