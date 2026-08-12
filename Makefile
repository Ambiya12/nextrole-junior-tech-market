VENV ?= .venv
VENV_PYTHON := $(VENV)/bin/python
PYTHON ?= $(if $(wildcard $(VENV_PYTHON)),$(VENV_PYTHON),python)
RUFF := $(PYTHON) -m ruff
MYPY := $(PYTHON) -m mypy
STREAMLIT := $(PYTHON) -m streamlit

.PHONY: setup check format lint test demo docker-demo

setup:
	python3 -m venv $(VENV)
	$(VENV_PYTHON) -m pip install --upgrade pip
	$(VENV_PYTHON) -m pip install -e '.[dev]'

check: lint test

format:
	$(RUFF) format .
	$(RUFF) check --fix .

lint:
	$(RUFF) format --check .
	$(RUFF) check .
	$(MYPY) src

test:
	$(PYTHON) -m pytest

demo:
	$(STREAMLIT) run app/streamlit_app.py

docker-demo:
	docker compose up --build demo
