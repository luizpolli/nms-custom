# NMS-Custom v1.1.0 — Release Notes

Covers the 130+ commits landed since v1.0.0 (2026-05-20 → 2026-06-11).

## Highlights

- **Chassis View shipped end-to-end** — 14 device profiles rendered with real EPNM SVG assets, live alarm overlay, and per-port detail panel.
- **AI Ops** — deterministic advisory endpoints plus an optional LLM assistant with strict redaction and citation guardrails (`NullLLMProvider` by default).
- **Security hardening (P2.x)** — body-size limit middleware, MIB source provenance, secret-manager integration guides, and a security regression test suite.
- **mypy promoted to a required CI gate** — type errors went from 220 to 0 (P1.7).
- **Self-monitoring stack** — opt-in Prometheus + Grafana + Alertmanager Compose profile (P2.11).

## Chassis View (Phase 6D, Fases 1–6)

- 14 chassis profiles across 4 platform families: ASR903/920, ASR9006/9010, NCS55A1, NCS560, NCS540 variants, NCS540X.
- Real EPNM SVG artwork merged with live ENTITY-MIB SNMP inventory; hotspots color-coded by worst alarm severity.
- Overlay render policy suppresses hotspot chrome that duplicates base SVG artwork.
- Port detail slide-out panel with interface KPIs and per-port alarm list.
- Port inventory table (physical/logical) backed by managed-interface data.
- Profile auto-detection from SNMP model strings (case/dash-insensitive) with detection test suite.
- ASR920 SNMP walk fixtures and MIB reference set committed under `docs/snmpwalks/` and `docs/MIBs/`.

## AI Ops (Phases 6A–6C)

- Deterministic advisory endpoints: alarm-group analysis, KPI anomalies, runbooks, narrative summaries — no LLM required.
- Optional GPT-compatible assistant: PII/secret redaction (IPs, MACs, FQDNs, communities, PEM keys), enforced citations, retrieval-grounded answers, provider-agnostic adapter.
- Settings panel for provider config: base URL, timeout, model, prompt hint.
- `/ai-ops` frontend page with advisory cards and assistant chat.

## Security (P2.1–P2.3)

- Request body-size limit middleware with per-route caps.
- MIB source provenance: SHA-256 checksum + upload metadata stored at ingest.
- Secret-manager examples and integration guide (Vault, AWS Secrets Manager).
- Security regression test suite; syslog payload size guard.
- Dependency hygiene: vitest 2→4 and react-router audit fixes — `npm audit` clean.

## Dashboard & Observability

- Customizable dashboard with drag-and-drop widget grid.
- EPNM-style trend charts, heatmap, and interface utilization widgets.
- Prometheus + Grafana + Alertmanager opt-in Compose profile with docs (`docs/OBSERVABILITY.md`).
- Lab Health trend export endpoint + frontend Export button.

## Quality & Refactoring

- mypy: 220 → 0 errors; now a hard CI gate (P1.7).
- `backend/app/api/settings.py` split into a package; Settings frontend decomposed into panel components (P1.5).
- Test coverage grew to 505 backend tests (64 files) and 299 frontend tests (30 files).
- Playwright e2e suite wired into CI with smoke checks and CI-specific Compose override.

## CI / Tooling

- GitHub Actions migrated to Node 24 runners: `checkout@v5`, `setup-node@v5`, `setup-python@v6`, `upload-artifact@v5`.
- e2e workflow stabilized: health polling, dependency-ordered startup, debug capture gated behind `E2E_DEBUG`.

## Upgrade notes

- No breaking API changes. Alembic migration chain unchanged since v1.0.0 baseline.
- New optional env vars for AI Ops provider config; LLM remains disabled unless `AI_OPS_LLM_ENABLED=true`.
- To enable self-monitoring: `docker compose --profile monitoring up -d`.
