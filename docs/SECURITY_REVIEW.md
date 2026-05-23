# Security Review — NMS_Custom

Review date: 2026-05-19

Scope: configuration, API auth/RBAC, TLS, AI Ops LLM guardrails, ingestion surfaces, MIB upload, SSH command execution, Docker Compose exposure, and Helm production posture.

## Current posture summary

NMS_Custom is still lab/development-friendly by default, but the main production controls are present:

- API routes are wired through a shared API-key dependency when `API_AUTH_ENABLED=true`.
- AI Ops LLM is disabled by default and uses a deterministic null provider unless explicitly enabled.
- AI Ops assistant answers are retrieval-grounded, citation-gated, length-limited, and redacted before provider handoff.
- Credential payloads are encrypted at rest by the credential vault and sensitive audit/log values are redacted.
- HTTPS can be enabled with TLS 1.3 minimum and Compose defaults currently enable HTTPS.
- MIB uploads have path traversal protection, extension allow-listing, and a size limit.
- Runtime collectors/workers are split so API, receivers, workers, Redis, and Timescale can be isolated later with Compose/Kubernetes network controls.

## Findings and recommendations

### P0 — Must do before internet/lab-wide exposure

1. **Replace all development defaults before deployment.**
   - Defaults such as `SECRET_KEY=change-me-to-a-real-secret-key`, `POSTGRES_PASSWORD=nms_secret`, `SNMP_DEFAULT_COMMUNITY=public`, and placeholder credential encryption material are unsafe outside local labs.
   - Set `APP_ENV=production`, `DEBUG=false`, `API_AUTH_ENABLED=true`, strong `API_KEYS`, strong role mappings, and generated encryption keys.

2. **Do not expose data stores directly.**
   - Compose publishes Postgres `5432` and Redis `6379` by default for local convenience.
   - In shared labs or production, bind these to localhost, remove the published ports, or place the host behind a firewall/VPN.

3. **Restrict ingestion receiver exposure.**
   - `syslog-receiver` (`5514/udp`), `trap-receiver` (`1162/udp`), and `telemetry-receiver` (`57400/tcp`) accept network-originated data and currently rely on host/network controls.
   - Only allow trusted simulator/device subnets. Prefer firewall allow-lists or Kubernetes NetworkPolicies.

4. **Use real TLS material.**
   - The server can generate a development self-signed cert when files are missing. That is useful for lab bootstrapping, not production trust.
   - Mount a real certificate/key pair and keep `TLS_MIN_VERSION=TLSv1.3` unless legacy clients force TLS 1.2.

### P1 — Recommended hardening next

1. **Keep command execution least-privilege.**
   - SSH command execution is API-auth gated, audited, role/permission separated by command action, and can be restricted by `COMMAND_ALLOWLIST`.
   - Before shared lab or production use, configure least-privilege `API_KEY_ROLES` and a command allow-list appropriate for the managed device fleet.

2. **Add receiver-level authentication where protocols allow it.**
   - Native gNMI should require TLS/mTLS and per-device credentials.
   - Syslog/SNMP trap ingestion should stay restricted by source networks because the protocols are weakly authenticated in common lab modes.

3. **Improve API-key lifecycle management.**
   - API key comparisons use constant-time checks and `API_KEYS` / `API_KEY_ROLES` may use `sha256$<hex-digest>` values to avoid plaintext keys in env files.
   - For higher assurance, add key IDs, rotation runbooks, and per-key audit metadata.

4. **Container production hardening.**
   - Add non-root runtime users, read-only filesystems where possible, dropped Linux capabilities, and stricter volume mounts for Compose/Helm.

### P2 — Later assurance improvements

- Add rate limits/body-size limits at ingress for API and telemetry receiver paths.
- Add signed/verified MIB source provenance if users upload third-party MIB packs.
- Add security regression tests for host allow-listing, command RBAC, TLS config, and ingestion bounds.
- Add secret-manager examples for Docker/Helm deployments.

## Control inventory

| Area | Current control | Residual risk |
| --- | --- | --- |
| API auth | `API_AUTH_ENABLED`, `API_KEYS`, `API_KEY_ROLES`; router-level dependency on API routes; constant-time plaintext or `sha256$<hex>` key matching | Disabled by default for local dev; key IDs/rotation are still manual |
| RBAC | Role dependency available; AI Ops assistant restricted to `admin,ai-ops` by default | Most API routes are broad API-key authenticated, not per-action authorized |
| TLS | Optional HTTPS with TLS min version; Compose defaults enable HTTPS | Development self-signed cert auto-generation if cert/key missing |
| CORS / host headers | Configurable `CORS_ORIGINS`; `ALLOWED_HOSTS` enforced by Trusted Host middleware with localhost/test/container dev defaults | Production deployments must set explicit public hostnames; avoid `*` |
| Credentials | Vault encryption plus log/audit redaction | Placeholder keys in examples; key rotation docs should be expanded |
| AI Ops LLM | Disabled by default; null provider; optional OpenAI-compatible adapter; redaction; evidence citations; max lengths; role gate | External provider use still needs provider-specific egress/retention review before enabling |
| MIB uploads | Filename normalization, traversal check, extension allow-list, size cap | Parser treats content as text; malicious large/complex MIBs need fuzz/timeout coverage |
| Ingestion | Dedicated receivers and event envelope | UDP/TCP listeners rely on firewall/network policy; unauthenticated protocol modes |
| SSH commands | Auth-gated, audited, bounded length, no control chars, command-action RBAC, optional `COMMAND_ALLOWLIST` | Production deployments must explicitly configure roles and allow-list patterns |
| Compose exposure | Clear service/port map | Datastores and receivers publish host ports by default |
| Helm | Production values for auth/HTTPS, ingress/TLS, NetworkPolicy, PDB, HPA, ExternalSecret, and dev/prod/HA lint/render CI gates | NetworkPolicy is intentionally disabled by default values; production overrides enable it |

## Production deployment checklist

Before exposing beyond a single local developer machine:

- [ ] `APP_ENV=production` and `DEBUG=false`.
- [ ] `API_AUTH_ENABLED=true` with at least two rotated, high-entropy API keys.
- [ ] `API_KEY_ROLES` maps keys to least-privilege roles; prefer `sha256$<hex-digest>` keys outside local dev.
- [ ] `SECRET_KEY`, credential encryption key, and database passwords are generated secrets, not examples.
- [ ] `SNMP_DEFAULT_COMMUNITY` is not `public`; prefer SNMPv3 credentials.
- [ ] `CORS_ORIGINS` and `ALLOWED_HOSTS` are explicit.
- [ ] Postgres/Redis ports are not reachable from untrusted networks.
- [ ] Ingestion receiver ports are limited to trusted source subnets.
- [ ] TLS cert/key are mounted from a trusted issuer or internal CA.
- [ ] AI Ops external providers remain disabled until data retention, logging, and redaction are reviewed; only enable `openai-compatible` with approved base URL/model/API key handling.
- [ ] SSH command endpoints are limited to trusted admins/operators and backed by `COMMAND_ALLOWLIST`.
