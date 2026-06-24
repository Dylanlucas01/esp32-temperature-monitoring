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
	PYTHONPATH=src PORT=$(PORT) $(PYTHON) -m app.server

test:
	PYTHONPATH=src $(PYTHON) -m pytest

test-unit:
	PYTHONPATH=src $(PYTHON) -m pytest tests/unit

test-integration:
	PYTHONPATH=src $(PYTHON) -m pytest tests/integration

check:
	PYTHONPATH=src $(PYTHON) -m compileall src tests
	PYTHONPATH=src $(PYTHON) -m pytest

clean:
	find . -type d \( -name "__pycache__" -o -name ".pytest_cache" \) -prune -exec rm -rf {} +
