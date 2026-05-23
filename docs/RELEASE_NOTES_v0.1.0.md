# NMS-Custom v0.1.0 — Release Notes

Draft release covering Phases 0 through 6E of the execution plan.

## Highlights

- End-to-end NMS pipeline: inventory, polling, telemetry, assurance, scoring, AI-assisted ops.
- Runtime is split into worker/receiver services with Redis Streams as the canonical event bus.
- Helm chart, Prometheus metrics, Timescale retention and aggregates, and HA/multicluster baselines (`docs/SCALING.md`).
- Local-lab parity via the `nms-traffic-sim` simulator with PCAP fixtures.

## What's included

### Foundation (Phases 0 – 2.5)
- Normalized data model: device, interface, KPI, alarm, audit, credential assignment.
- Standalone worker/receiver entrypoints and Compose services for poller, topology, reports, traps, syslog, telemetry.
- Alembic baseline migrations and worker Redis heartbeats; `/api/system/health` endpoint.

### Event bus and telemetry (Phases 3A – 3E)
- Canonical event envelope and Redis Streams wrapper.
- Telemetry schema, API, and UI; receiver service.
- JSON gNMI / MDT-style adapter, KPI normalization, and event publishing.

### Assurance and service impact (Phases 4A – 4P)
- Root-cause grouping, alarm lifecycle and suppression.
- Topology blast-radius, services and dependencies, service score history.
- Threshold alerts, event-driven snapshots, network score sparkline.
- Manual link-direction override, evidence-bearing score snapshots.

### Scale and production readiness (Phases 5A – 5E)
- Timescale retention policies and continuous aggregates.
- Prometheus metrics across workers and receivers.
- Worker sharding/concurrency, Helm baseline + hardening, CI validation.
- Redis consumer groups, stale pending-event reclaim.

### Local lab and simulator hardening (Phases 5F – 5O)
- Mock-device simulator: syslog, trap, telemetry flows.
- Cisco trap fixtures and classifier; native gNMI contract stub.
- EPS baselines, mixed soak notes, cross-repo simulator presets.

### AI-assisted operations (Phases 6A – 6E)
- Advisory APIs and UI.
- LLM is disabled by default; redaction and citation guardrails.
- RBAC-gated assistant; OpenAI-compatible provider option.

### HA and multi-cluster (post 5E, pre-1.0 hardening)
- `docs/SCALING.md`: capacity planning, multi-AZ, multi-cluster guidance.
- Helm `values-ha.yaml` overlay with hard anti-affinity and HTTPS probes.
- Optional Kafka backend for the event bus via `values-kafka.yaml`.

## Upgrade notes

- Run `alembic upgrade head` to apply migration `0010` (evidence column on `ServiceScoreSnapshot`).
- For HA deployments, pick `values-ha.yaml` overlay and review pod-anti-affinity / replica counts.
- AI Ops requires explicit opt-in: set the provider env vars and grant the `ai_ops:*` RBAC roles.

## Known gaps / next

- P0/P1/P2 settings administration polish items still tracked in `docs/NMS_ARCHITECTURE_EXECUTION_PLAN.md`.
- Service dependency UI: direction-override editor still pending in `ServicesPage.tsx`.
- Assurance and service-trend CSV export not yet wired through `ReportRegistry`.

## References

- `docs/ARCHITECTURE.md` — system architecture, HA and event-bus backends.
- `docs/SCALING.md` — capacity planning and HA topology.
- `docs/NMS_ARCHITECTURE_EXECUTION_PLAN.md` — full phase-by-phase plan and completion notes.
- `docs/SECURITY_REVIEW.md`, `docs/PRODUCTION_RBAC_REVIEW.md` — security posture.
