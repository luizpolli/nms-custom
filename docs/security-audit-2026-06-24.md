# NMS-Custom — Security Audit (SAST-style)

**Date:** 2026-06-24
**Scope:** Full codebase — `backend/` (FastAPI, ~312 Python files), `frontend/` (Vite/React, ~176 TS/TSX), Docker/Compose, Helm, CI/CD, infra config.
**Method:** Six parallel reviewers, one per vulnerability class (injection, authN/authZ/session, secrets/crypto/SSRF, path-traversal/deserialization/file-ops, frontend, infra/supply-chain). Read-only. Findings backed by `file:line` evidence; the two headline authorization findings were manually verified.

---

## Executive summary

The codebase is **well-built defensively**. No injection (SQLi / command / SSTI), no unsafe
deserialization, no XSS, and no XXE were found. Credential storage, password hashing, API-key
comparison, path-traversal guards, and the container/Helm posture are all sound, and a production
boot-guard fails fast on insecure config.

The real risk is **inconsistent per-route authorization** (several high-value mutating routers rely
only on "is authenticated", compounded by a fail-open `admin` default for unmapped API keys) plus a
single **SSRF** surface in the event-forwarding engine.

| Severity | Count | Theme |
|---|---|---|
| HIGH | 5 | Authorization gaps + SSRF + CORS-not-guarded |
| MEDIUM | ~6 | More missing authz gates, Redis auth, exposed ports, image pinning, CI hardening |
| LOW / INFO | ~9 | Token storage, CSV injection, security headers, dev Dockerfile, doc mismatch |

---

## 🔴 HIGH

### H1 — Fail-open admin default for unmapped API keys *(verified)*
- **File:** `backend/app/security/auth.py:285-289` (also dataclass default `Principal.role = "admin"`)
- **Class:** AuthZ — privilege default
- **Evidence:**
  ```python
  role = next(
      (r for k, r in _role_map().items() if _key_matches(presented, k)),
      "admin",                       # default when key not in api_key_roles
  )
  return Principal(subject="api-key", role=role)
  ```
- **Impact:** Any API key that is valid but **not explicitly listed** in `API_KEY_ROLES` is silently
  treated as a full administrator (all settings, user/role CRUD, command execution, interface admin).
  Configuring a low-trust automation key in `API_KEYS` but forgetting the matching `API_KEY_ROLES`
  entry hands out root.
- **Remediation:** Default unmapped keys to a minimal role (e.g. `viewer`), or reject keys with no
  explicit role mapping. Remove the permissive default on `Principal.role`.

### H2 — Credential vault CRUD has no permission gate *(verified)*
- **File:** `backend/app/api/credentials.py:38-102` (router mounted at `app/main.py:167`)
- **Class:** AuthZ — privesc
- **Evidence:** None of `list/create/get/update/delete_credential` declare a `require_*` dependency;
  the only gate is router-level `require_api_auth`.
- **Impact:** Any authenticated key (incl. `viewer`) can read metadata, create, overwrite, or delete
  the SNMP/SSH credentials used to manage **every** device — enabling credential substitution or
  denial of management. The `interfaces:admin_status` route is carefully gated to root/admin, yet the
  higher-value credential store is open.
- **Remediation:** Add a `credentials:*` permission (or reuse `PERM_SETTINGS_NETWORK_SNMP`) and gate
  every mutating route with `require_settings_permission(...)` / `require_roles("root","admin")`.

### H3 — System/infra admin endpoints have no role gate
- **File:** `backend/app/api/system.py:68-115` (mounted `app/main.py:184`)
- **Class:** AuthZ — privesc
- **Evidence:** `POST /containers/{name}/restart`, `POST /backups`, `DELETE /backups/{name}`,
  `PUT /backup-config` declare no permission dependency. (Container name *is* validated against a
  fixed `KNOWN_CONTAINERS` allowlist, so this is authz-only, not command injection.)
- **Impact:** Any authenticated principal can restart containers (DoS), trigger/delete backups, and
  rewrite backup configuration.
- **Remediation:** Gate all state-changing `system` routes with `require_roles("root","admin")` or
  `require_settings_permission(PERM_SETTINGS_SYSTEM)`.

### H4 — SSRF in event-forwarding engine
- **File:** `backend/app/services/forwarding/engine.py:130-153`; created via `app/api/forwarding.py:51-112`;
  validated in `app/schemas/forwarding.py:33-38`
- **Class:** SSRF
- **Evidence:** `target_host`/`target_port` are stored from the API and then connected to server-side
  (HTTP POST, raw TCP, UDP, SNMP). The only validation is a character-class regex
  (`^[A-Za-z0-9_.:-]+$` + reject `..`). `169.254.169.254`, `127.0.0.1`, `10.x`, `docker-proxy`,
  `postgres`, `redis` all pass. `_send_http` also lets `target_host` carry a full `http://...` prefix.
- **Impact:** An authenticated user can register a target (or hit `/targets/{id}/test`) to make the
  backend probe/POST internal infrastructure — cloud metadata, the Docker socket proxy at
  `docker-proxy:2375`, internal DBs — i.e. internal port-scan and event exfiltration.
- **Remediation:** Resolve the host and reject loopback / link-local / RFC-1918 / metadata / ULA
  ranges (re-check after DNS resolution to prevent rebind); restrict scheme to http/https; consider an
  explicit destination allowlist. Also add a role gate on the forwarding router (see M-authz below).

### H5 — CORS `allow_credentials=True` not covered by the production safety guard
- **File:** `backend/app/main.py:82-88`; `backend/app/config.py:109,266-267`
- **Class:** CORS — *Medium confidence*
- **Evidence:** `allow_origins=settings.cors_origins, allow_credentials=True, allow_methods=["*"],
  allow_headers=["*"]`. `cors_origins` is parsed from env and can contain `"*"` or over-broad origins;
  unlike `secret_key`/`https_enabled`/etc., there is **no** `_enforce_production_safety()` check on it.
  Starlette won't echo a literal `*` with credentials, but it *will* reflect any explicitly-listed
  origin with `Access-Control-Allow-Credentials: true`.
- **Impact:** With auth enabled, a permissive/misconfigured origin lets a malicious site make
  credentialed cross-origin calls.
- **Remediation:** Add a `cors_origins` check to `_enforce_production_safety()` that rejects `"*"` and
  any `http://` origin when `app_env=production`; avoid `allow_headers=["*"]` + credentials together.

---

## 🟠 MEDIUM

### M1 — Missing per-route authorization on additional mutating routers
- **Files / routes (only router-level `require_api_auth`, no permission gate):**
  - `app/api/devices/crud.py:46-88` — create/update/delete devices
  - `app/api/mibs.py:59,100,114,123` — MIB create/update/delete/upload
  - `app/api/devices/snmp_ops.py:67,109,121` — verify-credentials, poll, discover-neighbors
  - `app/api/discovery.py:45` — `POST /scan`
  - `app/api/bulkstats.py:48,66` — catalog create/update
  - `app/api/forwarding.py:51,75,96,105` — forwarding-target CRUD/test (also enables H4)
- **Impact:** Low-privilege keys can tamper with inventory, upload arbitrary MIB files, trigger network
  scans/polling, and edit bulkstats catalogs.
- **Remediation:** Add appropriate `require_command_permission(...)` / `require_settings_permission(...)`
  per route.

### M2 — Bundled Redis unauthenticated + protected-mode disabled
- **File:** `infra/redis/redis.conf:2-3` (`protected-mode no`, `bind 0.0.0.0`, no `requirepass`);
  `config.py:88` defaults `redis_password=""`; Helm `templates/postgres-redis.yaml:48-78` sets no
  password and relies on `networkPolicy.enabled` which is **off by default** (`values.yaml:126`).
- **Impact:** Anything that can reach 6379 has full unauthenticated access to the event bus and
  rate-limit store.
- **Remediation:** Set `requirepass`/`REDIS_PASSWORD`, keep `protected-mode yes`, add `redis_password`
  empty-in-prod to the boot guard; don't depend on a disabled-by-default NetworkPolicy.

### M3 — Postgres/Redis ports published to the host in Compose
- **File:** `docker-compose.yml:94-95` (`5432:5432`), `:119-120` (`6379:6379`); default DB password
  `nms_secret` (`config.py:78`).
- **Impact:** Datastore exposure beyond the Compose network, combined with weak default password and
  unauthenticated Redis (M2).
- **Remediation:** Drop the host port mappings (services already talk over `nms-net`), or bind to
  `127.0.0.1:...` for local debugging only.

### M4 — Floating `latest` / mutable image tags
- **File:** `docker-compose.yml:39,83,108,452,484,513`; `helm/nms-custom/values.yaml:2-3,51,61`; CI
  service images.
- **Impact:** Non-reproducible builds; a re-pull can silently swap a different/compromised image.
- **Remediation:** Pin to immutable digests (`image@sha256:...`) or exact version tags.

### M5 — CI: GITHUB_TOKEN default (write) permissions
- **File:** `.github/workflows/ci.yml`, `e2e.yml`, `security.yml` — no `permissions:` block anywhere.
- **Impact:** Every job (incl. ones running third-party actions) inherits a broad token.
- **Remediation:** Add top-level `permissions: contents: read`; escalate per-job only where needed.

### M6 — CI: third-party actions pinned by mutable tag, not SHA
- **File:** `security.yml:88` (`gitleaks-action@v3`), `:96` (`trivy-action@v0.36.0`),
  `ci.yml:161` (`setup-helm@v4`).
- **Impact:** A re-pointed tag can introduce malicious code into the pipeline.
- **Remediation:** Pin third-party actions to full commit SHAs (`@<sha> # v3`).

---

## 🟡 LOW / INFORMATIONAL

- **L1 — API key in `localStorage`** (`frontend/src/lib/api.ts:14`): XSS-stealable, persists
  indefinitely. No XSS exists today, so exploitability is low. Prefer an httpOnly+SameSite cookie.
- **L2 — Bare `axios` imports bypass auth+demo interceptor:** `topology/components/RebuildButton.tsx`,
  `discovery/DiscoveryPage.tsx`, `mibs/MIBsPage.tsx`, `reports/ReportsPage.tsx`,
  `reports/components/ReportParamsForm.tsx`. Same-origin → low impact, but they omit `X-API-Key`.
  Route all calls through the shared `api` instance.
- **L3 — CSV / formula injection in exports:** `app/api/alarms.py:198-203`, `app/api/devices/export.py:79-84`,
  `app/api/settings/audit.py:119-136`, `app/services/command_export.py:38-45`. Alarm `message`/`source_host`
  originate from inbound SNMP traps/syslog (device/attacker-influenceable). Neutralize cells whose first
  char is in `= + - @ \t \r`.
- **L4 — Command allowlist is allow-all by default** (`app/security/allowlist.py:36-50`): authenticated
  users with `commands:run` can send arbitrary device CLI when `COMMAND_ALLOWLIST` is empty. (Device
  CLI only, not host shell — asyncssh exec channel; control chars `\r\n\x00` are blocked.) Ship a
  restrictive default or fail-closed in prod.
- **L5 — Grafana default `admin/admin`** (`docker-compose.yml:527`, `.env.example`): not covered by the
  app's prod guard. Require a strong value.
- **L6 — Doc/impl mismatch:** `config.py:322-341` and `.env.example` describe
  `CREDENTIAL_ENCRYPTION_KEY` as "hex", but `app/security/crypto.py` uses base64. Operators supplying a
  hex string get the wrong key. Align wording on base64.
- **L7 — No security-headers middleware:** no HSTS / X-Content-Type-Options / X-Frame-Options / CSP
  emitted (`app/main.py` middleware stack). Add a response-header middleware (or document that ingress
  injects them).
- **L8 — Helm bundled Postgres/Redis have no resource limits**
  (`helm/nms-custom/templates/postgres-redis.yaml`): noisy-neighbor / DoS risk. Add requests/limits.
- **L9 — Frontend Dockerfile uses `npm install` (not `npm ci`)** and ships the Vite dev server as the
  container CMD (`frontend/Dockerfile:7-9,18`). Use `npm ci`; serve built static assets via nginx for
  non-dev deployments.
- **L10 — Permission checks disabled when `API_AUTH_ENABLED=false`** (default): the whole API is open.
  **Mitigated** by the prod boot-guard refusing to start when `APP_ENV=production` and auth is off
  (`config.py:344-348`). Residual: non-prod envs (`development`/`staging`) are fully open — consider
  treating `staging` like `production`.
- **MIB regex parser DoS** (`app/services/snmp/mib_parser.py:49-79`): linear-ish, size-capped by
  `mib_upload_max_bytes`; not catastrophic. Optional regex timeout.

---

## Confirmed secure (reviewed, no issue)

- **SQL injection:** all DB access is SQLAlchemy ORM or bound-parameter `text()` (retention, KPI engine,
  alembic). The recent "bind object_id as a parameter" fix pattern is correctly applied; no analogous
  string-interpolated SQL remains. Migrations use static SQL literals.
- **Command injection:** subprocess calls use `asyncio.create_subprocess_exec` (argv arrays, no shell);
  no `shell=True` / `os.system` / `os.popen`. Device CLI goes over a dedicated asyncssh exec channel;
  interface names are gated by a strict regex; control chars blocked.
- **SSTI / code injection:** no runtime jinja2/mako rendering of user input; no `eval`/`exec`/
  `pickle.loads`/`yaml.load` on untrusted data. The only `ast.literal_eval` parses a settings value.
- **Credential storage:** AES-256-GCM, random 12-byte nonce per encryption; API never returns plaintext
  (only a `has_secret` boolean); decryption only at SSH/SNMP connect time.
- **Password hashing:** PBKDF2-HMAC-SHA256, 210k iterations, 16-byte random salt, constant-time compare.
- **API-key verification:** constant-time `hmac.compare_digest`, supports `sha256$` pre-hashed keys.
- **Path traversal:** guards present and effective at every request-driven filesystem sink (MIB upload,
  command export, backup delete, chassis profile lookup, bulkstats ingestion, audit log).
- **Deserialization / XXE / zip-slip:** none present — no pickle/yaml.load/dill, no XML parsing, no
  archive extraction.
- **Frontend XSS:** no `dangerouslySetInnerHTML`, `innerHTML`/`outerHTML`, `document.write`, `eval`,
  `new Function`, `insertAdjacentHTML`; device strings rendered via auto-escaping JSX; SVGs referenced
  only via `<img src>` (cannot execute script). No open redirect, no `postMessage`, no `target=_blank`.
- **Container/Helm posture:** non-root, `readOnlyRootFilesystem`, `cap_drop: ALL`, `no-new-privileges`,
  `seccompProfile: RuntimeDefault`, Docker *socket-proxy* (not raw socket), secrets via `secretKeyRef`/
  ExternalSecrets (not plaintext ConfigMaps). No privileged/hostPath/hostNetwork.
- **Secret scanning & dep advisories:** gitleaks v3, trivy, bandit, pip-audit, npm audit all wired in
  CI; pydantic-settings `2.14.2` and vite `8.0.16` confirm the advisory bumps landed.
- **Rate limiting:** tight "sensitive" bucket on `/api/commands`, `/api/credentials`, settings, ai-ops,
  mibs; per-key (hashed) or per-IP identity.

---

## Suggested remediation order

1. **H1** (admin default → least-privilege) — smallest change, removes the systemic amplifier.
2. **H2, H3, M1** (add per-route authz gates) — the bulk of the real exposure.
3. **H4 + forwarding authz** (SSRF range-blocking + role gate).
4. **H5 / M2 / M3** (CORS guard, Redis auth, drop host ports) — config hardening.
5. **M4–M6** (image digests, GITHUB_TOKEN perms, action SHAs) — supply-chain.
6. LOW items as cleanup.

*Generated by an automated multi-agent SAST review. Findings list `file:line` evidence; verify against
current `HEAD` before remediation as the tree may have moved since this snapshot.*
