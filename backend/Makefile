.DEFAULT_GOAL := help

.PHONY: help setup dev gen fix check test db db-down

help:
	@echo "Backend commands: make setup, dev, gen, fix, check, test, db, db-down"

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
