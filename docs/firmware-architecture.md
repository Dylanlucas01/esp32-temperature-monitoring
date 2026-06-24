# Firmware Architecture

The ESP32 firmware is organized around a polling loop in `src/main.cpp` plus a background FreeRTOS task for API uploads. This document summarizes the firmware behavior that matters to this Flask backend.

## Modules

```mermaid
flowchart TD
    Main[src/main.cpp] --> LCD[src/lcd.cpp]
    Main --> WiFiTime[src/wifi_time.cpp]
    Main --> API[src/api_client.cpp]
    Main --> Button[src/button.cpp]
    Main --> DHT11[src/dht11.cpp]
    Main --> Display[src/display_manager.cpp]

    Display --> LCD
    Display --> API
    Display --> WiFiTime

    API --> HTTP[ESP-IDF HTTP Client]
    API --> Queue[FreeRTOS Queue]
    API --> Mutex[FreeRTOS Mutex]
    WiFiTime --> WiFi[ESP-IDF Wi-Fi + SNTP]
```

## Startup Sequence

```mermaid
sequenceDiagram
    participant Main as app_main
    participant LCD as LCD driver
    participant WiFi as Wi-Fi/time
    participant API as API client
    participant Button
    participant DHT as DHT11
    participant Display as Display manager

    Main->>LCD: lcd_init()
    Main->>LCD: show startup screen
    Main->>WiFi: wifi_time_init()
    WiFi-->>Main: connected and time synced
    Main->>API: api_client_init()
    API-->>API: create queue, mutex, upload task
    Main->>Button: button_init()
    Main->>DHT: dht11_init()
    Main->>DHT: dht11_update()
    DHT-->>Main: temperature + humidity
    Main->>Display: display_update_values()
    Main->>API: api_client_queue_indoor()
```

`wifi_time_init()` blocks until the ESP32 is connected and the system clock is synchronized. After that, the main loop begins updating sensor and display state.

## Main Loop

```mermaid
flowchart TD
    Loop[Main loop every 200 ms] --> SensorDue{2 seconds elapsed?}
    SensorDue -- Yes --> ReadSensor[Read DHT11]
    SensorDue -- No --> CheckButton
    ReadSensor --> ReadOk{Read OK?}
    ReadOk -- Yes --> UpdateDisplayValues[Update current temp/humidity]
    ReadOk -- No --> CheckButton[Check button]
    UpdateDisplayValues --> UploadDue{5 minutes elapsed?}
    UploadDue -- Yes --> QueueUpload[Queue latest indoor reading]
    UploadDue -- No --> CheckButton
    QueueUpload --> CheckButton
    CheckButton --> Pressed{Button pressed?}
    Pressed -- Yes --> NextScreen[Advance display screen]
    Pressed -- No --> Render
    NextScreen --> Render[Render two LCD rows]
    Render --> Delay[Delay 200 ms]
    Delay --> Loop
```

The DHT11 is sampled every 2 seconds. Successful readings update the display immediately. Uploads are queued every 5 minutes using the latest successful reading.

## Display Rotation

```mermaid
stateDiagram-v2
    [*] --> Time
    Time --> IndoorTemperature: button press
    IndoorTemperature --> OutdoorTemperature: button press
    OutdoorTemperature --> Location: button press
    Location --> Humidity: button press
    Humidity --> Time: button press
```

The LCD renders the selected screen on row 1 and the next screen on row 2. Long location names scroll horizontally.

## API Contract

The firmware posts indoor readings to this backend:

```http
POST /api/indoor
Content-Type: application/json
```

```json
{
  "temperature": 72.4,
  "humidity": 45.8
}
```

Successful response:

```http
201 Created
```

```json
{
  "nickname": "Home",
  "location": "Redwood City",
  "outside_temperature": 68.2,
  "outside_humidity": 62
}
```

The firmware requires `outside_temperature` to update the outdoor temperature display. It uses `location` when present and can ignore additional fields. The backend stores the full reading and caches OpenWeather results for five minutes per location.

## Timing

| Activity | Interval |
| --- | --- |
| Main loop delay | 200 ms |
| DHT11 read | 2 seconds |
| API upload queue | 5 minutes |
| Location scroll step | 450 ms |

## Error Handling

| Status | Meaning | Firmware behavior |
| ---: | --- | --- |
| `201` | Reading stored | Continue normal sampling schedule. |
| `400` | Invalid request or unknown active weather location | Log the error and avoid tight retry loops until configuration changes. |
| `502` | Weather lookup failed | Retry later with backoff. |
| `503` | Server missing OpenWeather config | Retry slowly; this is a server configuration problem. |
| Network timeout | Server unavailable or Wi-Fi issue | Reconnect Wi-Fi and retry later. |
