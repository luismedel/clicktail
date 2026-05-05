PYTHON ?= .e/bin/python
PIP := $(PYTHON) -m pip
PYTEST := $(PYTHON) -m pytest
RUFF := $(PYTHON) -m ruff
MYPY := $(PYTHON) -m mypy

.PHONY: setup test lint format format-check

setup:
	python3 -m venv .e
	$(PIP) install -r requirements.txt -r test-requirements.txt

test:
	set -a; . ./.env.tests; set +a; $(PYTEST) -q

lint:
	$(RUFF) check clicktail tests
	$(MYPY) clicktail tests

format:
	$(RUFF) format clicktail tests
	$(RUFF) check clicktail tests --fix

format-check:
	$(RUFF) format . --check
	$(RUFF) check .
