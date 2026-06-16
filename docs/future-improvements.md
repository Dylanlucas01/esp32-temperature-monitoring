# Future Improvements

## Reliability

- Store indoor readings even when OpenWeather is unavailable, then backfill outdoor weather later if desired.
- Add request authentication so only known devices can post readings.
- Add centralized request IDs or trace IDs so ESP32 logs can be correlated with server logs.
- Add rate limiting or per-device throttling to protect the API.
- Add health checks that can verify database connectivity, not just Flask process availability.

## Firmware

- Add a local buffer for offline readings.

## Data Model

- Add `device_id` to support multiple ESP32 devices.
- Add validation constraints for humidity and temperature ranges.
- Expand the database model to support richer location history, such as moving the device between rooms or taking it on the go.

## API

- Add typed request validation with clear error messages.
- Add location filtering for history and table endpoints.
- Add CSV export for readings.
- Add aggregate endpoints for min, max, average, and daily summaries.
- Expand API tests for database failures, malformed JSON, and multiple-device scenarios.

## Frontend

- Add controls to track extra metadata, such as whether the AC is on or whether the blinds are open.
- Add humidity charting.
- Add loading and error states that expose more detail without requiring browser dev tools.
- Improve chart accessibility with a data table or downloadable summary.
- Preserve readings table sort/page state in the URL.

## Operations

- Add monitoring for OpenWeather failures and ingestion volume.
- Add CI that runs linting and tests.
- Add production log aggregation and alerting.

## Security

- Add device API tokens or signed requests.
- Require HTTPS in deployed environments.
