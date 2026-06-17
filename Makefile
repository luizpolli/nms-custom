# ── Makefile for NMS_Custom ──────────────────────────────────────

.PHONY: up down test lint migrate migrate-stamp migrate-revision logs shell build restart helm-lint helm-template sim-device sim-syslog sim-trap sim-telemetry backup restore airgap-prepare airgap-install

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

sim-trap:
	python3 tools/simulators/mock_device.py trap --count $${COUNT:-10}

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

# ── Backup / Restore ────────────────────────────────────────────

# Full backup: PostgreSQL (custom format) + Redis RDB → ./backups/TIMESTAMP/
# Options (pass via env or ARGS):
#   BACKUP_DIR=./backups   override output directory
#   ARGS="--volumes"       also archive Docker volumes
backup:
	bash scripts/backup.sh $(if $(BACKUP_DIR),--dir $(BACKUP_DIR),) $(ARGS)

# Restore from a backup directory produced by 'make backup'.
# Usage:   make restore BACKUP_DIR=./backups/20260616_143000
restore:
	bash scripts/restore.sh --dir $(BACKUP_DIR) $(ARGS)

# ── Air-gap packaging ────────────────────────────────────────────

# Package NMS_Custom + nms-traffic-sim for deployment on an offline server.
# Produces dist/airgap/nms_airgap_TIMESTAMP.tar.gz
# Options (pass via ARGS):
#   ARGS="--skip-sim"       skip nms-traffic-sim packaging
#   ARGS="--skip-images"    skip Docker image export
#   ARGS="--sim-dir PATH"   path to nms-traffic-sim (default: ../nms-traffic-sim)
airgap-prepare:
	bash scripts/airgap-prepare.sh $(ARGS)

# Show the contents of the air-gap install script (informational).
airgap-install:
	@echo "Transfer the bundle produced by 'make airgap-prepare' to the target server, then:"
	@echo "  tar xzf nms_airgap_*.tar.gz"
	@echo "  chmod +x airgap-install.sh"
	@echo "  ./airgap-install.sh"
	@echo ""
	@echo "The installer script is: scripts/airgap-install.sh"

# ── Misc ────────────────────────────────────────────────────────

clean:
	docker compose down -v
	rm -rf backend/__pycache__ backend/.pytest_cache backend/.mypy_cache
	rm -rf frontend/node_modules frontend/dist
	find . -type d -name '.venv' -exec rm -rf {} +

help:
	@echo "NMS_Custom Makefile targets:"
	@echo ""
	@echo "  Stack"
	@echo "    up              Build & start all services"
	@echo "    down            Stop & remove volumes"
	@echo "    restart         Full restart"
	@echo "    logs            Tail logs"
	@echo "    shell           Open backend shell"
	@echo "    ps              Show container status"
	@echo ""
	@echo "  Development"
	@echo "    test            Run backend tests"
	@echo "    lint            Run linters (ruff, mypy, eslint)"
	@echo "    migrate         Run DB migrations (alembic upgrade head)"
	@echo "    migrate-stamp   Mark DB as at current head (no DDL)"
	@echo "    migrate-revision MSG=...  Generate migration from ORM"
	@echo "    frontend-dev    Start Vite dev server"
	@echo "    frontend-build  Build production frontend"
	@echo ""
	@echo "  Simulators"
	@echo "    sim-device      Ensure mock device exists"
	@echo "    sim-syslog      Send COUNT syslog messages"
	@echo "    sim-trap        Send COUNT SNMP traps"
	@echo "    sim-telemetry   Send COUNT telemetry updates"
	@echo "    sim-run         Run full simulation cycle"
	@echo ""
	@echo "  Backup / Restore"
	@echo "    backup          Dump PostgreSQL + Redis to ./backups/TIMESTAMP/"
	@echo "                    Optional: BACKUP_DIR=path ARGS='--volumes'"
	@echo "    restore         Restore from backup dir"
	@echo "                    Required: BACKUP_DIR=./backups/TIMESTAMP"
	@echo ""
	@echo "  Air-gap Deployment"
	@echo "    airgap-prepare  Package everything for offline install"
	@echo "                    Optional: ARGS='--skip-sim --skip-images'"
	@echo "    airgap-install  Show install instructions for target server"
	@echo ""
	@echo "  Misc"
	@echo "    clean           Remove all generated data"
	@echo "    help            Show this help"
