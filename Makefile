.PHONY: db-up db-down dev docker-build docker-run test

TEST_DATABASE_URL ?= postgresql+psycopg://ainews:ainews@localhost:5433/ainews_test

db-up:
	docker compose up -d --wait postgres

db-down:
	docker compose down

dev: db-up
	uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

docker-build:
	docker build -t ainews .

docker-run:
	docker run --rm --env-file .env -p 8000:8000 ainews

test:
	@set -e; \
		docker compose up -d --wait postgres-test; \
		trap 'docker compose stop postgres-test' EXIT; \
		TEST_DATABASE_URL=$(TEST_DATABASE_URL) uv run pytest
