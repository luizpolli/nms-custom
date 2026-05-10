# NMS_Custom — Architecture Document

## Table of Contents

1. [Overview](#overview)
2. [System Architecture](#system-architecture)
3. [Technology Stack](#technology-stack)
4. [Component Design](#component-design)
5. [Data Models](#data-models)
6. [Data Flow](#data-flow)
7. [SNMP Engine](#snmp-engine)
8. [SSH Engine](#ssh-engine)
9. [KPI Engine](#kpi-engine)
10. [Alarm Correlator](#alarm-correlator)
11. [Discovery Engine](#discovery-engine)
12. [Topology Builder](#topology-builder)
13. [Credential Vault](#credential-vault)
14. [Worker Pool](#worker-pool)
15. [Frontend Architecture](#frontend-architecture)
16. [Infrastructure](#infrastructure)
17. [Security Considerations](#security-considerations)
18. [Scalability & Performance](#scalability--performance)
19. [Future Enhancements](#future-enhancements)

---

## Overview

NMS_Custom is a self-hosted Network Management System inspired by **Cisco Prime Performance Manager** and **Cisco Prime Network**. It provides:

- **Device inventory** with full CRUD
- **SNMP-based monitoring** with multi-MIB support
- **KPI calculation** from SNMP counters
- **Alarm correlation** for SNMP traps
- **Network topology discovery** via LLDP/CDP
- **Configuration backup** via SSH
- **Real-time dashboard** with WebSocket updates
- **Report generation** (Excel/PDF)
- **IOS version tracking**

Designed for small-to-medium networks (10–5,000 devices) with a modular, extensible architecture.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (React 18)                  │
│  Dashboard │ Devices │ Credentials │ Topology │ Alarms  │
│  Performance │ MIBs │ Commands │ IOS │ Reports │ Settings│
└──────────────────────────────┬──────────────────────────┘
                               │ REST API + WebSocket
┌──────────────────────────────▼──────────────────────────┐
│                  Backend (FastAPI)                      │
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐ │
│  │ Devices  │  │ KPI      │  │ Alarm    │  │ Report │ │
│  │ API      │  │ Engine   │  │ Corr.    │  │ Gen.   │ │
│  └──────────┘  └──────────┘  └──────────┘  └────────┘ │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐ │
│  │ SNMP     │  │ SSH      │  │ Discovery│  │ Topology│ │
│  │ Engine   │  │ Engine   │  │ Engine   │  │ Builder │ │
│  └──────────┘  └──────────┘  └──────────┘  └────────┘ │
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│  │ Worker:  │  │ Worker:  │  │ Worker:  │             │
│  │ Poller   │  │ Discovery│  │ Alarm    │             │
│  └──────────┘  └──────────┘  └──────────┘             │
└──────────┬───────────┬────────────┬────────────────────┘
           │           │            │
     ┌─────▼───┐  ┌───▼────┐  ┌───▼──────────┐
     │Postgres │  │Redis   │  │ Timescale DB │
     │ +       │  │Queue   │  │ (Time-Series │
     │Timescale│  │Cache   │  │  for KPIs)   │
     └─────────┘  └────────┘  └──────────────┘
```

---

## Technology Stack

| Layer         | Technology                                |
|---------------|-------------------------------------------|
| Backend API   | FastAPI (Python 3.12), Pydantic v2        |
| Database      | PostgreSQL 16 + TimescaleDB extension     |
| Cache/Queue   | Redis 7 (Queues, Pub/Sub, Cache)          |
| SNMP          | pysnmp-lextudio (asynchronous)            |
| SSH           | asyncssh                                   |
| ORM           | SQLAlchemy 2.0 (async)                    |
| KPI Data      | TimescaleDB hypertables                    |
| MIB Parsing   | Custom parser + pysnmp MIB compiler        |
| Encryption    | Fernet (cryptography library), AES-256     |
| Reports       | openpyxl + reportlab                       |
| Frontend      | React 18 + TypeScript + Vite               |
| State Mgmt    | Zustand                                    |
| Charts        | Recharts                                   |
| HTTP Client   | axios                                      |
| Real-time     | WebSocket (FastAPI + native WS client)     |
| Task Queue    | Redis Streams + asyncio workers            |
| Container     | Docker Compose                             |

---

## Component Design

### 1. Models Layer (`app/models/`)

SQLAlchemy 2.0 async models representing all database tables:

- **Device** — Core device record (name, IP, type, model, vendor, status, tags)
- **Credential** — Encrypted credentials (hostname, username, auth_key, enc_key)
- **Inventory** — Hardware/software details (interfaces, ports, memory, CPU cores, serial, firmware)
- **KPI** — Time-series KPI data (kpi_type, technology, value, timestamp)
- **MIB** — Uploaded/custom MIB file metadata (path, oid_root, description)
- **Command** — Saved CLI commands per device (name, device_id, cli_command, output_path)
- **IOSVersion** — Software version tracking (device_id, image_file, version, platform)
- **TopologyNode** — Network topology node (node_id, device_id, role, position)
- **TopologyLink** — Topology link/edge (source_node_id, target_node_id, source_iface, target_iface)
- **Alarm** — Alarm record (source_device, alarm_type, severity, message, timestamp, status, correlation_id)
- **Report** — Generated report metadata (type, status, file_path, created_by, format)

### 2. Schemas Layer (`app/schemas/`)

Pydantic v2 models for request/response validation, all with `from_attributes=True` for SQLAlchemy compatibility.

### 3. API Layer (`app/api/`)

FastAPI routers with dependency injection:

| Router        | Endpoints                                              |
|---------------|--------------------------------------------------------|
| devices       | GET/POST/GET{id}/PUT/DELETE/{id}/search/status/search  |
| credentials   | GET/POST/PUT/DELETE + encrypt/decrypt helpers          |
| performance   | GET KPIs, POST bulk KPI ingest, GET history            |
| mibs          | GET/POST/PUT/DELETE MIBs + upload + OID resolution     |
| discovery     | POST start discovery, GET status                       |
| commands      | GET/POST/PUT/DELETE commands + EXECUTE command          |
| ios           | GET/POST/PUT/DELETE IOS versions + extract             |
| topology      | GET/POST topology nodes/links + refresh                |
| alarms        | GET/PUT alarms + acknowledge/clear + correlation view  |
| reports       | GET/POST reports + download + templates                |
| health        | GET health, GET metrics (Prometheus text)              |

### 4. Services Layer (`app/services/`)

#### SNMP Engine (`snmp_engine.py`)
- Async polling via pysnmp
- Multi-MIB loading: built-in + user-uploaded MIBs
- OID resolution (numeric → symbolic)
- BulkGET for efficient counter polling
- Trap receiving listener
- Timeout and retry configuration per-device

#### SSH Engine (`ssh_engine.py`)
- `asyncssh` connection pool per device credential
- Command execution with timeout
- Config backup (copy running-config/startup-config)
- File upload/download (TFTP/SCP helper)
- Auto-detect device type from banner/hostname

#### Crypto Service (`crypto.py`)
- Fernet-based AES-256-CBC credential encryption
- Encryption key rotation (v1, v2 keys)
- Automatic decryption on read
- Key derivation from environment variable

#### KPI Engine (`kpi_engine.py`)
- Maps SNMP counters → KPIs via schema:
  - Technology, KPI Area, KPI Name, Counters (OIDs), Schema (calc), Type (gauge/counter), Description, Formula
- Supports: CPU utilization, memory usage, interface utilization, packet drops, QoS drops, latency
- Aggregates counters with delta calculation
- Writes to TimescaleDB hypertables

#### Alarm Correlator (`alarm_correlator.py`)
- Processes incoming SNMP traps (linkDown, linkUp, coldStart, cpqRaid, etc.)
- Correlation rules engine (dedup, suppress, escalation)
- Alarm states: new → in_progress → acknowledged → resolved → closed
- Correlation window (configurable, default 5 min)

#### Topology Builder (`topology_builder.py`)
- LLDP/CDP neighbor discovery polling
- Builds undirected graph of device → neighbor relationships
- Stores nodes and links in topology tables
- Graph refresh trigger

#### Discovery Engine (`discovery_engine.py`)
- CIDR-based IP range scanning
- SNMP fingerprinting (sysObjectID → vendor/device)
- Port scanning for SSH (22), HTTP (80/443), NETCONF (830)
- Results in Device + Inventory records

#### Config Backup (`config_backup.py`)
- Scheduled config backup via SSH
- Delta detection (diff against previous version)
- Config archive storage (S3 or local)

#### IOS Extractor (`ios_extractor.py`)
- Auto-extract IOS version via SSH (show version)
- Manual upload (upload .bin file)
- Track version, image file, platform, uptime
- Alert on EOL/EOS IOS versions

### 5. Workers Layer (`app/workers/`)

Asyncio-based workers using Redis queues:

| Worker         | Interval | Description                           |
|----------------|----------|---------------------------------------|
| poller         | 60s      | Poll devices via SNMP, compute KPIs   |
| discovery      | 3600s    | Scan subnets for new devices          |
| alarm          | 30s      | Process pending alarms, correlation   |
| report         | On-demand| Generate scheduled reports              |

Workers run as asyncio tasks with a supervisor loop. Redis pub/sub for inter-worker communication.

### 6. Utils Layer (`app/utils/`)

- **logger.py** — Structured JSON logging (loguru + rich console output in dev)
- **helpers.py** — Common utilities (IP validation, SNMP community validation, time formatting)

---

## Data Models

### Device

```sql
CREATE TABLE devices (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name          VARCHAR(255) NOT NULL,
    ip_address    INET NOT NULL,
    device_type   VARCHAR(50) NOT NULL,        -- router, switch, firewall, server
    model         VARCHAR(255),
    vendor        VARCHAR(100),
    os_type       VARCHAR(100),                -- IOS, NX-OS, Junos, etc.
    status        VARCHAR(20) DEFAULT 'unknown', -- up, down, unknown
    location      VARCHAR(255),
    tags          TEXT[] DEFAULT '{}',
    credential_id UUID REFERENCES credentials(id),
    created_at    TIMESTAMPTZ DEFAULT now(),
    updated_at    TIMESTAMPTZ DEFAULT now(),
    UNIQUE(ip_address)
);
```

### KPI (TimescaleDB hypertable)

```sql
SELECT create_hypertable('kpis', 'timestamp');

CREATE TABLE kpis (
    id           BIGSERIAL,
    device_id    UUID REFERENCES devices(id),
    kpi_type     VARCHAR(50) NOT NULL,        -- cpu, memory, interface_utilization
    technology   VARCHAR(50),                 -- routing, switching, security
    value        DOUBLE PRECISION NOT NULL,
    unit         VARCHAR(20),                 -- percent, bytes, msec
    kpi_area     VARCHAR(50),                 -- performance, security, availability
    metadata     JSONB,
    timestamp    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (id, timestamp)
);
```

### Credential

```sql
CREATE TABLE credentials (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(255) NOT NULL,
    hostname    VARCHAR(255) NOT NULL,
    username    TEXT NOT NULL,
    auth_key    TEXT NOT NULL,                -- Fernet-encrypted
    enc_key     TEXT,                         -- Fernet-encrypted
    protocol    VARCHAR(10) DEFAULT 'snmp',   -- snmp, ssh, netconf
    snmp_version VARCHAR(5) DEFAULT 'v2c',    -- v1, v2c, v3
    port        INTEGER DEFAULT 161,
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now()
);
```

---

## Data Flow

### SNMP Polling Flow

```
poller worker
    │
    ├── 1. Fetch all "up" devices from DB
    ├── 2. For each device:
    │       ├── SNMP GET bulk (interface counters, sysStats)
    │       ├── SNMP GET (memory, CPU)
    │       └── KPI Engine maps counters → KPIs
    ├── 3. Calculate deltas (delta = current_value - previous_value)
    ├── 4. Store KPIs in TimescaleDB
    └── 5. Publish KPI update via Redis pub/sub → WebSocket → Frontend
```

### Alarm Flow

```
SNMP Trap Listener (async)
    │
    ├── Parse trap (OID, OID-value pairs, source IP)
    ├── Map OID → Alarm Type (MIB tables)
    ├── Alarm Correlator:
    │       ├── Deduplicate (same source + type within 5 min)
    │       ├── Suppress (if acknowledged within 30 min)
    │       └── Escalate (if no resolution within SLA)
    ├── Store in alarms table
    └── Publish via WebSocket → Alarm Panel updates in real-time
```

### Topology Discovery Flow

```
topology_builder worker
    │
    ├── 1. Fetch all devices with SNMP credentials
    ├── 2. For each device:
    │       ├── SNMP GET LLDP-MIB (lldpLocalPortTable, lldpRemTable)
    │       └── SNMP GET CDP-MIB (cdpCacheTable)
    ├── 3. Build adjacency graph
    ├── 4. Compare with existing topology
    ├── 5. Diff → update topology nodes & links
    └── 6. Publish via WebSocket → TopologyMap re-renders
```

---

## SNMP Engine

The SNMP engine is the heart of the monitoring system.

### Features

1. **Multi-protocol**: SNMPv1, SNMPv2c, SNMPv3 (authPriv)
2. **Multi-MIB**: Built-in MIBs (RFC1213, IF-MIB, CISCO-SYS-MIB) + user-uploaded custom MIBs
3. **OID resolution**: Maps numeric OIDs to symbolic names via loaded MIBs
4. **BulkGET**: Efficient polling of many OIDs in single request
5. **Counter delta**: Automatic delta calculation for counter-type OIDs
6. **Timeout/retry**: Per-device configurable timeout (default 5s) and retries (default 3)
7. **Trap listener**: Async SNMP trap receiver on configurable port

### MIB Loading

```python
# Built-in MIBs
BUILTIN_MIBS = ["RFC1213-MIB", "IF-MIB", "CISCO-SYS-MIB", "CISCO-ENTITY-EXT-MIB"]

# Custom MIBs uploaded via API → stored in MIB table
# Loaded on-demand into pysnmp MIB compiler
```

### Counter KPI Mapping

| KPI Area    | KPI Name              | Technology | Counters                                      | Formula                                  |
|-------------|----------------------|------------|-----------------------------------------------|------------------------------------------|
| Performance | CPU Utilization       | routing    | ciscoSSCpuTotal                               | (1 - idle/total) × 100                   |
| Performance | Memory Utilization    | switching  | memMemoryFree                                   | (1 - free/total) × 100                   |
| Performance | Interface Utilization | switching  | ifInOctets, ifOutOctets                         | (delta_in + delta_out) × 8 / speed × 100 |
| Performance | Packet Drops          | routing    | ifInDiscards, ifOutDiscards                     | delta_drops / delta_packets × 100         |
| Security    | ACL Hits              | security   | ciscoASAMHits                                  | delta_hits per interval                    |
| Availability| Link Up/Down         | switching  | ifAdminStatus, ifOperStatus                     | time_up / time_total × 100               |

---

## SSH Engine

- `asyncssh` connection pool (one connection per device credential, reused)
- Command execution with configurable timeout (default 30s)
- Output captured to files (base64 encoded for DB storage)
- Config backup via `copy running-config tftp://` / `copy running-config startup-config`
- SSH key-based auth support

---

## KPI Engine

The KPI engine transforms raw SNMP counters into actionable KPIs:

```python
# KPI schema entry
kpi_schema = {
    "technology": "switching",
    "kpi_area": "performance",
    "kpi_name": "Interface Utilization",
    "counters": ["ifInOctets", "ifOutOctets"],
    "schema": "delta",
    "type": "counter",
    "description": "Percentage of bandwidth utilization",
    "formula": "(delta_in + delta_out) * 8 / speed * 100",
    "unit": "%",
    "threshold": {"warning": 70, "critical": 90}
}
```

---

## Alarm Correlator

Inspired by Cisco Prime Network's alarm management:

### Alarm Types

| Alarm Type     | SNMP Trap OID                        | Severity  |
|---------------|--------------------------------------|-----------|
| linkDown      | IF-MIB::linkDown                     | critical  |
| linkUp        | IF-MIB::linkUp                       | info      |
| coldStart     | IF-MIB::coldStart                    | warning   |
| warmStart     | IF-MIB::warmStart                    | info      |
| cpuThreshold  | CISCO-SYS-MIB::cpqHeCpuThreshold     | critical  |
| memoryThreshold| CISCO-SYS-MIB::cpqHeMemThreshold    | critical  |
| diskFailure   | CISCO-SYS-MIB::cpqHeDiskFailure      | critical  |
| tempAlarm     | CISCO-SYS-MIB::cpqHeTempAlarm        | warning   |
| fanFailure    | CISCO-SYS-MIB::cpqHeFanFailure       | critical  |
| powerFailure  | CISCO-SYS-MIB::cpqHePowerSupplyFail  | critical  |

### Correlation Rules

1. **Deduplication**: Same source device + same alarm type within 5 minutes → suppress duplicate
2. **Suppression**: Acknowledged alarms within 30 minutes → suppress related new alarms
3. **Escalation**: Unresolved critical alarms after 60 minutes → escalate to "major"
4. **Root Cause**: If a core switch has linkDown, suppress linkDowns on downstream links within 30 minutes
5. **Auto-closure**: linkUp 5 minutes after linkDown on same interface → auto-resolve

---

## Discovery Engine

1. Input: CIDR range(s) (e.g., `192.168.1.0/24`)
2. For each IP in range:
   - SNMP walk on sysOID (RFC1213::sysDescr)
   - If SNMP community valid → device found
   - Record sysDescr, sysLocation, sysContact
3. For SNMP-invalid hosts:
   - Port scan (22, 80, 443, 23) for protocol fingerprint
4. If new device found → create Device + Credential record
5. Repeat on schedule

---

## Topology Builder

1. For each device in inventory:
   - Poll LLDP-MIB (lldpRemTable)
   - Poll CDP-MIB (cdpCacheTable)
2. Build adjacency matrix
3. Compare with existing topology (diff)
4. Update: add new links, remove stale links, update interface names
5. Store as nodes (devices) + links (LLDP/CDP neighbors)

---

## Credential Vault

All credentials are encrypted using Fernet (AES-128-CBC + HMAC-SHA256):

```python
class CryptoService:
    def encrypt(self, plaintext: str) -> str
    def decrypt(self, ciphertext: str) -> str
    def rotate_keys(self) -> list[str]  # Returns [old_key, new_key]
```

The encryption key is derived from the `CREDENTIAL_ENCRYPTION_KEY` environment variable (hex-encoded 32-byte key).

Key rotation: when `CREDENTIAL_ENCRYPTION_KEY` changes, the system:
1. Decrypts all existing credentials with the old key
2. Re-encrypts with the new key
3. Marks old key as deprecated (but keeps it for decryption)

---

## Worker Pool

Workers run as asyncio Tasks managed by a `WorkerSupervisor`:

```python
class WorkerSupervisor:
    async def start(self):
        self.tasks = [
            asyncio.create_task(poller_worker.loop()),
            asyncio.create_task(discovery_worker.loop()),
            asyncio.create_task(alarm_worker.loop()),
            asyncio.create_task(report_worker.loop()),
        ]
    
    async def stop(self):
        for task in self.tasks:
            task.cancel()
```

Each worker:
- Runs in a `while True` loop with configurable interval
- Uses Redis pub/sub for inter-worker communication
- Logs progress to structured logger
- Handles errors gracefully (retry, log, continue)

---

## Frontend Architecture

### State Management (Zustand)

- **deviceStore**: Devices list, filters, selection, loading
- **alarmStore**: Alarms list, active filters, auto-refresh via WebSocket
- **topologyStore**: Topology nodes/links, graph data for visualization

### WebSocket

- Endpoint: `ws://backend:8000/ws`
- Channels: `kpi_update`, `alarm_new`, `topology_changed`, `discovery_progress`
- Auto-reconnect with exponential backoff

### Pages

| Page          | Key Features                                    |
|---------------|------------------------------------------------|
| Dashboard     | KPI cards, line charts, alarm summary, device status |
| Devices       | CRUD table, filters, bulk actions, import CSV    |
| Credentials   | Vault with encrypt/decrypt, key rotation UI      |
| Performance   | KPI history charts, threshold configuration      |
| MIBs          | MIB file upload, OID browser, custom MIBs        |
| Discovery     | CIDR input, progress bar, results table          |
| Commands      | Saved commands list, execute per-device, view output |
| IOS Versions  | Version table, upload form, EOL/EOS alerts       |
| Topology      | Network graph visualization (cytoscape.js)       |
| Alarms        | Alarm list, correlation view, bulk acknowledge   |
| Reports       | Templates, schedule, export (Excel/PDF)          |
| Settings      | App settings, SNMP config, polling intervals     |

---

## Infrastructure

### Docker Compose Services

| Service       | Image                              | Purpose                    |
|---------------|------------------------------------|----------------------------|
| postgres      | timescale/timescaledb:latest-pg16  | Primary DB + time-series   |
| redis         | redis:7-alpine                     | Cache, queue, pub/sub      |
| app           | (custom build from backend/)       | FastAPI backend            |
| frontend      | (custom build from frontend/)      | React + Vite dev server    |

### Database Schema

- 11 main tables (devices, credentials, inventory, kpis, mibs, commands, ios_versions, topology_nodes, topology_links, alarms, reports)
- 2 hypertables (kpis, kpi_deltas) for time-series storage
- Indexes on device_type, status, ip_address, kpi_type, timestamp
- TimescaleDB continuous aggregates for KPI rollups

---

## Security Considerations

1. **Credentials**: AES-256 encrypted at rest; never logged
2. **SNMPv3**: authPriv support for encrypted SNMP traffic
3. **SSH**: StrictHostKeyChecking, key-based auth preferred
4. **API**: Token-based auth (JWT) with refresh tokens
5. **CORS**: Configurable allowed origins
6. **Rate limiting**: Per-IP rate limiting on API endpoints
7. **Audit log**: All credential changes logged
8. **Key rotation**: Automatic key rotation for credentials

---

## Scalability & Performance

### Current Design (Single Node)

- Polls up to 500 devices at 60s intervals
- TimescaleDB handles time-series KPI data efficiently
- Redis queues for async workers

### Future Scaling

- **Horizontal scaling**: Multiple backend instances behind load balancer
- **Worker scaling**: Redis Streams for distributed worker pools
- **Database**: TimescaleDB continuous aggregates for KPI rollups
- **MIB compilation**: Cache compiled MIBs in Redis

---

## Future Enhancements

- [ ] Webhook integration (Slack, Teams, PagerDuty)
- [ ] NetFlow/sFlow analysis
- [ ] IPAM integration
- [ ] Change management (RFC workflow)
- [ ] SNMPv3 user management via API
- [ ] Multi-tenant support
- [ ] Grafana dashboard exporter
- [ ] GraphQL API layer
- [ ] CLI tool for automation
- [ ] HA cluster with postgres streaming replication
