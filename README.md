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

| Service     | Port(s)           | Description                   |
|-------------|-------------------|-------------------------------|
| Frontend    | 5173              | React + Vite dev server       |
| Backend API | 8000              | FastAPI + Swagger             |
| Postgres    | 5432              | PostgreSQL + TimescaleDB      |
| Redis       | 6379              | Redis cache & message broker  |

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
