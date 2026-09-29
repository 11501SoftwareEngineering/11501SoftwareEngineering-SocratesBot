.DEFAULT_GOAL := help

.PHONY: help setup dev gen fix check test db db-down db-revision db-upgrade db-downgrade db-current

help:
	@echo "Backend commands: make setup, dev, gen, fix, check, test, db, db-down"
	@echo 'Migration commands: make db-revision message="description", db-upgrade, db-downgrade, db-current'

setup:
	uv sync --locked
	uv run pre-commit install --config ../.pre-commit-config.yaml

dev:
	uv run --locked fastapi dev app/main.py

gen:
	uv run --locked python -m scripts.generate_openapi

fix:
	uv run --locked ruff check --fix .
	uv run --locked ruff format .

check:
	uv run --locked ruff check .
	uv run --locked ruff format --check .
	uv run --locked pytest tests/api -q

test:
	uv run --locked pytest tests/api -q

db:
	docker-compose -f ../devops/prod/docker-compose.db.yml up

db-down:
	docker-compose -f ../devops/prod/docker-compose.db.yml down

db-revision:
	@test -n "$(message)" || { echo 'Usage: make db-revision message="description"' >&2; exit 2; }
	uv run --locked alembic revision --autogenerate -m "$(message)"

db-upgrade:
	uv run --locked alembic upgrade head

db-downgrade:
	uv run --locked alembic downgrade -1

db-current:
	uv run --locked alembic current
