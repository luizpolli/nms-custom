# Functional Manual — NMS_Custom

This manual describes what each major module does, how operators use it, and the security/operational notes that matter in labs and early production.

## 1. Dashboard and NOC overview

**Purpose:** give operators a first screen for health, active alarms, network score, KPI status, and lab/runtime signals.

**Typical workflow**

1. Open the frontend at the configured `FRONTEND_PORT`.
2. Review top-level health cards and severity counts.
3. Drill into alarms, assurance groups, devices, services, or lab health from the relevant card.
4. Use score trends and sparklines to decide whether an issue is new, worsening, or recovering.

**Notes**

- Dashboard data is derived from normalized device, KPI, alarm, assurance, and worker-health models.
- The NMS also monitors itself through worker heartbeat and event-bus metrics.

## 2. Inventory and device management

**Purpose:** maintain the managed-device source of truth.

**Core capabilities**

- Create, list, update, and delete network devices.
- Track device role, site, lifecycle state, platform family, management VRF, and feature toggles.
- Enable or disable SNMP, SSH, and telemetry collection per device.
- Attach credential profiles explicitly instead of embedding secrets in device records.
- Inspect related interfaces, KPIs, alarms, topology links, and telemetry state.

**Operational guidance**

- Keep lifecycle state accurate so lab/decommissioned devices do not pollute assurance views.
- Prefer SNMPv3 and SSH credentials for real devices.
- Avoid enabling telemetry on devices until the receiver and subscription path are ready.

## 3. Credential vault

**Purpose:** store reusable access profiles for SNMP/SSH/API-style access.

**Core capabilities**

- Store plaintext input only at create/update time; secrets are encrypted before persistence.
- Return metadata such as `has_secret`, not plaintext secrets.
- Support explicit credential-to-device assignment.
- Emit redacted audit events for sensitive actions.

**Security guidance**

- Generate real `CREDENTIAL_ENCRYPTION_KEY` and `CREDENTIAL_ENCRYPTION_IV` values for any non-local deployment.
- Rotate credentials regularly and update device assignments deliberately.
- Do not commit `.env` files or exported database dumps containing encrypted secrets.

## 4. SNMP monitoring and KPI engine

**Purpose:** poll devices and normalize counters into useful KPIs.

**Core capabilities**

- Poll common SNMP counters for CPU, memory, interface, QoS, and custom MIB-backed values.
- Normalize samples with source type, object type, object ID, metric name, unit, quality/status, and labels.
- Store durable KPI samples and short-retention raw data where applicable.
- Evaluate thresholds and create/update alarm state when metrics breach configured limits.

**Typical workflow**

1. Add device and credential profile.
2. Enable SNMP on the device record.
3. Choose or create a monitoring policy.
4. Let the poller collect samples.
5. Review device KPIs, threshold alerts, and assurance impact.

## 5. MIB management

**Purpose:** support custom MIB metadata and trap/KPI interpretation.

**Core capabilities**

- Upload `.mib`, `.my`, or `.txt` files within the configured size limit.
- Parse SMIv2 module identity and notification metadata.
- Store MIB metadata and parsed summaries.
- Reference custom MIBs from monitoring/trap-classification workflows.

**Security notes**

- Uploads normalize filenames, reject path traversal, enforce extension allow-lists, and cap file size.
- Treat third-party MIBs as untrusted input; only upload from known sources in shared environments.

## 6. Fault, alarms, and alarm rules

**Purpose:** convert traps, syslog, telemetry events, and threshold breaches into actionable fault state.

**Core capabilities**

- Maintain alarm lifecycle fields: severity, status, first/last seen, occurrence count, dedup key, source type, object identity, root alarm, and correlation group.
- Acknowledge, clear, and suppress alarms with audit trail.
- Classify Cisco-ish trap fixtures and data-driven custom rules.
- Correlate related alarms into root-cause/assurance groups.

**Typical workflow**

1. Review active alarms by severity.
2. Open an alarm group to see related events and root-cause candidates.
3. Check impacted service/device/interface/topology context.
4. Acknowledge or suppress noise with a clear reason.
5. Clear once the underlying condition is fixed.

## 7. Assurance and service impact

**Purpose:** show blast radius, root-cause context, impacted services, and network health trend.

**Core capabilities**

- Build assurance groups from correlated alarms and topology evidence.
- Calculate service impact and network score.
- Track service score history and network score sparklines.
- Trigger event-driven snapshots so changes in alarm state are reflected quickly.

**Typical workflow**

1. Start from an alarm group or service view.
2. Review severity, affected devices/interfaces, and dependent services.
3. Use topology blast-radius evidence to confirm likely propagation.
4. Prioritize the repair that improves the highest-impact service score.

## 8. Topology

**Purpose:** discover and visualize network relationships.

**Core capabilities**

- Refresh LLDP/CDP-derived topology.
- Store topology nodes and links separately from raw discovery payloads.
- Use topology links for alarm blast-radius and service dependency scoring.

**Guidance**

- Validate LLDP/CDP visibility before trusting blast-radius calculations.
- Use manual service dependency modeling for business-critical paths that protocol discovery cannot infer.

## 9. Discovery

**Purpose:** find candidate devices and refresh inventory details.

**Core capabilities**

- Chunk subnet scans based on `DISCOVERY_CHUNK_SIZE` and `DISCOVERY_MAX_HOSTS`.
- Validate SNMP community-like input before running discovery.
- Fan discovery events through workers for refresh workflows.

**Security notes**

- Discovery can be noisy. Limit ranges in shared labs.
- Do not use default community strings outside a disposable lab.

## 10. SSH command execution

**Purpose:** run saved or ad-hoc CLI commands against devices through managed credentials.

**Core capabilities**

- Save command definitions per device.
- Run saved or ad-hoc commands over SSH.
- Persist output for saved commands.
- Audit command execution with exit status.

**Security notes**

- Current validation rejects control characters and bounds command length.
- Before production use, add command allow-lists and separate roles for command create/run.
- Keep SSH host-key checking enabled unless a lab exception is explicitly documented.

## 11. Reporting and schedules

**Purpose:** export inventory, KPI, alarm, and health information.

**Core capabilities**

- Generate report jobs.
- Schedule recurring reports.
- Export operator-facing summaries for later review.

**Guidance**

- Treat generated reports as sensitive because they may reveal topology, device names, and alarm history.
- Prefer sanitized exports for demos or public issue reports.

## 12. Telemetry and native gNMI path

**Purpose:** ingest streaming telemetry and normalize it into the same KPI/event model as SNMP.

**Core capabilities**

- Manage telemetry collectors, sensor paths, and subscriptions.
- Receive gNMI-like/MDT-like line-delimited JSON in the lab receiver.
- Normalize telemetry samples to KPI/event records.
- Publish telemetry events to Redis Streams for worker fan-out.
- Provide a native gNMI protobuf contract and stub adapter for future real transport.

**Current limitations**

- The real native gRPC/protobuf `NativeGnmiAdapter` is intentionally blocked until compatible lab hardware/test servers are available.
- Real deployment should require TLS/mTLS, backpressure handling, per-device credentials, and subscription lifecycle management.

## 13. Event bus and workers

**Purpose:** decouple ingestion/API actions from background processing.

**Runtime roles**

- `worker-poller` — monitoring policies and KPI sampling.
- `worker-topology` — LLDP/CDP graph refresh.
- `worker-report` — scheduled report generation.
- `worker-alarm` — alarm event consumer.
- `worker-discovery` — discovery event consumer and refresh fan-out.
- `worker-telemetry` — telemetry event consumer and KPI fan-out.
- `syslog-receiver`, `trap-receiver`, `telemetry-receiver` — external ingestion boundaries.

**Event-bus behavior**

- Uses Redis Streams consumer groups with `XGROUP`, `XREADGROUP`, `XACK`, and stale-event reclaim.
- Event envelopes include source/type/timestamp/trace-style metadata so Kafka/NATS could be introduced later without a full domain rewrite.

## 14. Lab Health

**Purpose:** monitor the NMS pipeline itself during simulator and soak runs.

**Core capabilities**

- Show API/worker/receiver/event-bus health.
- Track telemetry, alarms, and event-bus EPS.
- Display EPS distributions and latency histograms.
- Run a snapshot and export JSON for lab evidence.

**Typical workflow**

1. Start Compose services.
2. Drive traffic with `nms-traffic-sim`.
3. Open Lab Health.
4. Watch EPS, consumer lag, latency buckets, and worker heartbeats.
5. Export a JSON snapshot after each scenario.

## 15. AI Ops assistant and advisory APIs

**Purpose:** assist operators with deterministic advisory output and optional LLM-backed summaries.

**Core capabilities**

- Deterministic advisory endpoints for alarm groups, KPI anomalies, runbook hints, and narrative summaries.
- Optional assistant endpoint behind `AI_OPS_LLM_ENABLED`.
- Role gate for assistant calls; defaults to `admin,ai-ops`.
- Provider abstraction with a built-in deterministic `NullLLMProvider` and an optional OpenAI-compatible chat-completions adapter.
- Redaction for IPs, MACs, FQDNs, secrets, SNMP communities, and private keys.
- Citation enforcement: assistant answers must cite retrieved evidence IDs in `[prefix:id]` format.
- Question and answer length caps.

**Security guidance**

- Keep external LLM providers disabled until provider retention, logging, and egress policies are approved. Configure `AI_OPS_LLM_PROVIDER=openai-compatible`, `AI_OPS_LLM_BASE_URL`, `AI_OPS_LLM_MODEL`, and `AI_OPS_LLM_API_KEY` only for approved environments.
- Never relax citation enforcement for operational recommendations.
- Treat redaction as a guardrail, not as permission to send raw secrets to third parties.

## 16. Access control and account audit

**Purpose:** manage who can use the NMS, what each role can do, and review account activity without exposing sysadmin-only filesystem paths in the GUI.

**Core capabilities**

- Use **Settings -> Access Control** for local Web GUI users, NBI users, roles, task permissions, virtual domains, and account audit review.
- Export account activity as CSV from the GUI for customer-facing review or compliance evidence.
- Keep identity/RBAC configuration separate from audit evidence in the backend.
- Use **Settings -> Notifications & Forwarding** for SMTP mail notification settings, mail validation, and event forwarding targets.
- Event Forwarding targets can subscribe to **Account Audit** events for non-root/non-admin login, logout, and privilege-change alerts.

**Sysadmin audit paths**

- Normal user/API activity is written to `data/audit/account_audit.jsonl` by default.
- Admin/root activity is also written to `data/audit/privileged_account_audit.jsonl` by default.
- Override paths with `ACCOUNT_AUDIT_LOG_PATH` and `PRIVILEGED_ACCOUNT_AUDIT_LOG_PATH` when the deployment needs dedicated volumes or external log collection.
- Treat the privileged audit file as restricted evidence; ship or retain it with stricter access controls than normal operator exports.

## 17. Deployment modes

### Local Compose

Best for development, demos, and simulator-driven labs.

- Easy startup with `make up` / `docker compose up --build`.
- Publishes API, frontend, data stores, and ingestion ports for convenience.
- Requires firewall/localhost binding changes before shared-network use.

### Kubernetes/Helm

Best target for production-like labs.

- API, frontend, workers, receivers, Postgres, and Redis have chart boundaries.
- Values include toggles for auth, HTTPS, ExternalSecret, NetworkPolicy, autoscaling, and PDBs.
- NetworkPolicy and secret-manager wiring still need environment-specific completion.

## 18. Minimal operating runbook

1. Copy `.env.example` to `.env` and replace every placeholder secret.
2. Start services with `make up` or `docker compose up --build -d`.
3. Confirm API health at `/health` and frontend availability.
4. Add credentials and devices.
5. Enable SNMP/SSH/telemetry only for devices that are ready.
6. Start simulator or real lab traffic.
7. Watch Lab Health for EPS, lag, and worker heartbeat.
8. Review alarms, assurance groups, service impact, and topology.
9. Export snapshots/reports for evidence.
10. Stop with `make down` when done.
