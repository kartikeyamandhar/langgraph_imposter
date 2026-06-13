.PHONY: setup dev-server dev-web test lint typecheck evals migrate

PYTHON ?= python3
VENV ?= .venv

setup:
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/pip install -e ".[dev]"
	cd web && npm install

dev-server:
	$(VENV)/bin/uvicorn server.main:app --reload --port 8000

dev-web:
	cd web && npm run dev

test:
	$(VENV)/bin/pytest

lint:
	$(VENV)/bin/ruff check .
	cd web && npm run lint

typecheck:
	$(VENV)/bin/mypy
	cd web && npx tsc --noEmit

evals:
	$(VENV)/bin/pytest evals --override-ini testpaths=evals

migrate:
	$(VENV)/bin/alembic -c server/alembic.ini upgrade head
