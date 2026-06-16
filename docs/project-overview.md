# ESP32 Environmental Monitoring System

## Overview

The ESP32 Environmental Monitoring System is a full-stack IoT application that collects indoor environmental data, integrates external weather information, stores historical readings, and presents the data through a web interface.

The project combines embedded development, backend API design, database management, cloud deployment, and web development into a single system.

The primary objective was to build a reliable platform for monitoring temperature and humidity while gaining experience across multiple areas of software engineering.

---

## Outcome

This project demonstrates the integration of embedded systems, backend services, databases, cloud infrastructure, and web technologies. It serves as both a practical monitoring platform and a learning experience in full-stack software engineering and system design.

## Features

### Embedded Device

- ESP32 microcontroller
- DHT11 temperature and humidity sensor
- 16x2 LCD display
- Push-button interface
- Wi-Fi connectivity
- Network time synchronization

### Backend Services

- Flask REST API
- Sensor data ingestion endpoints
- Weather API integration
- Business logic and data processing
- Request, weather, validation, and database logging
- Pytest coverage for backend routes and service helpers

### Data Storage

- SQLite for local development
- PostgreSQL for deployment
- Historical environmental data storage
- Timestamped sensor readings

### Web Application

- View collected sensor data
- Monitor environmental conditions
- Access historical readings

---

## System Workflow

1. The ESP32 reads temperature and humidity data from the DHT11 sensor.
2. Sensor readings are sent to the Flask API.
3. The backend retrieves outdoor weather information for the requested location.
4. The backend stores the indoor reading together with the outdoor weather values in the configured SQL database.
5. The saved reading is returned to the ESP32 and can be displayed on the LCD.
6. Users can access stored data through the web application.

---

## Technologies Used

### Embedded

- ESP32
- ESP-IDF
- C++

### Backend

- Python
- Flask

### Database

- SQLite
- PostgreSQL
- SQLAlchemy

### Frontend

- HTML
- CSS
- JavaScript

### Infrastructure

- Heroku
- Neon
- Git
- GitHub
- Makefile-based local workflow

---

## My Contributions

This project was designed and developed independently.

Responsibilities included:

- System architecture design
- ESP32 firmware development
- Sensor integration
- LCD interface development
- Wi-Fi and NTP implementation
- REST API development
- Database design
- Web application development
- Deployment and testing
- Backend test automation
- Operational logging

---

## Key Design Decisions

### Server-Side Weather Integration

Rather than having the ESP32 communicate directly with an external weather service, the backend server handles weather requests.

Benefits include:

- Reduced complexity on the embedded device
- Centralized external API management
- Easier maintenance and future expansion

### Modular Firmware Architecture

The firmware was separated into dedicated modules for:

- Sensor management
- Display management
- Wi-Fi and time synchronization
- User input handling

This improves maintainability and scalability.

### API-Driven Communication

The ESP32 communicates exclusively through REST endpoints, allowing the device, backend, and database layers to remain loosely coupled.

---

## Challenges

- Configuring reliable Wi-Fi connectivity
- Implementing accurate time synchronization
- Managing limited LCD display space
- Designing a flexible database schema
- Deploying and maintaining cloud services
- Debugging interactions between embedded and backend components
- Keeping backend behavior testable without requiring live weather API calls

---

## Future Improvements

- Support for multiple ESP32 devices
- User authentication
- Alerting and notifications
- Additional sensors
- Containerized deployment
- CI/CD pipelines that run the existing automated tests
