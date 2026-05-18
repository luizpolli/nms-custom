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

## Phase 5C completion notes — 2026-05-17

Completed Helm and worker hardening slice:

- Added Helm Ingress template with TLS wiring and class/annotation support.
- Added existing-secret and provider-neutral ExternalSecret placeholders without requiring a specific secret manager.
- Added NetworkPolicy, HPA, and PDB templates with chart values disabled by default.
- Added `make helm-lint` helper.
- Added event-bus worker skeletons for `worker-alarm`, `worker-discovery`, and `worker-telemetry` using Redis Streams `XREAD` via the existing `EventBus` abstraction.
- Wired the new worker kinds into standalone runner, embedded supervisor, worker heartbeat catalog, Docker Compose, and Helm deployments.
- Added unit tests for defensive/idempotent event consumer behavior.

Validation:

- `./backend/.venv/bin/python -m pytest backend/tests -q` → 159 passed.
- `./backend/.venv/bin/python -m compileall -q backend/app` → passed.
- `docker compose config --quiet` → passed.
- `npm run build` in `frontend/` → passed.
- `helm lint helm/nms-custom` → passed after installing Helm locally.
- `helm template nms-custom helm/nms-custom` → rendered successfully.

## Phase 5D completion notes — 2026-05-17

Completed CI validation hardening:

- Added `.github/workflows/ci.yml` with backend tests, backend compile, frontend build, Docker Compose config validation, Helm lint, and Helm render jobs.
- Added `make helm-template` helper alongside `make helm-lint`.

## Phase 5E completion notes — 2026-05-17

Completed Redis Streams consumer-group semantics:

- Added `EventBus` helpers for consumer-group creation, `XREADGROUP`, `XACK`, and stale pending-event reclaim via `XAUTOCLAIM`.
- Updated alarm, discovery, and telemetry event workers to use explicit group/consumer identity with ack-after-success behavior.
- Added worker stats for acknowledged and claimed events.
- Added configurable consumer group prefix, block interval, and stale-claim timeout for Compose/Kubernetes environments.
- Updated Helm values/ConfigMap for event stream and consumer tuning.
- Added tests covering ack behavior and stale pending-event claim flow.

Remaining Phase 5 work:

- Replace defensive worker handlers with domain processors for alarm enrichment, discovery refresh triggers, and telemetry fan-out once processor ownership rules are finalized.

## Phase 3E telemetry productization notes — 2026-05-17

Completed telemetry protocol-adapter skeleton:

- Added gNMI/MDT-style JSON frame parser that normalizes path/value/timestamp/update payloads into `TelemetrySampleIngest` rows.
- `telemetry-receiver` can now run a line-delimited TCP JSON adapter via `TELEMETRY_TRANSPORT=gnmi-json|mdt-json|json` and pass decoded samples into the existing ingestion/KPI normalization path.
- Added tests for multiple updates, path object handling, decimal values, and required device id validation.

Remaining telemetry productization work:

- Add native gRPC/gNMI protobuf transport with TLS/mTLS, subscriptions, backpressure, and per-device collector credentials once lab devices or packet captures are available.
- Native gNMI is now documented as a lab-ready interface contract in code; real protobuf/gRPC dependencies remain intentionally deferred.

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

## Phase 6B completion notes — 2026-05-17

Completed advisory UI slice:

- Added AI Ops navigation and page with cards for alarm-group summary, KPI anomaly explanation, report narrative, and runbook suggestions.
- Every card marks output as advisory-only and displays citations/evidence when the API returns them.
- The UI degrades cleanly when advisory endpoints have no data.

Remaining Phase 6 work:

- Optional LLM-backed assistant with strict retrieval/citation guardrails and command-output redaction.

## Immediate next tasks

## Phase 5F completion notes — 2026-05-17

Completed mock-device simulator harness:

- Added `tools/simulators/mock_device.py` to create/find a mock Cisco device through the API and emit local lab traffic.
- Added UDP syslog simulation with Cisco-ish heartbeat and `%LINK-3-UPDOWN` messages.
- Added line-delimited gNMI/MDT JSON telemetry simulation for interface counters and CPU utilization.
- Added `make sim-device`, `make sim-syslog`, `make sim-telemetry`, and `make sim-run` helpers.
- Added `docs/MOCK_DEVICE_SIMULATORS.md` with local lab workflow and limitations.
- Added unit tests for simulator payload builders.

## Phase 5G completion notes — 2026-05-17

Completed first real worker processors and simulator inspection pass:

- Telemetry normalized-sample events now include `raw_sample_id` and `kpi_id` so downstream workers can load the persisted KPI row.
- `worker-telemetry` now evaluates KPI thresholds for `telemetry.sample.normalized` events instead of only ACKing them.
- `worker-alarm` now accepts syslog/trap-sourced alarm events even when the event type is facility/OID-shaped, and enriches active alarms with device metadata when a matching device can be found.
- Alarm correlation now preserves the true source type (`syslog`, `trap`, or `event`) when creating alarm rows.
- `worker-discovery` now applies lightweight device status updates from discovery/inventory/topology events.
- Mock simulator traffic was run through local receivers: syslog alarms were created and telemetry frames returned `OK 2` while raw telemetry/KPI rows were inserted.

## Phase 5H completion notes — 2026-05-17

Completed syslog-to-device correlation for local/mock labs:

- Syslog parsing now extracts RFC5424 and BSD-style hostnames while preserving the packet source IP.
- The syslog receiver passes the logical hostname to alarm correlation and keeps the packet source in alarm fields for audit/debugging.
- Alarm correlation now resolves devices by source hostname/IP and attaches `device_id`/`object_id` directly when creating or deduping alarms.
- This fixes Docker/local runs where UDP source IP is a bridge/local address but the syslog payload contains the real/simulated device name.

## Phase 5I completion notes — 2026-05-17

Completed SNMP trap simulator support for local/mock labs:

- Added raw SNMPv2c Trap-PDU generation to `tools/simulators/mock_device.py` without depending on the broken local `pysnmp/pyasn1` import path.
- Added `make sim-trap` and updated `make sim-run` to emit syslog, SNMP traps, and telemetry.
- Trap simulator emits paired `linkDown`/`linkUp` traps with `sysUpTime.0`, `snmpTrapOID.0`, `sysName.0`, and `ifIndex` varbinds.
- Trap correlation now prefers `sysName.0` as the logical source host, preserving packet source in varbinds when the simulator/relay hides the device IP.
- Mock simulator docs now cover syslog, SNMP traps, and telemetry together.

## Phase 5J completion notes — 2026-05-17

Completed lab health and EPS visibility:

- Added `/api/lab/health` for compact local lab diagnostics across mock devices, telemetry samples/KPIs, syslog/trap/event alarms, Redis Stream health, pending consumer-group lag, and worker heartbeats.
- Added frontend `Lab Health` page with summary cards for telemetry EPS, alarm EPS, event-bus EPS, pending events, stale workers, mock devices, alarm sources, event-bus breakdowns, and worker status.
- Added sidebar route `/lab` so local simulator state can be checked without jumping between API, DB, and logs.
- Live local validation showed mock device discovery, syslog/trap alarm counts, Redis stream groups, zero pending events, and healthy workers.

Remaining Phase 5 work:

- Add broader vendor trap fixtures/captures beyond the focused linkDown/linkUp SNMPv2c lab path.
- Add richer discovery refresh triggers and telemetry fan-out processors beyond threshold evaluation.
- Add optional deeper EPS/latency histograms once `nms-traffic-sim` starts driving sustained loads.

## Phase 5K completion notes — 2026-05-17

Completed discovery refresh triggers and telemetry fan-out processors:

- `DiscoveryEventConsumer._apply_device_status` now returns `(prev_status, updated)` so the caller knows the previous device state before the update.
- Added `DiscoveryEventConsumer._maybe_emit_refresh`: when a device transitions to `up` from `down`/`unknown`/`None`, or when `payload.refresh_requested=true`, publishes a `discovery.refresh.requested` event with `device_id`, `correlation_key`, and `reason`. Idempotent via a per-instance `_last_status` cache.
- Added `TelemetryEventConsumer._emit_kpi_evaluated`: after threshold evaluation for `telemetry.sample.normalized`, publishes a `telemetry.kpi.evaluated` fan-out event with `kpi_id`, `device_id`, `value`, and `severity` (`nominal` when no TCAs fired, `warning` when at least one crossed). Fan-out is skipped when the KPI row is not found (existing early-return guard).
- Added 5 new tests in `backend/tests/services/test_event_consumers.py`:
  - Discovery emits refresh on `down->up` transition.
  - Discovery does not re-emit when status is already `up` (idempotency).
  - Telemetry fan-out carries `nominal` severity when no TCA fires.
  - Telemetry fan-out carries `warning` severity when TCAs fire.
  - No fan-out emitted when KPI row is not found.
- `FakeBus` in the test file gained a `publish` method and a `published` list for assertion.
- Validation: `pytest backend/tests -q` → 174 passed (up from 169).

## Phase 5L completion notes — 2026-05-17

Broader vendor SNMP trap fixtures and classifier added.

Deliverables:

- `backend/tests/fixtures/traps/cisco_traps.py` — 7 Cisco trap fixture dicts covering linkDown, linkUp, BGP peer state change, OSPF neighbor state change, fan fail, PSU fail, and config change. Each includes OID, realistic varbinds, expected_event_type, expected_severity, and expected_correlation_key_hint.
- `backend/app/services/snmp/trap_classifier.py` — data-driven OID->event_type/severity map; `classify_trap(trap_oid, varbinds) -> ClassifiedTrap`. Unknown OIDs fall back to `snmp.trap / info`.
- `tools/simulators/mock_device.py` — extended `build_snmp_v2c_trap_packet` with a `trap_type` parameter; `trap` subcommand now accepts `--trap-type {link-down,link-up,bgp-down,ospf-down,fan-fail,psu-fail,config-change}`. No new third-party deps; raw BER bytes only.
- `backend/tests/services/test_snmp_trap_fixtures.py` — 30 tests: 21 parametrized classifier assertions (event_type, severity, correlation_key per fixture) + 2 generic fallback tests + 7 end-to-end simulator round-trip tests (raw PDU -> parse -> classify -> alarm-shaped dict).

Validation:

- `pytest backend/tests -q` → 204 passed (+30 vs Phase 5K).
- `python -m compileall -q backend/app` → clean.
- `docker compose config --quiet` → clean.

Deferred: full async integration test feeding bytes through `SNMPTrapReceiver` with a live UDP socket is deferred to a separate integration-test suite; it requires `pysnmp-lextudio` and root/CAP_NET_BIND_SERVICE for port 162.

## Phase 5M completion notes — 2026-05-17

Native gNMI proto contract scaffolding and stub adapter (lab-bound).

Deliverables:

- `backend/app/services/telemetry/native_gnmi.py` extended with
  `StubNativeGnmiAdapter`, `GnmiUpdate`, `make_lab_subscription`, and
  `build_stub_from_paths`. `GnmiSubscriptionConfig` now carries a
  `device_id` so emitted samples match `TelemetrySampleIngest`'s required
  `device_id` field.
- `proto/README.md` documents the codegen target against upstream
  openconfig/gnmi without vendoring proto files until a real lab/capture is
  available.
- `backend/tests/services/test_native_gnmi_stub.py` exercises TLS validation,
  mTLS material requirement, the lab subscription factory, and stub
  replayability (5 tests).

Real gRPC/protobuf interop remains blocked on lab hardware or captured
Subscribe streams; the contract is now in place so a future adapter can
be dropped in without touching downstream code.

## Phase 6C completion notes — 2026-05-17

AI Ops LLM assistant with strict guardrails. LLM-disabled by default.

Deliverables:

- `backend/app/services/ai_ops/guardrails.py` — `redact_text` strips IPv4,
  IPv6, MAC, FQDN, secrets, SNMP communities, and PEM private key blocks
  before anything crosses the trust boundary. `validate_question` and
  `validate_answer` enforce length caps and citation integrity (rejects
  unknown ids, rejects uncited answers when evidence exists, requires the
  `prefix:id` citation shape so redaction placeholders cannot be mistaken
  for citations).
- `backend/app/services/ai_ops/providers.py` — `LLMProvider` Protocol +
  deterministic `NullLLMProvider` for tests/lab/air-gapped deploys.
  `get_provider("null")` is the only built-in; real providers must be
  registered explicitly.
- `backend/app/services/ai_ops/assistant.py` — retrieval-grounded
  orchestrator: validates question, pulls active alarms + non-good KPIs,
  redacts every label before building evidence, calls the provider, and
  validates the answer against the allowed citation set.
- `app/api/ai_ops.py` — new `POST /api/ai-ops/assistant/ask` endpoint;
  returns `503` when `ai_ops_llm_enabled=False`.
- `app/config.py` — `ai_ops_llm_enabled` (default `False`),
  `ai_ops_llm_provider` (`null`), plus per-call caps.
- `backend/tests/services/test_ai_ops_assistant.py` — 15 tests covering
  redaction, citation validation, question length checks, the Null
  provider, and an end-to-end orchestrator run with a fake session.

Validation:

- `pytest backend/tests -q` → 224 passed (+20 vs Phase 5L).
- `python -m compileall -q backend/app` → clean.
- `docker compose config --quiet` → clean.
- `helm lint helm/nms-custom` → clean.
- `npm run build` in `frontend/` → clean.

## Phase 6D completion notes — 2026-05-18

Frontend UI for the AI Ops assistant.

- `frontend/src/pages/aiops/AIOpsPage.tsx` — added `AssistantPanel`: question
  input (1000-char cap matching backend), `kpi_hours` selector (1–168),
  submit handler wired to `POST /api/ai-ops/assistant/ask`.
- Renders provider, redacted answer, guardrail rejection reason when
  applicable, and the citation list using the existing `CitationList`
  component.
- 503 responses (when `AI_OPS_LLM_ENABLED=False`) are surfaced as an
  EmptyState rather than a hard error.

Validation: `npm run build` clean.

## Phase 5N — EPS baseline against simulator

Drove `nms-traffic-sim syslog` at 500 EPS for 20s against the local
Compose stack (laptop):

- Sent 10000 UDP syslog messages.
- Stream `nms:events` grew from 54 → 9949 (+9895 events captured).
- All three consumer groups (`nms:worker-alarm`,
  `nms:worker-discovery`, `nms:worker-telemetry`) drained to lag=0 within
  seconds of burst end.

Effective sustained throughput ~495 EPS end-to-end with zero consumer
lag. Baseline recorded in `README.md` for future regressions.

## Phase 6E completion notes — 2026-05-18

RBAC gating on the LLM-backed AI Ops assistant.

- `app/security/auth.py`: `Principal.role` is now derived from a new
  `api_key_roles` setting ("key1:admin,key2:ai-ops,..."). Unmapped keys
  keep the default `admin` role for back-compat. Added a `require_roles(...)`
  dependency factory and a `roles_from_setting` helper.
- `app/config.py`: added `api_key_roles` and
  `ai_ops_assistant_allowed_roles` (default `"admin,ai-ops"`).
- `app/api/ai_ops.py`: `POST /assistant/ask` now requires one of the allowed
  roles in addition to the existing router-level API auth. Returns 403 if the
  caller's role is not in the allow-list.
- 9 new tests in `backend/tests/services/test_auth_roles.py` covering CSV
  parsing, role-map lookup, local-dev passthrough, admin/ai-ops accept,
  viewer reject.

Plain viewers cannot trigger LLM calls even when `AI_OPS_LLM_ENABLED=True`.

## Phase 5O — mixed EPS soak baseline

Ran three concurrent emitters from `nms-traffic-sim` for 65s against the
local Compose stack:

- syslog 300 EPS + traps 100 EPS + telemetry 100 fps.
- ~24000 frames sent across all three streams.
- `entries-read` on `nms:events` advanced from 9949 → 33604 = +23655 events
  ingested → ~364 EPS sustained aggregate.
- Consumer-group lag drained to 0 within seconds; alarm group had 3
  pending entries (expected — `XAUTOCLAIM` reclaims them on the next cycle).
- Telemetry receiver did write `OK n` acks per frame as expected.

The stream is `MAXLEN`-trimmed at ~10k, so `XLEN` alone underestimates
throughput; always use `XINFO GROUPS nms:events`'s `entries-read` for
baseline numbers.

## Phase 4G completion notes — 2026-05-18

Service impact UI page added.

- Added frontend `/services` page and sidebar entry for service impact visibility.
- Page surfaces `/api/services` inventory and `/api/assurance/services` impact scoring.
- Shows service count, average score, impacted services, impact matrix, and member-level score cards.
- Validation: `npm run build` in `frontend/` clean.

## Phase 4H completion notes — 2026-05-18

Services UI management controls added.

- Added create-service modal backed by `POST /api/services`.
- Added initial device-member selection during service creation.
- Added add/remove device member controls backed by `/api/services/{service_id}/members`.
- Added delete-service action backed by `DELETE /api/services/{service_id}`.
- Services page now lets operators model device-level service impact without raw API calls.
- Validation: `npm run build` in `frontend/` clean.

## Phase 1 frontend follow-up — 2026-05-18

Device detail interface tab wired to the existing live IF-MIB endpoint.

- Replaced the placeholder Interfaces tab with an on-demand SNMP fetch against `GET /api/devices/{id}/interfaces`.
- Added interface table with index, description, alias, admin/oper state, speed, error counters, and MAC address.
- Added refresh control and failure empty-state guidance for missing credentials/unreachable devices.
- Validation: `npm run build` in `frontend/` clean.

## Phase 4I completion notes — 2026-05-18

Interface-level service membership controls added.

- Added `GET /api/devices/{id}/managed-interfaces` for persisted normalized interface records with stable IDs.
- Fixed normalized interface schema serialization around SQLAlchemy's reserved `metadata` attribute by reading `metadata_json`.
- Services UI can now create initial members as device or interface targets.
- Services UI can add device or interface members to existing services; interface options are fetched after selecting a device.
- Interface service members send only `interface_id`, preserving existing service impact scoring semantics.
- Validation: backend compile/schema smoke clean; `npm run build` in `frontend/` clean.

## Phase 4J completion notes — 2026-05-18

Service dependency modeling added.

- Added `ServiceDependency` ORM model for directed service-to-service dependency edges.
- Added Alembic migration `0005_service_dependencies.py` with unique source/target edge constraint and indexes.
- Added Services API endpoints to add/remove dependencies under `/api/services/{service_id}/dependencies`.
- Services API responses now include each service's outgoing dependencies with labels, type, direction, weight, critical flag, and description.
- Services UI can add/remove dependencies, set direction, weight, type, criticality, and description.
- Validation: backend compile clean; `npm run build` in `frontend/` clean.

## Phase 4K completion notes — 2026-05-18

Service dependency impact propagation added.

- Assurance service scoring now performs a base pass, then applies dependency penalties from degraded target services.
- Critical dependencies and dependency weight increase propagated penalty; healthy dependencies do not penalize.
- `ServiceImpact` now returns `base_score`, `dependency_penalty`, and `dependency_impacts` with target score and propagated penalty evidence.
- Services UI shows propagated dependency impact blocks and includes dependency penalty in impact text.
- Added tests for dependency penalty propagation and healthy dependency no-op behavior.
- Validation: focused service-impact tests clean; `npm run build` in `frontend/` clean.

## Phase 4L completion notes — 2026-05-18

Dependency graph visualization added to Services UI.

- Added a dependency graph panel showing directed service edges with type, direction, weight, criticality, and optional description.
- Added filters for all, impacted, and critical dependency edges.
- Impacted edges show propagated penalty and target service score, making blast-radius propagation visible without opening each service card.
- Validation: `npm run build` in `frontend/` clean.

## Immediate next tasks

1. Real gRPC/protobuf gNMI adapter implementing `NativeGnmiAdapter` (still
   blocked on lab hardware or captures).
2. Higher-rate EPS soak (5k+ EPS) once a dedicated lab host is available —
   the laptop ceiling above is the environment, not the pipeline.
3. Add nms-traffic-sim Cisco trap presets aligned with nms-custom classifier
   for BGP, OSPF, fan, PSU, and config-change scenarios.

## Notification rules

I will notify Kapy when:

- a phase completes;
- a meaningful task completes with validation evidence;
- a blocker appears that needs a decision;
- I find a better architectural path than the current plan.

I will avoid noisy updates for every tiny file edit.
