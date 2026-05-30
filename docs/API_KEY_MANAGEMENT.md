# API Key Management Guide

This document covers the full lifecycle of API keys in NMS-Custom: generation,
configuration, role mapping, rotation, and the `COMMAND_ALLOWLIST` that governs
which device commands operators may execute through the API.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Key Generation Best Practices](#2-key-generation-best-practices)
3. [Hashed Key Configuration (`sha256$<hex>`)](#3-hashed-key-configuration-sha256hex)
4. [Per-Key Role Mapping (`API_KEY_ROLES`)](#4-per-key-role-mapping-api_key_roles)
5. [Command Allow-List (`COMMAND_ALLOWLIST`)](#5-command-allow-list-command_allowlist)
6. [Key Rotation Runbook](#6-key-rotation-runbook)
7. [Recommended Production Defaults](#7-recommended-production-defaults)
8. [Auditing & Monitoring](#8-auditing--monitoring)
9. [Kubernetes / Helm Deployment Notes](#9-kubernetes--helm-deployment-notes)

---

## 1. Overview

When `API_AUTH_ENABLED=true` the application validates every `/api/*` request
against the `API_KEYS` environment variable (or its equivalent Kubernetes
Secret). A request is authenticated if the `X-API-Key` header matches one of
the configured keys.

```
Client ──X-API-Key: <key>──► FastAPI middleware
                              │
                              ├─ hash(key) matches sha256$<hex>?  → OK
                              └─ key matches plaintext?            → OK (dev only)
```

**Authentication is disabled by default** (`API_AUTH_ENABLED=false`) to allow
zero-friction local development. Enable it before any deployment that is
reachable by more than one person.

---

## 2. Key Generation Best Practices

### Entropy requirements

| Use-case | Minimum entropy | Recommended generator |
|---|---|---|
| Admin key | 256 bits | `openssl rand -hex 32` |
| Service-to-service key | 128 bits | `openssl rand -hex 16` |
| Read-only / monitoring key | 128 bits | `openssl rand -hex 16` |

### Generation commands

```bash
# 32-byte (256-bit) random key — suitable for admin and long-lived keys
openssl rand -hex 32

# 16-byte (128-bit) key — suitable for service accounts
openssl rand -hex 16

# Python alternative (if openssl unavailable)
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### Rules

- **Never reuse** keys across environments (dev / staging / prod).
- **Never commit** raw keys to source control — use environment variables or a
  secrets manager.
- Store the raw key **only once** at generation time; only the hash is stored
  in configuration.
- Apply key expiry policies for long-lived service accounts (90 days
  recommended).
- Rotate immediately on suspected compromise (see §6).

---

## 3. Hashed Key Configuration (`sha256$<hex>`)

Storing raw API keys in environment variables or Kubernetes Secrets exposes
them to log scraping and `kubectl get secret` access. NMS-Custom supports
**prehashed** key entries so the live token never appears in configuration.

### Generating a hashed entry

```bash
# Generate a new key and its hash in one step
RAW_KEY=$(openssl rand -hex 32)
HASH=$(echo -n "$RAW_KEY" | sha256sum | awk '{print "sha256$"$1}')

echo "Raw key (store securely, give to caller): $RAW_KEY"
echo "Config entry (store in .env / Secret):    $HASH"
```

Example output:
```
Raw key: a3f1...c9e2
Config entry: sha256$7b8d2f...3c4a
```

### Setting hashed keys in `.env`

```dotenv
# Comma-separated list; mix of hashed and plaintext is allowed.
# Plaintext entries are accepted but NOT recommended outside local dev.
API_KEYS=sha256$7b8d2f...3c4a,sha256$9e1a4c...0f2b
```

The application computes `sha256(incoming_key)` and compares against each
`sha256$<hex>` entry in constant time (using `hmac.compare_digest`) so timing
attacks are not possible even with plaintext entries.

> **Note:** The role map (`API_KEY_ROLES`) must use the **same form** as
> `API_KEYS`. If a key is stored hashed, its role entry must also use the hash.

---

## 4. Per-Key Role Mapping (`API_KEY_ROLES`)

By default, every authenticated key is treated as an `admin`. Use
`API_KEY_ROLES` to assign least-privilege roles to individual keys.

### Format

```dotenv
API_KEY_ROLES=<key-or-hash>:<role>[,<key-or-hash>:<role>...]
```

### Available roles

| Role | Description |
|---|---|
| `admin` | Full access: devices, credentials, users, settings, commands |
| `operator` | Read/write for devices, alarms, topology; no user/settings management |
| `read-only` | GET requests only across all resources |
| `ai-ops` | Access to AI Ops endpoints only (`/api/ai-ops/*`) |

### Example

```dotenv
# Generate two keys
ADMIN_KEY=$(openssl rand -hex 32)
ADMIN_HASH=$(echo -n "$ADMIN_KEY" | sha256sum | awk '{print "sha256$"$1}')

AIOPS_KEY=$(openssl rand -hex 32)
AIOPS_HASH=$(echo -n "$AIOPS_KEY" | sha256sum | awk '{print "sha256$"$1}')

# .env configuration
API_KEYS=${ADMIN_HASH},${AIOPS_HASH}
API_KEY_ROLES=${ADMIN_HASH}:admin,${AIOPS_HASH}:ai-ops
```

### Fallback behaviour

A key present in `API_KEYS` but absent from `API_KEY_ROLES` defaults to the
`admin` role for backward compatibility. To apply strict least-privilege,
ensure **every** key has an explicit role mapping.

---

## 5. Command Allow-List (`COMMAND_ALLOWLIST`)

The `COMMAND_ALLOWLIST` variable restricts which commands operators may send to
managed devices via the SSH command execution API (`POST /api/devices/{id}/exec`).

### Format

Comma-separated **Python regular expressions**. A command is permitted only
when it fully matches at least one pattern (`re.fullmatch`). An empty list
means **all commands are permitted** (development default).

```dotenv
# Development — no restriction (empty = allow all)
COMMAND_ALLOWLIST=

# Production — restrict to read-only Cisco IOS/IOS-XR/NX-OS commands
COMMAND_ALLOWLIST=show\s+.*,ping\s+.*,traceroute\s+.*,dir\s+.*
```

### Pattern reference for Cisco devices

| Category | Pattern | Example commands allowed |
|---|---|---|
| Show commands | `show\s+.*` | `show version`, `show ip route`, `show interfaces` |
| Ping | `ping\s+.*` | `ping 10.0.0.1`, `ping vrf MGMT 192.168.1.1` |
| Traceroute | `traceroute\s+.*` | `traceroute 8.8.8.8` |
| File listing | `dir\s+.*` | `dir flash:`, `dir bootflash:` |
| NX-OS show | `show\s+.*` | All `show` commands on NX-OS |
| IOS-XR admin-show | `admin\s+show\s+.*` | `admin show platform` |

### Recommended production allow-list

```dotenv
COMMAND_ALLOWLIST=show\s+.*,ping\s+[\w.:]+,traceroute\s+[\w.:]+,dir\s+.*,admin\s+show\s+.*
```

This restricts execution to read-only diagnostic commands. Any attempt to
execute `configure terminal`, `reload`, `write erase`, or similar destructive
commands is rejected with HTTP 403 before the SSH session is opened.

### Applying the allow-list to a specific role only

The allow-list is applied globally across all authenticated roles. If you need
per-role command restrictions, combine it with role-scoped key issuance: issue
one key per role and configure `COMMAND_ALLOWLIST` to the most restrictive
common set for external service accounts while giving admin keys a wider (or
empty) allowlist via a separate internal deployment.

---

## 6. Key Rotation Runbook

Follow this procedure to rotate an API key with **zero downtime**.

### Prerequisites

- Access to the environment file (`.env`) or the Kubernetes Secret that holds
  `API_KEYS` and `API_KEY_ROLES`.
- Access to the caller(s) that hold the old key (service configuration or
  Vault secret).

### Step 1 — Generate the new key

```bash
NEW_RAW=$(openssl rand -hex 32)
NEW_HASH=$(echo -n "$NEW_RAW" | sha256sum | awk '{print "sha256$"$1}')
echo "New raw key  : $NEW_RAW"
echo "New hash     : $NEW_HASH"
```

### Step 2 — Add the new key alongside the old key

Edit `.env` (or Kubernetes Secret) to include **both** old and new keys:

```dotenv
# Before rotation (old key only)
API_KEYS=sha256$<old-hash>
API_KEY_ROLES=sha256$<old-hash>:operator

# During rotation (both keys active)
API_KEYS=sha256$<old-hash>,sha256$<new-hash>
API_KEY_ROLES=sha256$<old-hash>:operator,sha256$<new-hash>:operator
```

### Step 3 — Reload the application

```bash
# Docker Compose
docker compose up -d --no-deps app

# Kubernetes
kubectl rollout restart deployment/nms-custom-api
kubectl rollout status deployment/nms-custom-api
```

### Step 4 — Update all callers to use the new key

Deploy/update every service or integration that holds the old key. Verify that
traffic is flowing correctly using the new key:

```bash
curl -sk -H "X-API-Key: $NEW_RAW" https://<nms-host>/api/health
# Expected: {"status":"ok"}
```

### Step 5 — Remove the old key

```dotenv
# After rotation (new key only)
API_KEYS=sha256$<new-hash>
API_KEY_ROLES=sha256$<new-hash>:operator
```

Reload the application again (Step 3). The old key is now invalid.

### Step 6 — Record the rotation

Update your secret management system (Vault, AWS Secrets Manager, etc.) with:
- The new key value
- The rotation date
- The next scheduled rotation date (recommend 90 days)

---

## 7. Recommended Production Defaults

```dotenv
# ---- API Auth ----
API_AUTH_ENABLED=true

# All keys prehashed — no plaintext keys in config
API_KEYS=sha256$<admin-hash>,sha256$<monitoring-hash>

# Explicit role mapping for every key
API_KEY_ROLES=sha256$<admin-hash>:admin,sha256$<monitoring-hash>:read-only

# ---- Command allow-list (read-only Cisco commands) ----
COMMAND_ALLOWLIST=show\s+.*,ping\s+[\w.:]+,traceroute\s+[\w.:]+,dir\s+.*,admin\s+show\s+.*

# ---- SSH hardening ----
SSH_DISABLE_HOST_KEY_CHECKING=false
SSH_KNOWN_HOSTS_PATH=/app/data/known_hosts

# ---- Rate limiting ----
RATE_LIMIT_ENABLED=true
RATE_LIMIT_BACKEND=redis
RATE_LIMIT_DEFAULT=120/60
RATE_LIMIT_SENSITIVE=20/60
RATE_LIMIT_ANONYMOUS=30/60

# ---- Session ----
MAX_PARALLEL_SESSIONS=5
IDLE_TIMEOUT_MINUTES=30
ROOT_WEB_LOGIN_ENABLED=false
```

### Additional recommendations

| Setting | Production value | Notes |
|---|---|---|
| `API_AUTH_ENABLED` | `true` | Never disable in production |
| `DEBUG` | `false` | Disables stack traces in API responses |
| `APP_ENV` | `production` | Enables production middleware (CORS, security headers) |
| `TLS_MIN_VERSION` | `TLSv1.3` | Disable TLS 1.2 and below |
| `HTTPS_REDIRECT_ENABLED` | `true` | Redirect all HTTP to HTTPS |
| Key entropy | ≥ 256 bits | Use `openssl rand -hex 32` |
| Key rotation cadence | 90 days | Immediate on suspected compromise |
| Key storage | Vault / KMS | Never in plaintext files |

---

## 8. Auditing & Monitoring

Every authenticated request is logged with:
- Timestamp
- Hashed key fingerprint (first 8 hex chars of the SHA-256 hash — never the
  full hash or the raw key)
- Authenticated role
- HTTP method and path
- Response status

Watch for:
- Sudden spike in `403 Forbidden` responses → possible key compromise / brute
  force
- Requests from unexpected source IPs → lateral movement
- Commands outside the allow-list → `COMMAND_ALLOWLIST` violations are logged
  at `WARNING` level

Recommended alert rule (Loki / Prometheus):

```logql
{app="nms-custom"} |= "COMMAND_ALLOWLIST violation" | rate()[5m] > 0
```

---

## 9. Kubernetes / Helm Deployment Notes

### Store keys in a Kubernetes Secret

```yaml
# secret-api-keys.yaml (apply manually or via Sealed Secrets / ESO)
apiVersion: v1
kind: Secret
metadata:
  name: nms-app-secrets
  namespace: nms
stringData:
  API_AUTH_ENABLED: "true"
  API_KEYS: "sha256$<admin-hash>,sha256$<monitor-hash>"
  API_KEY_ROLES: "sha256$<admin-hash>:admin,sha256$<monitor-hash>:read-only"
  COMMAND_ALLOWLIST: "show\\s+.*,ping\\s+[\\w.:]+,traceroute\\s+[\\w.:]+"
```

```bash
kubectl apply -f secret-api-keys.yaml
```

### Reference the Secret in Helm values

```yaml
# values-prod.yaml
secrets:
  existingSecret: nms-app-secrets
```

### External Secrets Operator integration

```yaml
externalSecrets:
  enabled: true
  refreshInterval: "1h"
  secretStoreRef:
    name: vault-backend
    kind: ClusterSecretStore
  credentialClasses:
    apiKeys:
      enabled: true
      remoteRef:
        key: nms/api-keys
```

### Key rotation in Kubernetes

1. Update the Secret value (via `kubectl edit`, Vault sync, or CI/CD pipeline).
2. Trigger a rolling restart:
   ```bash
   kubectl rollout restart deployment/nms-custom-api
   ```
3. Pods pick up the new Secret on startup; old pods continue handling traffic
   during the rolling update (dual-key window is not required in Kubernetes
   since rollout is gradual).
