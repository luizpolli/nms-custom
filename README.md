# NMS_Custom — Network Management System

A full-featured **Network Management System** inspired by **Cisco Prime Performance Manager** and **Cisco Prime Network**. Built for scalable device discovery, SNMP monitoring, alarm correlation, topology mapping, and KPI-based performance management.

## Features

- **Device Inventory** — CRUD management of network devices (routers, switches, firewalls, etc.)
- **Credential Vault** — AES-256 encrypted credential storage with key rotation
- **SNMP Engine** — Multi-MIB loading, OID resolution, and counter polling
- **SSH Engine** — Async command execution and configuration backup
- **KPI Engine** — Maps SNMP counters to KPIs (CPU, memory, interfaces, QoS, etc.)
- **Alarm Correlator** — Correlates SNMP traps into actionable alarms
- **Topology Builder** — Auto-discovers network topology via LLDP/CDP
- **IOS Version Management** — Track and report device IOS/software versions
- **Report Generation** — Excel/PDF export via openpyxl + reportlab
- **Discovery Engine** — Automated IP subnet discovery and device fingerprinting
- **Real-time Dashboard** — KPI cards, charts, WebSocket updates
- **Dark/Light Theme** — Modern UI with theme toggle

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Frontend   │────▶│   Backend    │────▶│   Devices   │
│ (React + TS) │     │ (FastAPI)    │     │   (SNMP/SSH)│
└─────────────┘     └──────┬───────┘     └─────────────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
        ┌─────▼─────┐ ┌──▼───┐ ┌─────▼─────┐
        │  PostgreSQL│ │Redis │ │ Timescale │
        │  + Timescale││     │ │  Extension│
        └────────────┘ └──────┘ └───────────┘
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full design document.

## Quick Start

### Prerequisites

- Docker & Docker Compose v2+
- Python 3.12+ (for local development)

### Run with Docker

```bash
# Copy env file and configure
cp .env.example .env

# Start all services
make up

# Or manually
docker compose up --build -d
```

### Local Development

```bash
# Backend
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) (frontend) and
[http://localhost:8000/docs](http://localhost:8000/docs) (Swagger API docs).

## Services & Ports

| Service             | Port(s)        | Description                          |
|---------------------|----------------|--------------------------------------|
| Frontend            | 5173           | React + Vite dev server              |
| Backend API         | 8000           | FastAPI + Swagger                    |
| Postgres            | 5432           | PostgreSQL + TimescaleDB             |
| Redis               | 6379           | Redis Streams + cache                |
| Syslog receiver     | 5514/udp       | Cisco-ish syslog ingestion           |
| SNMP trap receiver  | 1162/udp       | SNMPv2c traps (data-driven classifier) |
| Telemetry receiver  | 57400/tcp      | gNMI/MDT-like line-delimited JSON    |

## Worker / receiver topology

Runtime is split out of the API container:

- `worker-poller` — monitoring policies, KPI sampling
- `worker-topology` — LLDP/CDP graph refresh
- `worker-report` — scheduled report generation
- `worker-alarm` — Redis Streams alarm event consumer
- `worker-discovery` — discovery event consumer + refresh fan-out
- `worker-telemetry` — telemetry event consumer + KPI fan-out
- `syslog-receiver`, `trap-receiver`, `telemetry-receiver` — UDP/TCP ingest pods

All event consumers use Redis Streams consumer groups (`XGROUP / XREADGROUP / XACK / XAUTOCLAIM`).

## Phases shipped (highlights)

- **Phase 1–2**: device/interface/KPI/alarm data model + runtime split (API vs workers/receivers).
- **Phase 2.5**: Alembic baseline + worker heartbeat + `GET /api/system/health`.
- **Phase 3A–3E**: event bus (Redis Streams) + canonical envelope + telemetry MVP (gNMI-JSON / MDT-JSON / JSON).
- **Phase 4A–4F**: alarm correlation, assurance groups, service impact scoring.
- **Phase 5A–5L**: production hardening (Helm chart, CI, consumer groups, simulators, lab health UI, EPS visibility, vendor trap fixtures + classifier).
- **Phase 5M**: native gNMI proto contract + `StubNativeGnmiAdapter` (lab-bound).
- **Phase 6A–6C**: AI-assisted operations.
  - 6A/6B: deterministic advisory endpoints (alarm groups, KPI anomalies, runbooks, narrative).
  - **6C**: LLM-backed assistant with strict guardrails — redaction (IPs, MACs, FQDNs, secrets, SNMP community, PEM keys), citation enforcement (`prefix:id`), retrieval-grounded, provider-agnostic. Ships a deterministic `NullLLMProvider`; LLM disabled by default behind `AI_OPS_LLM_ENABLED`.
  - Frontend: `/ai-ops` page exposes the assistant form + advisory cards with citations.

See [docs/NMS_ARCHITECTURE_EXECUTION_PLAN.md](docs/NMS_ARCHITECTURE_EXECUTION_PLAN.md) for the full per-phase log.

## Load testing

Use the standalone [`nms-traffic-sim`](https://github.com/kapy024/nms-traffic-sim) project to drive synthetic syslog / SNMP traps / event-bus NDJSON / gNMI-JSON telemetry against the ingestion path without real hardware.

Baseline (2026-05-18, single laptop, all services in Compose):

| Stream  | Target EPS | Sent  | Duration | Stream growth | Consumer lag |
|---------|-----------:|------:|---------:|--------------:|-------------:|
| syslog  | 500        | 10000 | 20s      | +9895 events  | 0            |

The three consumer groups (`nms:worker-alarm`, `nms:worker-discovery`, `nms:worker-telemetry`) drained to 0 lag within seconds of the burst ending.

## Makefile Commands

```bash
make up          # Start all services
make down        # Stop all services
make test        # Run backend tests
make lint        # Run ruff + mypy
make migrate     # Run DB migrations
make logs        # Tail docker compose logs
make shell       # Open backend shell
```

## License

MIT
