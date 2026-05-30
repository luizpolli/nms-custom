# Secret Manager Integration Examples

This document shows how to inject NMS Custom secrets (database passwords, API
keys, credential encryption keys, etc.) from external secret stores rather than
storing them in plain-text `.env` files or Compose override files.

Consult [`SECURITY_REVIEW.md`](SECURITY_REVIEW.md) for the full P0/P1 checklist
and [`API_KEY_MANAGEMENT.md`](API_KEY_MANAGEMENT.md) for API key lifecycle
guidance.

---

## Contents

1. [Docker Compose — Docker Secrets](#1-docker-compose--docker-secrets)
2. [Kubernetes — ExternalSecret Operator (ESO)](#2-kubernetes--externalsecret-operator-eso)
   - [AWS Secrets Manager](#21-aws-secrets-manager)
   - [HashiCorp Vault](#22-hashicorp-vault)
   - [Azure Key Vault](#23-azure-key-vault)
3. [Environment Variable Injection Patterns](#3-environment-variable-injection-patterns)
   - [CI/CD (GitHub Actions)](#31-cicd-github-actions)
   - [systemd EnvironmentFile](#32-systemd-environmentfile)
   - [Shell one-liner for local testing](#33-shell-one-liner-for-local-testing)
4. [Checklist](#4-checklist)

---

## 1. Docker Compose — Docker Secrets

Docker Swarm (and standalone Compose 3.x) can mount secrets as read-only
files under `/run/secrets/<name>`.  The NMS Custom backend reads every setting
from environment variables, so the pattern is:

1. Store each secret as a Docker secret.
2. Mount the secret files into the container.
3. Use a custom entrypoint wrapper that reads the file and exports it as the
   corresponding env var before starting the app.

### 1a. Create secrets (Swarm / docker secret)

```bash
# Swarm-managed secrets (recommended for production)
printf 'super-strong-db-password-here' | docker secret create postgres_password -
printf 'super-strong-secret-key-here'  | docker secret create nms_secret_key -
printf 'hex-encoded-32-byte-key'        | docker secret create nms_cred_enc_key -
printf 'hex-encoded-16-byte-iv'         | docker secret create nms_cred_enc_iv -
printf 'api-key-one,api-key-two'        | docker secret create nms_api_keys -
```

### 1b. `docker-compose.secrets.yml` override

```yaml
# docker-compose.secrets.yml — overlay on top of docker-compose.yml
# Usage: docker stack deploy -c docker-compose.yml -c docker-compose.secrets.yml nms

version: "3.8"

secrets:
  postgres_password:
    external: true
  nms_secret_key:
    external: true
  nms_cred_enc_key:
    external: true
  nms_cred_enc_iv:
    external: true
  nms_api_keys:
    external: true

services:
  app:
    secrets:
      - postgres_password
      - nms_secret_key
      - nms_cred_enc_key
      - nms_cred_enc_iv
      - nms_api_keys
    environment:
      # Tell the entrypoint wrapper which file to read each var from.
      SECRET_KEY_FILE: /run/secrets/nms_secret_key
      POSTGRES_PASSWORD_FILE: /run/secrets/postgres_password
      CREDENTIAL_ENCRYPTION_KEY_FILE: /run/secrets/nms_cred_enc_key
      CREDENTIAL_ENCRYPTION_IV_FILE: /run/secrets/nms_cred_enc_iv
      API_KEYS_FILE: /run/secrets/nms_api_keys

  postgres:
    secrets:
      - postgres_password
    environment:
      POSTGRES_PASSWORD_FILE: /run/secrets/postgres_password
```

### 1c. Entrypoint wrapper (`scripts/docker-entrypoint.sh`)

```bash
#!/bin/sh
# Read *_FILE env vars and export the real values before exec-ing the app.
set -e

load_secret() {
  local var="$1"
  local file_var="${var}_FILE"
  local file_path="${!file_var:-}"
  if [ -n "$file_path" ] && [ -f "$file_path" ]; then
    export "$var=$(cat "$file_path")"
    echo "[entrypoint] Loaded $var from $file_path"
  fi
}

load_secret SECRET_KEY
load_secret POSTGRES_PASSWORD
load_secret CREDENTIAL_ENCRYPTION_KEY
load_secret CREDENTIAL_ENCRYPTION_IV
load_secret API_KEYS

exec "$@"
```

> **Tip:** Set `DATABASE_URL` from the individual `POSTGRES_*` env vars so you
> don't need to template a connection URL inside the secret file.

### 1d. Compose file secrets (non-Swarm, file-based)

For local staging without Swarm you can use file-backed secrets:

```yaml
secrets:
  nms_secret_key:
    file: ./secrets/nms_secret_key.txt   # git-ignored plain text file
```

This is suitable for a single-machine staging environment; **never commit the
`secrets/` directory**.

---

## 2. Kubernetes — ExternalSecret Operator (ESO)

The [External Secrets Operator](https://external-secrets.io) syncs secrets from
external stores (AWS, Vault, Azure…) into Kubernetes `Secret` objects. The Helm
chart references `ExternalSecret` templates in `helm/nms-custom/templates/`.

Install ESO once per cluster:

```bash
helm repo add external-secrets https://charts.external-secrets.io
helm install external-secrets external-secrets/external-secrets \
  -n external-secrets-system --create-namespace
```

### 2.1 AWS Secrets Manager

#### Create the secret in AWS

```bash
aws secretsmanager create-secret \
  --name nms-custom/production \
  --secret-string '{
    "SECRET_KEY": "super-strong-key-here",
    "POSTGRES_PASSWORD": "db-pass-here",
    "CREDENTIAL_ENCRYPTION_KEY": "hex-32-byte-key",
    "CREDENTIAL_ENCRYPTION_IV": "hex-16-byte-iv",
    "API_KEYS": "key-one,key-two"
  }'
```

#### `SecretStore` (IRSA / service-account-based auth)

```yaml
# helm/nms-custom/templates/secret-store-aws.yaml
apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: nms-aws-secrets
  namespace: nms
spec:
  provider:
    aws:
      service: SecretsManager
      region: us-east-1
      auth:
        jwt:
          serviceAccountRef:
            name: nms-backend   # must have IRSA annotation
```

#### `ExternalSecret`

```yaml
# helm/nms-custom/templates/external-secret-aws.yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: nms-app-secrets
  namespace: nms
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: nms-aws-secrets
    kind: SecretStore
  target:
    name: nms-app-secrets          # resulting k8s Secret name
    creationPolicy: Owner
  data:
    - secretKey: SECRET_KEY
      remoteRef:
        key: nms-custom/production
        property: SECRET_KEY
    - secretKey: POSTGRES_PASSWORD
      remoteRef:
        key: nms-custom/production
        property: POSTGRES_PASSWORD
    - secretKey: CREDENTIAL_ENCRYPTION_KEY
      remoteRef:
        key: nms-custom/production
        property: CREDENTIAL_ENCRYPTION_KEY
    - secretKey: CREDENTIAL_ENCRYPTION_IV
      remoteRef:
        key: nms-custom/production
        property: CREDENTIAL_ENCRYPTION_IV
    - secretKey: API_KEYS
      remoteRef:
        key: nms-custom/production
        property: API_KEYS
```

#### Reference in the Helm `values.yaml`

```yaml
# values.production.yaml
existingSecret: nms-app-secrets   # tells the chart to skip creating its own Secret
```

The chart's `deployment.yaml` already supports `envFrom.secretRef` when
`existingSecret` is set:

```yaml
envFrom:
  - secretRef:
      name: {{ .Values.existingSecret | default (include "nms-custom.fullname" .) }}
```

---

### 2.2 HashiCorp Vault

#### Mount the secret in Vault

```bash
vault kv put secret/nms-custom/production \
  SECRET_KEY="super-strong-key" \
  POSTGRES_PASSWORD="db-pass" \
  CREDENTIAL_ENCRYPTION_KEY="hex-32-byte-key" \
  CREDENTIAL_ENCRYPTION_IV="hex-16-byte-iv" \
  API_KEYS="key-one,key-two"
```

#### `SecretStore` (Kubernetes auth)

```yaml
apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: nms-vault-secrets
  namespace: nms
spec:
  provider:
    vault:
      server: "https://vault.example.com"
      path: "secret"
      version: "v2"
      auth:
        kubernetes:
          mountPath: "kubernetes"
          role: "nms-backend"
          serviceAccountRef:
            name: nms-backend
```

#### `ExternalSecret`

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: nms-app-secrets
  namespace: nms
spec:
  refreshInterval: 30m
  secretStoreRef:
    name: nms-vault-secrets
    kind: SecretStore
  target:
    name: nms-app-secrets
    creationPolicy: Owner
  dataFrom:
    - extract:
        key: secret/data/nms-custom/production   # ESO v1beta1 KV v2 path
```

`dataFrom.extract` pulls all key/value pairs from the Vault secret into the
Kubernetes `Secret`, so every env-var key (e.g. `SECRET_KEY`, `POSTGRES_PASSWORD`)
is available without listing each one individually.

---

### 2.3 Azure Key Vault

#### Store secrets in Azure

```bash
az keyvault secret set --vault-name nms-prod-kv --name SECRET-KEY      --value "super-strong-key"
az keyvault secret set --vault-name nms-prod-kv --name POSTGRES-PASSWORD --value "db-pass"
az keyvault secret set --vault-name nms-prod-kv --name CRED-ENC-KEY    --value "hex-32-byte-key"
az keyvault secret set --vault-name nms-prod-kv --name CRED-ENC-IV     --value "hex-16-byte-iv"
az keyvault secret set --vault-name nms-prod-kv --name API-KEYS        --value "key-one,key-two"
```

> Azure Key Vault secret names cannot contain underscores; use hyphens and map
> them to env-var names via `remoteRef.property`.

#### `SecretStore` (Workload Identity / AAD Pod Identity)

```yaml
apiVersion: external-secrets.io/v1beta1
kind: SecretStore
metadata:
  name: nms-azure-secrets
  namespace: nms
spec:
  provider:
    azurekv:
      tenantId: "00000000-0000-0000-0000-000000000000"
      vaultUrl: "https://nms-prod-kv.vault.azure.net"
      authType: WorkloadIdentity
      serviceAccountRef:
        name: nms-backend
```

#### `ExternalSecret`

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: nms-app-secrets
  namespace: nms
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: nms-azure-secrets
    kind: SecretStore
  target:
    name: nms-app-secrets
    creationPolicy: Owner
  data:
    - secretKey: SECRET_KEY
      remoteRef:
        key: SECRET-KEY
    - secretKey: POSTGRES_PASSWORD
      remoteRef:
        key: POSTGRES-PASSWORD
    - secretKey: CREDENTIAL_ENCRYPTION_KEY
      remoteRef:
        key: CRED-ENC-KEY
    - secretKey: CREDENTIAL_ENCRYPTION_IV
      remoteRef:
        key: CRED-ENC-IV
    - secretKey: API_KEYS
      remoteRef:
        key: API-KEYS
```

---

## 3. Environment Variable Injection Patterns

### 3.1 CI/CD (GitHub Actions)

Store secrets in **GitHub Actions Secrets** (Settings → Secrets and variables →
Actions) and inject them at deploy time.  Never write them to a file in the
repository.

```yaml
# .github/workflows/deploy.yml  (excerpt)
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to production
        env:
          SECRET_KEY: ${{ secrets.NMS_SECRET_KEY }}
          POSTGRES_PASSWORD: ${{ secrets.NMS_POSTGRES_PASSWORD }}
          CREDENTIAL_ENCRYPTION_KEY: ${{ secrets.NMS_CRED_ENC_KEY }}
          CREDENTIAL_ENCRYPTION_IV: ${{ secrets.NMS_CRED_ENC_IV }}
          API_KEYS: ${{ secrets.NMS_API_KEYS }}
        run: |
          # Write a temporary .env for the remote host — pipe over SSH, do not
          # write to disk locally.
          ssh deploy@prod-host "cat > /opt/nms/.env" <<EOF
          APP_ENV=production
          SECRET_KEY=${SECRET_KEY}
          POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
          CREDENTIAL_ENCRYPTION_KEY=${CREDENTIAL_ENCRYPTION_KEY}
          CREDENTIAL_ENCRYPTION_IV=${CREDENTIAL_ENCRYPTION_IV}
          API_KEYS=${API_KEYS}
          EOF
          ssh deploy@prod-host "cd /opt/nms && docker compose up -d --pull always"
```

> **Do not** echo or log secret values. GitHub Actions masks them in logs, but
> defensive coding avoids accidental exposure.

### 3.2 systemd EnvironmentFile

For bare-metal / VM deployments managed by systemd, store secrets in a
permission-restricted file that systemd reads before starting the process.

```ini
# /etc/nms/nms.env  (mode 0600, owned by nms user)
APP_ENV=production
SECRET_KEY=super-strong-key-here
POSTGRES_PASSWORD=db-pass-here
CREDENTIAL_ENCRYPTION_KEY=hex-32-byte-key
CREDENTIAL_ENCRYPTION_IV=hex-16-byte-iv
API_KEYS=key-one,key-two
```

```ini
# /etc/systemd/system/nms-backend.service  (excerpt)
[Service]
User=nms
EnvironmentFile=/etc/nms/nms.env
ExecStart=/opt/nms/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

```bash
# Create and lock down the env file
sudo install -m 0600 -o nms -g nms /dev/null /etc/nms/nms.env
sudo editor /etc/nms/nms.env          # fill in values
sudo systemctl daemon-reload
sudo systemctl restart nms-backend
```

### 3.3 Shell one-liner for local testing

When you need to run the backend locally **without** a `.env` file, export
secrets from your password manager or credential store on-the-fly:

```bash
# Example using 1Password CLI (op)
export SECRET_KEY=$(op read "op://Private/NMS Dev/secret_key")
export POSTGRES_PASSWORD=$(op read "op://Private/NMS Dev/postgres_password")
export API_KEYS=$(op read "op://Private/NMS Dev/api_keys")
export APP_ENV=development

cd backend && .venv/bin/uvicorn app.main:app --reload
```

Or using `pass` (the standard Unix password manager):

```bash
export SECRET_KEY=$(pass show nms/dev/secret_key)
export POSTGRES_PASSWORD=$(pass show nms/dev/postgres_password)
```

---

## 4. Checklist

Before going to production, verify all of the following:

- [ ] No plaintext secrets in `docker-compose.yml`, Helm `values.yaml`, or
      committed `.env` files.
- [ ] `APP_ENV=production` — the fail-fast `ProductionSafetyError` guard runs
      and rejects any unsafe placeholder values at boot time.
- [ ] `SECRET_KEY`, `CREDENTIAL_ENCRYPTION_KEY`, `CREDENTIAL_ENCRYPTION_IV`,
      and `POSTGRES_PASSWORD` are sourced from a secret manager or secure
      `EnvironmentFile` (mode 0600).
- [ ] `API_KEYS` contains at least one high-entropy key (≥ 32 chars); prefer
      the `sha256$<hex>` form so plaintext keys are not held in env vars at
      all.  See [`API_KEY_MANAGEMENT.md`](API_KEY_MANAGEMENT.md).
- [ ] Secret rotation runbook is documented for each store.
- [ ] ESO `refreshInterval` is set (recommend 30m–1h) so rotated secrets
      propagate without a full redeployment.
- [ ] Access to the secret store is scoped to the service account / IAM role
      that needs it (least privilege).
- [ ] Secret store audit logs are enabled (CloudTrail, Vault audit device,
      Azure Monitor).

---

*See also: [`SECURITY_REVIEW.md`](SECURITY_REVIEW.md) · [`API_KEY_MANAGEMENT.md`](API_KEY_MANAGEMENT.md) · [`OS_HARDENING_GUIDE.md`](OS_HARDENING_GUIDE.md)*
