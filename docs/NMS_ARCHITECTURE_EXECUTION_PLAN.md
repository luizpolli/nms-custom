# NMS_Custom Architecture Execution Plan

Source reviewed: `NMS_Custom_Architecture_Recommendation.docx` received 2026-05-16.

## Executive decision

The recommendation is solid and should be treated as the product north star. I would **not** rewrite the current stack. The best path is incremental: stabilize the existing FastAPI + React + TimescaleDB + Redis product, then split runtime responsibilities into workers/receivers, then add telemetry as a first-class ingestion path.

The product should aim to become an **Assurance-oriented NMS** with these pillars:

1. Inventory & Topology
2. Performance & Telemetry
3. Fault & Alarm Correlation
4. Automation & Reporting
5. Administration, Security & Observability

## Token / work management strategy

To avoid burning context on huge rewrites:

- Keep this document as the owner plan and update it only at phase boundaries.
- Use focused implementation tasks per domain instead of asking one run to change everything.
- Prefer small commits/PR-sized chunks: backend model/API, worker, frontend view, tests.
- Validate every chunk with the smallest meaningful gate: backend tests, frontend build, typecheck, or direct inspection.
- Notify only when a phase or meaningful task finishes, or when blocked by a real decision.
- Use subagents for large code reviews or isolated implementation areas, not for every tiny edit.

## Recommended improvements beyond the document

These would make the final product stronger:

1. **Define a normalized canonical data contract before telemetry.**
   - Device, Interface, Component, KPI sample, Alarm, Event, TopologyNode, TopologyLink, CredentialProfile, Report.
   - This prevents building separate SNMP, telemetry, trap, and UI worlds.

2. **Add an event envelope early.**
   - Every internal event should include `event_id`, `event_type`, `source`, `timestamp`, `trace_id`, optional `device_id`, `object_type`, `object_id`, `severity`, and `payload`.
   - Redis Streams can be used now; Kafka/NATS can come later without redesign.

3. **Keep raw ingestion short-retention and normalized KPIs long-retention.**
   - Raw telemetry/traps/syslog are expensive and noisy.
   - Normalized KPI/alarm/topology data is the durable source for reports and AI.

4. **Make RBAC command permissions separate from normal operator permissions.**
   - A user who can view devices should not automatically be allowed to run commands.
   - Command allow-lists and full audit trails are mandatory.

5. **Add observability for the NMS itself.**
   - Poller lag, queue depth, collector health, samples/sec, dropped events, API latency, DB query latency.
   - The NMS needs to monitor its own monitoring pipeline.

6. **Delay Kubernetes until the Compose runtime boundaries are clean.**
   - Compose should first run separate API, workers, receivers, Redis, and Timescale services.
   - Helm/K8s should promote the same service boundaries later.

## Phase 0 — Baseline and gap alignment

Goal: turn the architecture recommendation into an executable backlog.

Deliverables:

- [x] Extract and review architecture recommendation.
- [x] Create this execution plan.
- [x] Compare current repo against recommended domains.
- [x] Open/update backlog items by phase.
- [x] Verify current backend tests and frontend build status.

Acceptance criteria:

- Current repo gaps are known.
- Phases below are mapped to concrete files/modules.
- No major implementation starts before baseline gates are known.

## Phase 0 completion notes — 2026-05-16

Completed:

- Fixed Docker Compose infra mounts by replacing accidental directories with real files:
  - `infra/postgres/init.sql`
  - `infra/redis/redis.conf`
- Hardened backend settings so compose-style environment variables no longer break Pydantic loading.
- Added test-mode lifespan behavior so API smoke tests do not require Docker-only Postgres/Redis hostnames.
- Added backend pytest env defaults in `backend/tests/conftest.py`.
- Validation:
  - `./backend/.venv/bin/python -m pytest backend/tests -q` → 112 passed
  - `npm run build` in `frontend/` → passed
  - `docker compose config --quiet` → passed

Next: start Phase 1 data model normalization.

## Phase 1 — Stabilize core SNMP / SSH / inventory foundation

Goal: make the existing product reliable before adding more ingestion complexity.

Backend tasks:

- Normalize device fields: `site_id`, `role`, `lifecycle_state`, `platform_family`, `mgmt_vrf`, `snmp_enabled`, `ssh_enabled`, `telemetry_enabled`.
- Ensure credentials are profile-based and device assignments are explicit.
- Harden inventory and interface identity:
  - create/verify dedicated interface model/table;
  - stable interface ID for KPI, topology, and alarms;
  - avoid only storing interfaces inside JSON.
- Confirm KPI sample model supports:
  - `source_type`, `object_type`, `object_id`, `metric_name`, `unit`, `quality/status`, labels.
- Confirm alarm model supports:
  - dedup key, correlation group, root alarm, first/last seen, occurrence count.
- Add/verify audit events for credential changes, command execution, alarm ack/clear, admin changes.

Frontend tasks:

- Improve Dashboard drill-down links.
- Inventory device detail should expose credentials, interfaces, KPIs, alarms, topology links.
- Consistent status/severity badges across pages.

Infrastructure tasks:

- Keep Docker Compose stable.
- Add health checks and clear env defaults.

Validation:

- Backend tests pass.
- Frontend build passes.
- Device CRUD + credential flow + basic KPI query manually inspected.

## Phase 1 completion notes — 2026-05-16

Completed data-model foundation:

- Extended `Device` with site/role/lifecycle/platform/VRF and collection toggles: SNMP, SSH, telemetry.
- Added normalized `Interface` ORM model and schemas for stable interface identity.
- Extended `KPI` with telemetry-ready fields: `metric_name`, `source_type`, `object_type`, `object_id`, `quality`, `labels`.
- Extended `Alarm` with assurance-ready fields: `dedup_key`, `correlation_group_id`, `root_alarm_id`, `source_type`, `object_type`, `object_id`.
- Added persistent `AuditLog` ORM model and schemas.
- Added explicit `CredentialAssignment` model for profile-to-device mapping while keeping existing `device.credential_id` compatibility.
- Updated KPI/alarm creation paths to populate normalized defaults.
- Added lightweight local-upgrade DDL in `init_db()` for existing deployments.

Validation:

- `./backend/.venv/bin/python -m pytest backend/tests -q` → 112 passed
- `npm run build` in `frontend/` → passed
- `docker compose config --quiet` → passed

Notes:

- This is a compatibility-first model foundation, not a full migration system. Alembic migrations should be introduced before production upgrades.
- Next phase should split runtime workers and receivers out of the API process.

## Phase 2 — Operational workflows for NOC/TAC

Goal: make the system operationally useful, not just a data collector.

Tasks:

- Alarm ack/clear/suppress workflows with audit trail.
- Root-cause group UI and event timeline.
- LLDP/CDP topology refresh and graph diff.
- Topology alarm overlay and link utilization overlay.
- Config backup scheduling and compare view.
- Command execution allow-list and audited output store.
- Report generation jobs for inventory, KPI, alarms, and device health.

Validation:

- User can start from dashboard alarm → alarm group → impacted device/interface → topology context.
- User can run allowed command and see audit entry.
- User can generate/export at least one report.

## Phase 2 completion notes — 2026-05-16

Completed runtime separation foundation:

- Added standalone worker/receiver entrypoint: `python -m app.workers.run <kind>`.
- Supported worker kinds:
  - `monitoring-policies` / `poller`
  - `topology`
  - `reports`
  - `trap-receiver`
  - `syslog-receiver`
- Added `START_EMBEDDED_WORKERS` setting. Compose now runs API without embedded workers by default.
- Split Docker Compose runtime services:
  - `app`
  - `worker-poller`
  - `worker-topology`
  - `worker-report`
  - `trap-receiver`
  - `syslog-receiver`
- Kept current `WorkerSupervisor` for compatibility/local embedded mode.

Validation:

- `./backend/.venv/bin/python -m pytest backend/tests -q` → 112 passed
- `npm run build` in `frontend/` → passed
- `docker compose config --quiet` → passed
- `python -m app.workers.run --help` from backend → passed
- `python -m compileall -q backend/app` → passed

Notes:

- This is the first runtime split. There is not yet a true event-bus-driven alarm worker; alarm processing is still attached to trap/syslog receivers and API workflows.
- Next phase should introduce canonical event envelope + Redis Streams wrapper before telemetry MVP.

## Phase 3 — Telemetry MVP

Goal: add streaming ingestion without breaking SNMP compatibility.

Backend tasks:

- Add telemetry models/tables:
  - collectors;
  - subscriptions;
  - sensor paths;
  - raw samples with short retention;
  - ingestion stats.
- Implement telemetry receiver skeleton for gNMI/gRPC/MDT-ready ingestion.
- Implement telemetry worker normalization into existing KPI model.
- Add sensor catalog mapping vendor/model/path → normalized metric.
- Publish collector health and KPI updates through the existing event/WebSocket path.

Frontend tasks:

- New Telemetry navigation section.
- Collector status page.
- Subscription management page.
- Sensor path catalog page.
- Ingestion health cards: samples/sec, lag, drops, last seen.

Validation:

- Simulated telemetry sample becomes normalized KPI sample.
- Telemetry health appears in UI.
- SNMP KPI path remains working.

## Phase 4 — Correlation and assurance

Goal: move from monitoring to assurance/root-cause/impact.

Tasks:

- Correlation groups across traps, syslog, KPI breaches, topology changes.
- Device/interface/service health score.
- Topology impact calculation.
- Event timeline per device, interface, and alarm group.
- Suppression and dedup rules.
- Baseline breach detection using historical KPI windows.

Validation:

- Multiple related events collapse into a root-cause group.
- Dashboard shows health score and impacted entities.
- Topology overlay explains downstream impact.

## Phase 5 — Scale and production readiness

Goal: prepare the product for larger networks and clean operations.

Tasks:

- Split Compose into separate runtime services:
  - api;
  - worker-poller;
  - worker-alarm;
  - worker-discovery;
  - worker-topology;
  - worker-report;
  - worker-telemetry;
  - trap-receiver;
  - syslog-receiver;
  - telemetry-receiver.
- Add worker sharding/concurrency controls.
- Add retention policies and Timescale continuous aggregates.
- Add NMS self-observability metrics.
- Prepare Helm chart after Compose boundaries are proven.
- Add production RBAC review.

Validation:

- Workers can run independently.
- Queue depth and worker health are observable.
- Dashboard queries remain fast with seeded/test volume.

## Phase 6 — AI-assisted operations

Goal: add intelligence only after data is clean enough to trust.

Tasks:

- Alarm group summarization.
- KPI anomaly explanations.
- Report narratives.
- Runbook suggestion engine.
- Optional operational assistant that uses command outputs, known models, topology, and alarm context.

Validation:

- AI output cites underlying alarms/KPIs/events.
- AI is advisory, not required for core monitoring.
- No secrets or command outputs leak into unsafe contexts.

## Immediate next tasks

1. Finish current repo gap analysis against this plan.
2. Run baseline validation gates:
   - backend tests;
   - frontend build/typecheck.
3. Start Phase 1 with data model alignment and dashboard drill-down improvements.

## Notification rules

I will notify Kapy when:

- a phase completes;
- a meaningful task completes with validation evidence;
- a blocker appears that needs a decision;
- I find a better architectural path than the current plan.

I will avoid noisy updates for every tiny file edit.
