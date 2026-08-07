PYTHON := .venv/bin/python

.PHONY: setup check format lint test

setup:
	python3 -m venv .venv
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e '.[dev]'

check: lint test

format:
	.venv/bin/ruff format .
	.venv/bin/ruff check --fix .

lint:
	.venv/bin/ruff format --check .
	.venv/bin/ruff check .
	.venv/bin/mypy src

test:
	$(PYTHON) -m pytest
