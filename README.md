# NMS_Custom — Network Management System

A full-featured **Enterprise Network Management System** inspired by **Cisco EPNM / Prime Performance Manager / Prime Network**. Built for scalable device discovery, SNMP/SSH/telemetry monitoring, alarm correlation, service assurance, chassis visualization, and AI-assisted operations.

## Features

### Core Platform
- **Device Inventory** — CRUD management of network devices (routers, switches, firewalls, etc.) with OS version tracking, EPNM-style form layout, and CSV import/export
- **Credential Vault** — AES-256 encrypted credential storage with key rotation, per-profile type support (SNMP, SSH, HTTP, TL1, Netconf), live confirm-password validation
- **SNMP Engine** — Multi-MIB loading, OID resolution, and counter polling with MIB source provenance (SHA-256 checksums)
- **SSH Engine** — Async command execution and configuration backup with allowlist-enforced command runner
- **KPI Engine** — Maps SNMP counters to KPIs (CPU, memory, interfaces, QoS, etc.) with TimescaleDB time-series storage
- **Alarm Correlator** — Correlates SNMP traps and syslog events into actionable alarms with EPNM-style severity, saved filters, column visibility, datetime range, bulk operations, and acknowledgement attribution
- **Topology Builder** — Auto-discovers network topology via LLDP/CDP with interactive visualization
- **Discovery Engine** — Automated IP subnet discovery and device fingerprinting
- **Report Generation** — Excel/PDF export via openpyxl + reportlab with scheduled report workers
- **Real-time Dashboard** — KPI cards, charts, recent alarms, device status widgets via WebSocket
- **Dark/Light Theme** — Modern EPNM-inspired UI with theme toggle

### Chassis View
- **Interactive Front-Panel Diagrams** — Renders device chassis using real **EPNM SVG assets** merged with live ENTITY-MIB SNMP data
- **14 device profiles** across 4 platform families (see [Supported Chassis Profiles](#supported-chassis-profiles))
- **Alarm severity overlay** — Hotspots color-coded by worst alarm severity in real time
- **Port detail panel** — Slide-out panel with interface KPIs, description, and alarm list per physical port
- **Profile auto-detection** — Matches device model strings (case/dash-insensitive) from SNMP inventory data

### Assurance Engine
- **Health Scoring** — Per-device composite health scores from KPI thresholds
- **Root-Cause Groups** — Automatically correlates alarms into assurance groups with probable root cause
- **Blast-Radius Estimation** — Propagates impact scores through the service dependency graph

### Service Impact Modeling
- **Dependency Graph** — Declarative service-to-device/interface dependency model
- **Impact Propagation** — Computes affected services for any device or alarm event
- **Impact Alerts** — Surfaces affected service count in alarm and assurance views

### AI Ops
- **Advisory Endpoints** — Deterministic analysis of alarm groups, KPI anomalies, runbooks, and narrative summaries (no LLM required)
- **LLM Assistant** — Optional GPT-compatible assistant with strict guardrails: PII/secret redaction (IPs, MACs, FQDNs, SNMP communities, PEM keys), citation enforcement (`prefix:id`), retrieval-grounded responses, provider-agnostic adapter
- **`NullLLMProvider`** — Ships by default; LLM entirely disabled unless `AI_OPS_LLM_ENABLED=true`
- **Frontend `/ai-ops` page** — Advisory cards with citations + assistant chat form

### Event Bus
- **Redis Streams** — All ingest events flow through `nms:events` with canonical JSON envelope
- **Consumer Groups** — `XGROUP / XREADGROUP / XACK / XAUTOCLAIM` for at-least-once delivery
- **Worker fanout** — Alarm, discovery, and telemetry consumers process events independently
- **EPS visibility** — Lab Health dashboard shows real-time events-per-second per stream

### Telemetry Ingestion
- **gNMI-JSON / MDT-JSON** — Line-delimited JSON telemetry receiver on port 57400/tcp
- **Native gNMI proto contract** — `StubNativeGnmiAdapter` for lab-bound testing
- **Syslog receiver** — RFC 5425-compliant with configurable payload size cap (5514/udp)
- **SNMP trap receiver** — Data-driven severity classifier with vendor trap fixture library (1162/udp)

### Settings Administration
- **EPNM-style module settings** — Per-module toggle panels, persistent user preferences
- **RBAC** — Role-based access control with `API_KEY_ROLES` enforcement; Users & Roles management panel
- **Event Forwarding** — Configure outbound syslog/trap forwarding targets
- **MIB Management** — Upload, resolve, and provenance-track MIB files with SHA-256 integrity

### Security Hardening
- **Container hardening** — Docker Compose: non-root users, read-only filesystems, `cap_drop: ALL`, no new privileges; Helm: `securityContext` on all pod specs
- **Request body-size limits** — Per-route configurable caps via middleware (prevents oversized payload attacks)
- **MIB source provenance** — SHA-256 checksum + upload metadata stored with every MIB file
- **API key lifecycle** — Sliding-window rate limiting, key rotation procedures; see [`docs/API_KEY_MANAGEMENT.md`](docs/API_KEY_MANAGEMENT.md)
- **Fail-fast production guards** — Startup validation rejects unsafe `APP_ENV=production` defaults
- **Trusted Host middleware** — `ALLOWED_HOSTS` enforced; local defaults restricted to localhost/container names

### Test Coverage
- **Backend: 500+ tests** across 64 test files — API endpoints, workers, event bus, assurance, AI Ops, chassis detection, security regression suite
- **Frontend: 295+ tests** — Vitest + React Testing Library covering UI components, pages, alarm table, chassis detection, settings, telemetry, AI Ops
- **CI gates:** ruff lint, mypy (0 errors required), pytest, alembic migration check, frontend lint + typecheck, helm lint

---

## Supported Chassis Profiles

| Profile ID | Platform Family | Detection Keywords | EPNM SVG Assets |
|---|---|---|---|
| `asr903` | ASR 900 | `asr` + `903` | ✓ |
| `asr920` | ASR 900 | `asr` + `920` | ✓ |
| `asr9006` | ASR 9000 | `asr` + `9006` | ✓ |
| `asr9010` | ASR 9000 | `asr` + `9010` | ✓ |
| `ncs55a1` | NCS 5500 | `ncs55a1` (compact) | ✓ (44 hotspots) |
| `ncs560` | NCS 5600 | `ncs560` (compact) | ✓ (55 hotspots) |
| `ncs540` | NCS 540 | `ncs540` / `n540` | ✓ (33 hotspots) |
| `ncs540-12z16g` | NCS 540 | `ncs540-12z16g` | ✓ |
| `ncs540-12z20g` | NCS 540 | `ncs540-12z20g` | ✓ |
| `ncs540-16z4` | NCS 540 | `ncs540-16z4` | ✓ |
| `ncs540-28z4c` | NCS 540 | `ncs540-28z4c` | ✓ |
| `ncs540-fh-agg` | NCS 540 | `ncs540` + `fh-agg` | ✓ |
| `ncs540-fh-csr` | NCS 540 | `ncs540` + `fh-csr` | ✓ |
| `ncs540x-4z14g2q` | NCS 540X | `ncs540x` | ✓ |

Detection is case-insensitive and dash/underscore-insensitive. See [`docs/chassis-view.md`](docs/chassis-view.md) for the full developer guide.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Frontend (React + TS)               │
│  Inventory · Alarms · Topology · Chassis · AI Ops   │
│  Assurance · Telemetry · Lab Health · Settings       │
└────────────────────┬────────────────────────────────┘
                     │ REST + WebSocket
┌────────────────────▼────────────────────────────────┐
│              Backend (FastAPI + Python 3.12)         │
│  API layer · KPI engine · Assurance · AI Ops         │
│  Alarm correlator · Topology builder · Chassis view  │
└──────┬──────────────┬──────────────┬────────────────┘
       │              │              │
┌──────▼──────┐  ┌───▼───┐   ┌─────▼──────┐
│ PostgreSQL  │  │ Redis │   │ TimescaleDB│
│ + Alembic  │  │Streams│   │ (hypertable│
└─────────────┘  └───┬───┘   │ time-series│
                     │       └────────────┘
        ┌────────────┼──────────────────────┐
        │            │                      │
┌───────▼──┐  ┌──────▼──────┐   ┌──────────▼──────┐
│ worker-  │  │  worker-    │   │  worker-        │
│  alarm   │  │  telemetry  │   │  discovery/etc  │
└──────────┘  └─────────────┘   └─────────────────┘

Ingest pods: syslog-receiver · trap-receiver · telemetry-receiver
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full design document, [docs/FUNCTIONAL_MANUAL.md](docs/FUNCTIONAL_MANUAL.md) for the operator/function manual, and [docs/SECURITY_REVIEW.md](docs/SECURITY_REVIEW.md) for the current security posture and hardening checklist.

---

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

### Refreshing frontend dependencies (Docker)

The `frontend` Compose service keeps `node_modules` in an **anonymous volume**
(`- /app/node_modules` in `docker-compose.yml`) so the host bind-mount doesn't
clobber the container's installed packages. That volume is populated by
`npm install` the first time the container starts and then **persists across
`up`/`down`** — so when `frontend/package.json` gains a new dependency,
rebuilding the image alone is *not* enough: the stale volume shadows the image's
fresh `node_modules` and Vite fails with `Failed to resolve import "<pkg>"`.

After any change to frontend dependencies, refresh the volume with either:

```bash
# Quick: install the new deps straight into the running container's volume
docker compose exec frontend npm install
docker compose restart frontend          # let Vite re-optimize deps

# Clean: rebuild the image AND recreate the anonymous node_modules volume from it
docker compose up -d --build --renew-anon-volumes frontend
```

(Plain local `npm install` in `frontend/` already covers the non-Docker dev flow.)

---

## Services & Ports

| Service             | Port(s)        | Description                          | Exposure guidance |
|---------------------|----------------|--------------------------------------|-------------------|
| Frontend            | 5173           | React + Vite UI                      | expose through HTTPS/ingress only |
| Backend API         | 8000           | FastAPI + Swagger                    | require API auth outside local dev |
| Postgres            | 5432           | PostgreSQL + TimescaleDB             | do not expose beyond localhost/private network |
| Redis               | 6379           | Redis Streams + cache                | do not expose beyond localhost/private network |
| Syslog receiver     | 5514/udp       | RFC 5425 syslog ingestion with payload cap | allow-list trusted device/simulator subnets |
| SNMP trap receiver  | 1162/udp       | SNMPv2c traps (data-driven classifier) | allow-list trusted device/simulator subnets |
| Telemetry receiver  | 57400/tcp      | gNMI/MDT-like line-delimited JSON    | restrict to trusted collectors; native gNMI should use TLS/mTLS |
| Prometheus          | 9090           | Self-monitoring TSDB (monitoring profile) | internal only |
| Alertmanager        | 9093           | Alert routing (monitoring profile)    | internal only |
| Grafana             | 3000           | Dashboards (monitoring profile)       | put behind auth proxy if exposed |

The self-monitoring stack (Prometheus + Alertmanager + Grafana) lives in the
opt-in `monitoring` Compose profile. Start it with
`docker compose --profile monitoring up -d`. See
[docs/OBSERVABILITY.md](docs/OBSERVABILITY.md) for setup, alerts, dashboards,
and receiver configuration.

## Worker / Receiver Topology

Runtime is split out of the API container:

- `worker-poller` — monitoring policies, KPI sampling
- `worker-topology` — LLDP/CDP graph refresh
- `worker-report` — scheduled report generation
- `worker-alarm` — Redis Streams alarm event consumer
- `worker-discovery` — discovery event consumer + refresh fan-out
- `worker-telemetry` — telemetry event consumer + KPI fan-out
- `syslog-receiver`, `trap-receiver`, `telemetry-receiver` — UDP/TCP ingest pods

All event consumers use Redis Streams consumer groups (`XGROUP / XREADGROUP / XACK / XAUTOCLAIM`).

---

## Phases Shipped

| Phase | Highlights |
|---|---|
| **1–2** | Device/interface/KPI/alarm data model + runtime split (API vs workers/receivers) |
| **2.5** | Alembic baseline + worker heartbeat + `GET /api/system/health` |
| **3A–3E** | Event bus (Redis Streams) + canonical envelope + telemetry MVP (gNMI-JSON / MDT-JSON) |
| **4A–4F** | Alarm correlation, assurance groups, service impact scoring |
| **5A–5L** | Production hardening: Helm chart, CI gates, consumer groups, simulators, lab health UI, EPS visibility, vendor trap fixtures + classifier |
| **5M** | Native gNMI proto contract + `StubNativeGnmiAdapter` (lab-bound) |
| **6A–6B** | Deterministic AI advisory endpoints: alarm groups, KPI anomalies, runbooks, narrative |
| **6C** | LLM-backed assistant with redaction, citation enforcement, retrieval-grounded, provider-agnostic; `NullLLMProvider` default; `/ai-ops` frontend page |
| **6D (Chassis Fase 1–6)** | Chassis view: 14 profiles, real EPNM SVG assets, alarm overlay, port detail panel, detection tests, developer docs |
| **P1.5** | Settings refactor: extracted `UsersRolesPanel`, shared helpers/constants |
| **P1.6** | Observability: log last silent `except Exception` sites |
| **P1.7** | mypy type coverage: 220 → 0 errors; mypy promoted to required CI gate |
| **P2.1** | Body-size limit middleware with per-route caps |
| **P2.2** | MIB source provenance (SHA-256 checksum + upload metadata) |
| **P2.3** | Secret manager examples + integration guide ([`docs/SECRET_MANAGER_EXAMPLES.md`](docs/SECRET_MANAGER_EXAMPLES.md)) |
| **Security** | Docker Compose + Helm hardening (non-root, read-only FS, cap_drop); API key lifecycle docs; sliding-window rate limiting; security regression test suite |

See [docs/NMS_ARCHITECTURE_EXECUTION_PLAN.md](docs/NMS_ARCHITECTURE_EXECUTION_PLAN.md) for the full per-phase execution log.

---

## Test Coverage

| Layer | Test Files | Tests | Notes |
|---|---|---|---|
| Backend (pytest) | 64 | 505 | API endpoints, workers, event bus, assurance, chassis detection, AI Ops, security regression |
| Frontend (Vitest + RTL) | 30 | 299 | Components, pages, alarm table, chassis detection, settings panels, AI Ops |

**CI pipeline (GitHub Actions):**
- `ruff check` — Python lint (hard gate)
- `mypy` — type checking, 0 errors required (hard gate since P1.7)
- `pytest` — backend tests with PostgreSQL + TimescaleDB service
- `alembic upgrade head` — migration chain validation
- Frontend `eslint` + `tsc --noEmit` — TypeScript typecheck
- `helm lint` — Kubernetes chart validation

---

## Load Testing

Use the standalone [`nms-traffic-sim`](https://github.com/kapy024/nms-traffic-sim) project to drive synthetic syslog / SNMP traps / event-bus NDJSON / gNMI-JSON telemetry without real hardware.

Baseline (2026-05-18, single laptop, all services in Compose):

| Mode    | Composition                                  | Duration | Frames sent | Events through `nms:events` | Effective EPS | Consumer lag |
|---------|----------------------------------------------|---------:|------------:|----------------------------:|--------------:|-------------:|
| syslog  | 500 EPS UDP syslog                           | 20s      | 10,000      | +9,895                      | ~495          | 0            |
| mixed   | 300 EPS syslog + 100 EPS traps + 100 fps tel | 65s      | 24,000+     | +23,655                     | ~364          | 0 (3 pending)|

The three consumer groups (`nms:worker-alarm`, `nms:worker-discovery`, `nms:worker-telemetry`) drained to 0 lag within seconds of each burst ending. Use `XINFO GROUPS nms:events` field `entries-read` for true throughput counts.

---

## Security Quick Checklist

Local defaults are intentionally convenient for development. Before using a shared lab or production-like host:

- Set `APP_ENV=production`, `DEBUG=false`, `API_AUTH_ENABLED=true`, strong `API_KEYS`, and least-privilege `API_KEY_ROLES` — startup validation will reject unsafe defaults.
- Replace `SECRET_KEY`, Postgres password, credential encryption material, and `SNMP_DEFAULT_COMMUNITY`; never deploy `public` as a default community.
- Use explicit `CORS_ORIGINS` / `ALLOWED_HOSTS` and real TLS cert/key files.
- Keep Postgres/Redis off untrusted networks; restrict syslog/trap/telemetry receiver ports with firewall rules or NetworkPolicies.
- Container hardening is already applied in Docker Compose and Helm: non-root users, read-only filesystems, `cap_drop: ALL`, no new privileges.
- MIB uploads are integrity-tracked: SHA-256 checksum and upload metadata stored at ingest time.
- Keep AI Ops LLM disabled (`AI_OPS_LLM_ENABLED` defaults to `false`) until retention/egress review is complete.

**Security docs:**
- [docs/SECURITY_REVIEW.md](docs/SECURITY_REVIEW.md) — full security posture and hardening checklist
- [docs/API_KEY_MANAGEMENT.md](docs/API_KEY_MANAGEMENT.md) — API key lifecycle and rotation guide
- [docs/OS_HARDENING_GUIDE.md](docs/OS_HARDENING_GUIDE.md) — OS-level hardening for deployment hosts
- [docs/SECRET_MANAGER_EXAMPLES.md](docs/SECRET_MANAGER_EXAMPLES.md) — Vault/AWS Secrets Manager integration examples

---

## Functional Manual

The detailed module-by-module operating guide lives in [docs/FUNCTIONAL_MANUAL.md](docs/FUNCTIONAL_MANUAL.md). It covers inventory, credential vault, SNMP/KPI polling, MIB uploads, alarms, assurance/service impact, topology, discovery, SSH command execution, reporting, telemetry/gNMI, workers/event bus, Lab Health, AI Ops, chassis view, settings, and deployment modes.

---

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

---

## License

MIT
