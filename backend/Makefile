.DEFAULT_GOAL := help

.PHONY: help setup dev fix check test \
	db-prod db-prod-down db-dev db-dev-down \
	db-revision db-upgrade db-downgrade db-current db-heads \
	db-migration-check

help:
	@echo "App: setup, dev, fix, check, test"
	@echo "Docker: db-dev, db-dev-down, db-prod, db-prod-down"
	@echo 'Migrations: db-revision message="...", db-upgrade, db-downgrade, db-current, db-heads'
	@echo "CI gate: db-migration-check (Alembic chain vs origin/main)"
	@echo ""
	@echo "From repo root: make -C backend db-upgrade"
	@echo "                make -C backend db-migration-check"

setup:
	uv sync --locked
	uv run pre-commit install --config ../.pre-commit-config.yaml

dev:
	uv run --locked fastapi dev app/main.py

fix:
	uv run --locked ruff check --fix .
	uv run --locked ruff format .

check:
	uv run --locked ruff check .
	uv run --locked ruff format --check .
	$(MAKE) db-migration-check
	uv run --locked pytest tests/api tests/migration_check -q

test:
	uv run --locked pytest tests/api -q

db-prod:
	docker-compose -f ../devops/prod/docker-compose.db.yml up

db-prod-down:
	docker-compose -f ../devops/prod/docker-compose.db.yml down

db-dev:
	docker-compose -f ../devops/dev/docker-compose.db.yml up

db-dev-down:
	docker-compose -f ../devops/dev/docker-compose.db.yml down

db-revision:
	@test -n "$(message)" || { echo 'Usage: make db-revision message="description"' >&2; exit 2; }
	uv run --locked alembic revision --autogenerate -m "$(message)"

db-upgrade:
	uv run --locked alembic upgrade head

db-downgrade:
	uv run --locked alembic downgrade -1

db-current:
	uv run --locked alembic current

db-heads:
	uv run --locked alembic heads

db-migration-check:
	git fetch origin main
	uv run --locked scripts/check_migrations_align_with_main.py --base origin/main
