.PHONY: help install run test test-unit test-integration check clean

PYTHON ?= .venv/bin/python
PIP ?= .venv/bin/pip
PORT ?= 5001

help:
	@echo "Available targets:"
	@echo "  make install          Install Python dependencies"
	@echo "  make run              Start the Flask app on PORT=$(PORT)"
	@echo "  make test             Run the Python test suite"
	@echo "  make test-unit        Run unit tests"
	@echo "  make test-integration Run integration tests"
	@echo "  make check            Compile Python files and run tests"
	@echo "  make clean            Remove Python test/build cache files"

install:
	$(PIP) install -r requirements.txt

run:
	PORT=$(PORT) $(PYTHON) server.py

test:
	$(PYTHON) -m pytest

test-unit:
	$(PYTHON) -m pytest tests/unit

test-integration:
	$(PYTHON) -m pytest tests/integration

check:
	$(PYTHON) -m compileall server.py routes services models.py config.py extensions.py tests
	$(PYTHON) -m pytest

clean:
	find . -type d \( -name "__pycache__" -o -name ".pytest_cache" \) -prune -exec rm -rf {} +
