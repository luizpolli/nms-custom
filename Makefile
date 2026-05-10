# ── Makefile for NMS_Custom ──────────────────────────────────────

.PHONY: up down test lint migrate logs shell build restart

APP := nms-app
PROJECT := nms-custom

# ── Docker Compose helpers ──────────────────────────────────────

up:
	docker compose up --build -d

down:
	docker compose down -v

restart:
	docker compose down
	docker compose up --build -d

logs:
	docker compose logs -f

shell:
	docker compose exec $(APP) bash

ps:
	docker compose ps

# ── Frontend ────────────────────────────────────────────────────

frontend-dev:
	cd frontend && npm run dev

frontend-build:
	cd frontend && npm run build

frontend-lint:
	cd frontend && npm run lint

# ── Backend ─────────────────────────────────────────────────────

backend-venv:
	cd backend && python3 -m venv .venv
	cd backend && . .venv/bin/activate && pip install -r requirements.txt

backend-migrate:
	docker compose exec $(APP) alembic upgrade head

backend-test:
	cd backend && python -m pytest tests/ -v --tb=short

backend-lint:
	cd backend && ruff check app/ && mypy app/

lint: backend-lint frontend-lint

test: backend-test

# ── Infra ───────────────────────────────────────────────────────

db-reset:
	docker compose down -v
	docker compose up -d postgres
	docker compose exec postgres pg_isready

redis-cli:
	docker compose exec redis redis-cli

# ── Misc ────────────────────────────────────────────────────────

clean:
	docker compose down -v
	rm -rf backend/__pycache__ backend/.pytest_cache backend/.mypy_cache
	rm -rf frontend/node_modules frontend/dist
	find . -type d -name '.venv' -exec rm -rf {} +

help:
	@echo "NMS_Custom Makefile targets:"
	@echo "  up             Build & start all services"
	@echo "  down           Stop & remove volumes"
	@echo "  restart        Full restart"
	@echo "  logs           Tail logs"
	@echo "  shell          Open backend shell"
	@echo "  test           Run backend tests"
	@echo "  lint           Run linters (ruff, mypy)"
	@echo "  migrate        Run DB migrations"
	@echo "  clean          Remove all generated data"
	@echo "  help           Show this help"
