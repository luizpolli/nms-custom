# ── Makefile for NMS_Custom ──────────────────────────────────────

.PHONY: up down test lint migrate migrate-stamp migrate-revision logs shell build restart helm-lint helm-template sim-device sim-syslog sim-telemetry

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

migrate: backend-migrate

# Mark existing DB as already at baseline (one-time, for envs upgraded from
# pre-alembic create_all). Skips applying baseline DDL on a populated schema.
migrate-stamp:
	docker compose exec $(APP) alembic stamp head

# Generate a new migration file from current ORM state. Usage:
#   make migrate-revision MSG="add foo column"
migrate-revision:
	docker compose exec $(APP) alembic revision --autogenerate -m "$(MSG)"

backend-test:
	cd backend && python -m pytest tests/ -v --tb=short

backend-lint:
	cd backend && ruff check app/ && mypy app/

lint: backend-lint frontend-lint

test: backend-test

# ── Infra ───────────────────────────────────────────────────────

helm-lint:
	helm lint helm/nms-custom

helm-template:
	helm template nms-custom helm/nms-custom >/tmp/nms-custom-rendered.yaml

# ── Mock lab traffic ─────────────────────────────────────────────

sim-device:
	python3 tools/simulators/mock_device.py ensure-device

sim-syslog:
	python3 tools/simulators/mock_device.py syslog --count $${COUNT:-10}

sim-telemetry:
	python3 tools/simulators/mock_device.py telemetry --count $${COUNT:-10}

sim-run:
	python3 tools/simulators/mock_device.py run --count $${COUNT:-10}

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
