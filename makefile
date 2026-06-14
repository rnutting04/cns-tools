.PHONY: dev seed migrate reset stop logs ps install test test-backend test-frontend help

dev:
	docker compose up -d
	cd backend && venv/bin/python -m uvicorn app.main:app --reload --port 8000

seed:
	./scripts/seed.sh

migrate:
	cd backend && alembic upgrade head

reset:
	./scripts/reset.sh

stop:
	docker compose down

logs:
	docker compose logs -f

ps:
	docker compose ps

install:
	cd backend && pip install -r requirements.txt

# Backend tests need Postgres + MinIO running (make dev / docker compose up -d).
test-backend:
	cd backend && venv/bin/python -m pytest

test-frontend:
	cd frontend && npm test

test: test-backend test-frontend

help:
	@echo "Available commands:"
	@echo "  make dev           - start docker + uvicorn"
	@echo "  make seed          - seed the database"
	@echo "  make migrate       - run alembic migrations"
	@echo "  make reset         - nuke and rebuild local DB"
	@echo "  make stop          - stop docker containers"
	@echo "  make logs          - tail docker logs"
	@echo "  make ps            - show container status"
	@echo "  make install       - install python dependencies"
	@echo "  make test          - run backend + frontend test suites"
	@echo "  make test-backend  - run backend pytest (needs docker services up)"
	@echo "  make test-frontend - run frontend vitest"