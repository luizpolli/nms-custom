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

## Phase 2.5 — Migration hardening and worker observability (in progress)

Inserted before Phase 3 to fix two foundational gaps surfaced by Phases 1–2:

1. `init_db()` was applying ad-hoc `ALTER TABLE IF NOT EXISTS` DDL on every
   API start, which would not scale to production schema changes.
2. The new worker/receiver services have no lag/health visibility.

### Alembic baseline (done)

- Added `backend/alembic.ini` and async `backend/alembic/env.py` driven by
  `Settings.database_url` and `app.database.Base.metadata`.
- Generated `alembic/versions/0001_baseline_schema.py` capturing the full
  current ORM schema (devices, interfaces, KPI, alarms, alarm rules,
  monitoring policies, MIBs, reports, RBAC, audit log, topology).
- Removed inline `ALTER TABLE` DDL from `init_db()`; `create_all` remains
  as a dev/embedded fallback only.
- `Makefile`: added `migrate` (`alembic upgrade head`), `migrate-stamp`
  (one-time mark of pre-alembic envs), and `migrate-revision MSG="…"`.
- Verified: `alembic upgrade head` + `alembic downgrade base` + `alembic check`
  round-trip cleanly on a clean Postgres 16.
- Verified: backend tests `112 passed`.

### Worker observability (done)

- Added best-effort Redis worker heartbeat publisher: `nms:workers:<kind>` with
  `last_run_at`, `last_status`, `runs_total`, `errors_total`, `last_error`, and
  `expected_interval_s`.
- Instrumented monitoring-policy, topology, trap receiver, and report scheduler
  loops with startup/success/failure heartbeats. Long-lived trap receiver
  refreshes its heartbeat periodically while idle.
- Added `GET /api/system/health` to aggregate worker heartbeat state and flag
  workers as stale when `now - last_run_at > interval * 3`.
- Added system-health API tests for stale and healthy worker summaries.
- Frontend system-health surface will follow in Phase 5; this phase only wires
  backend self-observability.

## Phase 2.5 completion notes — 2026-05-17

Completed migration and observability hardening:

- Alembic baseline replaces ad-hoc schema ALTER logic for production-ready
  migrations while preserving `create_all` as a dev/embedded fallback.
- Separated worker services now publish best-effort Redis heartbeats.
- API exposes worker health at `GET /api/system/health`.
- Phase validation gates:
  - backend tests pass;
  - Bandit SAST passes;
  - backend compile check passes.

Next: Phase 3 should introduce canonical event envelope + Redis Streams wrapper
before starting the telemetry MVP.

## Phase 3A — Event bus foundation

Goal: introduce the canonical event envelope and Redis Streams transport before
adding telemetry-specific ingestion.

Deliverables:

- [x] Canonical `EventEnvelope` contract with `event_id`, `event_type`,
  `source`, `timestamp`, `trace_id`, optional `device_id`, `object_type`,
  `object_id`, `severity`, and `payload`.
- [x] Redis Streams-backed `EventBus` wrapper with publish/read helpers.
- [x] Configurable stream name via `EVENT_STREAM_NAME` and event-bus disable
  switch via `EVENT_BUS_ENABLED`.
- [x] Best-effort publishing from the alarm correlator path, covering SNMP
  traps, syslog events, custom events, and KPI threshold-crossing events that
  flow through `AlarmCorrelator`.
- [x] Unit tests for envelope roundtrip, Redis Streams wrapper behavior, and
  test-mode publish suppression.

Validation:

- Backend tests pass.
- Bandit SAST passes.
- Backend compile check passes.
- Frontend build and Compose config remain clean.

Next: Phase 3B telemetry MVP can consume the same event contract instead of
creating a separate ingestion world.

## Phase 3B — Telemetry MVP

Goal: add streaming ingestion without breaking SNMP compatibility.

Backend tasks:

- [x] Add telemetry models/tables:
  - collectors;
  - subscriptions;
  - sensor paths;
  - raw samples with short retention;
  - ingestion stats.
- [x] Add Alembic migration for telemetry MVP schema.
- [x] Add telemetry API skeleton:
  - collector list/create;
  - subscription list/create;
  - sensor path catalog list/create;
  - sample ingest;
  - telemetry health summary.
- [x] Implement telemetry normalization into existing KPI model.
- [x] Publish normalized telemetry sample events through the canonical event bus.
- [x] Add frontend telemetry navigation/pages for collector status, subscriptions,
  sensor catalog, and health cards.
- [x] Add standalone `telemetry-receiver` runtime service/worker boundary with
  heartbeat and gNMI-ready config.
- [ ] Implement real gNMI/gRPC/MDT protocol adapter. The receiver process is now
  wired, but protocol decoding/subscription transport remains future work.



## Phase 3B completion notes — 2026-05-17

Completed telemetry MVP backend skeleton:

- Added telemetry ORM models and migration `0002_telemetry_mvp_schema.py` for
  collectors, subscriptions, sensor paths, raw samples, and ingestion stats.
- Added Pydantic schemas and `/api/telemetry` routes for collector, subscription,
  sensor catalog, sample ingest, and health summary workflows.
- Added `TelemetryIngestionService` to persist raw samples and normalize them
  into the existing KPI table with `source_type=telemetry`.
- Normalized telemetry samples publish `telemetry.sample.normalized` events via
  the canonical Redis Streams event bus from Phase 3A.
- Added tests for telemetry sample normalization.

Remaining for full telemetry productization:

- Real gNMI/gRPC/MDT protocol adapter inside the now-wired receiver process.
- Retention policies/continuous aggregates for raw telemetry at scale.

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


## Phase 3C/3D completion notes — 2026-05-17

Completed telemetry UI and receiver runtime boundary:

- Added Telemetry navigation and page with health cards, collector list/create,
  subscription list/create, and sensor path catalog list/create.
- Added standalone `telemetry-receiver` worker kind and Docker Compose service.
- Added telemetry receiver config/runtime skeleton with heartbeat integration via
  `/api/system/health`.
- Kept protocol adapter explicitly pending: gNMI/gRPC/MDT decoding and device
  subscription transport should plug into `TelemetryReceiver` next.

## Phase 4 — Correlation and assurance

Goal: move from monitoring to assurance/root-cause/impact.

Tasks:

- [x] Correlation groups across active/acknowledged alarms using correlation keys
  and group ids.
- [x] Network and impacted-device health score derived from active alarm severity
  and occurrence count.
- [x] Topology impact calculation with downstream dependency traversal.
- [x] Event timeline API and UI for recent assurance events.
- [x] Suppression workflow UI beyond existing dedup/alarm-rule foundation.
- [x] Baseline breach count from recent non-good KPI quality samples.

Validation:

- Multiple related events collapse into a root-cause group.
- Dashboard shows health score and impacted entities.
- Topology overlay explains downstream impact.


## Phase 4A completion notes — 2026-05-17

Completed first assurance slice:

- Added `/api/assurance/summary`, `/api/assurance/groups`, and
  `/api/assurance/timeline`.
- Added deterministic health scoring helpers and tests.
- Added Assurance UI page with score cards, root-cause groups, impacted devices,
  and event timeline.
- Added Dashboard assurance score card.

Remaining Phase 4 work:

- True topology downstream impact traversal.
- Service-specific impact scoring beyond interface/device health.
- Service-level impact modeling.


## Phase 4B completion notes — 2026-05-17

Completed topology and interface assurance slice:

- Added `/api/assurance/impact` for downstream topology traversal from a root
  device/node using persisted topology links.
- Extended assurance summary with impacted interface scoring based on interface
  alarms, link status, and non-good interface KPI quality samples.
- Added Assurance UI cards/tables for impacted interfaces and downstream
  topology impact.
- Added tests for group collapse and interface alarm matching.

Remaining Phase 4 work:

- Service-level impact modeling.
- Bidirectional/topology-role-aware blast radius for ambiguous discovery edges.
- Service-level impact modeling.


## Phase 4C completion notes — 2026-05-17

Completed alarm suppression lifecycle slice:

- Added alarm suppress/unsuppress API endpoints with audit-log entries.
- Suppressed alarms keep visibility via `state=suppressed` and retain suppression
  actor/reason metadata under `raw_varbinds._suppression`.
- Added Alarms UI suppression modal, suppressed filter, suppress/unsuppress table
  actions, and detail drawer controls.
- Assurance summaries now include suppressed alarms in lifecycle context while
  keeping active counts explicit.

Remaining Phase 4 work:

- Group-level lifecycle controls such as suppress/unsuppress whole correlation
  groups. Completed as Phase 4D with Assurance group controls and audit logs.
- Service-level impact modeling.
- Bidirectional/topology-role-aware blast radius for ambiguous discovery edges.


## Phase 4D completion notes — 2026-05-17

Completed group lifecycle controls:

- Added Assurance APIs to suppress/unsuppress a whole correlation group.
- Group lifecycle writes a correlation-group audit event and updates all member
  alarms with group suppression metadata.
- Assurance group state now reports `suppressed` when all member alarms are
  suppressed.
- Added Assurance UI controls to suppress/unsuppress groups directly from the
  root-cause group card.

## Phase 4E completion notes — 2026-05-17

Completed service-level impact modeling:

- Added `Service` and `ServiceMember` models for logical customer, transport,
  platform, or infrastructure service groupings.
- Added Alembic migration `0004_services.py` for `services` and
  `service_members`.
- Added `/api/services` CRUD endpoints for service definitions and membership.
- Added `/api/assurance/services` and `/api/assurance/services/{service_id}` to
  score service impact from member device alarms, interface alarms, and
  interface operational state.
- Added Assurance UI service-impact table next to device/interface/topology
  impact views.
- Added backend unit tests for healthy, critical, weighted, interface-down, and
  empty-service scoring paths.

## Phase 4F completion notes — 2026-05-17

Completed topology-role-aware blast-radius refinement:

- Added role-aware topology traversal that understands common core/distribution/access/customer hierarchy.
- `/api/assurance/impact` now supports `traversal_mode=auto|downstream|upstream|bidirectional`.
- `auto` mode keeps directed traversal but safely reverse-walks ambiguous or upstream-oriented discovery edges so LLDP/CDP orientation quirks do not hide blast radius.
- Impact results now include link id, traversal direction, confidence, reason, and ambiguous-edge count.
- Added unit tests for downstream traversal, ambiguous reverse traversal, and bidirectional mode.

Phase 4 status: complete for the current roadmap. Future improvements can add richer service dependency weighting and manual link-direction overrides.

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
- [x] Add retention policies and Timescale continuous aggregates.
- [x] Add NMS self-observability metrics.
- Prepare Helm chart after Compose boundaries are proven.
- Add production RBAC review.

Validation:

- Workers can run independently.
- Queue depth and worker health are observable.
- Dashboard queries remain fast with seeded/test volume.

## Phase 5A completion notes — 2026-05-17

Completed first scale/production-readiness slice:

- Added best-effort TimescaleDB setup for `kpis` and `telemetry_raw_samples`:
  extension check, hypertable conversion, retention policies, and hourly KPI
  rollup continuous aggregate (`kpi_hourly_rollups`).
- Added portable retention policy definitions for raw telemetry (7 days) and
  normalized KPIs (90 days), with explicit `/api/system/retention` visibility.
- Added Prometheus `/metrics` endpoint with NMS gauges for KPI rows, raw
  telemetry rows, telemetry accepted/dropped counters, event queue depth, and
  worker stale/run/error heartbeat state.
- Added API request count/latency middleware metrics.
- Added Alembic migration `0003_timescale_retention_metrics.py` for production
  Timescale deployments, keeping operations best-effort on plain PostgreSQL.

## Phase 5B completion notes — 2026-05-17

Completed second scale/production-readiness slice:

- Added deterministic worker sharding helpers and monitoring-policy device partitioning via `WORKER_SHARD_ID` / `WORKER_SHARD_COUNT`.
- Added `WORKER_MAX_CONCURRENCY` control for bounded concurrent policy execution.
- Added DB query latency histogram instrumentation for self-observability scrape probes.
- Added baseline Helm chart under `helm/nms-custom` for API, frontend, worker services, telemetry receiver, Redis, TimescaleDB, services, ConfigMap, and least-privilege service account/RBAC.
- Added `docs/PRODUCTION_RBAC_REVIEW.md` with high-risk permissions, recommended production defaults, Kubernetes RBAC posture, and pre-production gaps.

Remaining Phase 5 work:

- Harden Helm for real clusters: ingress, TLS secret integration, secret-manager support, autoscaling, NetworkPolicies, pod disruption budgets, and chart lint in CI.
- Split additional worker kinds (`worker-alarm`, `worker-discovery`, `worker-telemetry`) when event-bus consumers are implemented.

## Phase 3E telemetry productization notes — 2026-05-17

Completed telemetry protocol-adapter skeleton:

- Added gNMI/MDT-style JSON frame parser that normalizes path/value/timestamp/update payloads into `TelemetrySampleIngest` rows.
- `telemetry-receiver` can now run a line-delimited TCP JSON adapter via `TELEMETRY_TRANSPORT=gnmi-json|mdt-json|json` and pass decoded samples into the existing ingestion/KPI normalization path.
- Added tests for multiple updates, path object handling, decimal values, and required device id validation.

Remaining telemetry productization work:

- Add native gRPC/gNMI protobuf transport with TLS/mTLS, subscriptions, backpressure, and per-device collector credentials once lab devices or packet captures are available.

## Phase 6 — AI-assisted operations

Goal: add intelligence only after data is clean enough to trust.

Tasks:

- [x] Alarm group summarization.
- [x] KPI anomaly explanations.
- [x] Report narratives.
- [x] Runbook suggestion engine.
- [ ] Optional operational assistant that uses command outputs, known models, topology, and alarm context.

Validation:

- AI output cites underlying alarms/KPIs/events.
- AI is advisory, not required for core monitoring.
- No secrets or command outputs leak into unsafe contexts.

## Phase 6A completion notes — 2026-05-17

Completed advisory-only AI operations API slice:

- Added `/api/ai-ops/alarm-groups/{group_key}/summary` for cited alarm-group summaries.
- Added `/api/ai-ops/kpis/anomalies/explain` for cited KPI anomaly explanations.
- Added `/api/ai-ops/reports/narrative` for report narrative drafts backed by alarm/KPI citations.
- Added `/api/ai-ops/runbooks/suggest` for deterministic runbook suggestions from active alarm category.
- All responses carry `advisory_only=true` and cite underlying alarm/KPI IDs.

Remaining Phase 6 work:

- Optional LLM-backed assistant with strict retrieval/citation guardrails and command-output redaction.
- Frontend AI Ops page/cards if this becomes a UX priority.

## Immediate next tasks

1. Add native gRPC/gNMI protobuf transport with TLS/mTLS and subscription management when lab devices or captures are available.
2. Harden Helm for real cluster deployment (Ingress/TLS, external secrets, NetworkPolicies, HPA/PDB, chart lint in CI).
3. Add event-bus-driven alarm/discovery/telemetry worker consumers so Compose/Helm can split those worker kinds cleanly.

## Notification rules

I will notify Kapy when:

- a phase completes;
- a meaningful task completes with validation evidence;
- a blocker appears that needs a decision;
- I find a better architectural path than the current plan.

I will avoid noisy updates for every tiny file edit.
