# Production RBAC Review

Status: initial production review checklist added in Phase 5B.

## High-risk permissions

Require explicit assignment, audit trail, and periodic review:

- Command execution and command template changes.
- Credential profile create/update/delete and device credential assignment.
- User, role, virtual domain, and API key administration.
- Alarm suppress/unsuppress and group lifecycle controls.
- Service topology/service membership edits.
- Telemetry collector/subscription changes.
- Report schedule changes that export data externally.

## Recommended production defaults

- `API_AUTH_ENABLED=true` in all shared environments.
- Separate viewer/operator/admin roles; do not grant command execution to viewer/operator by default.
- Prefer named custom roles over shared admin use.
- Enable HTTPS with managed certs or terminate TLS at ingress.
- Store secrets in Kubernetes Secrets or an external secret manager, never ConfigMaps.
- Review audit logs for credential, command, lifecycle, and RBAC changes.

## Kubernetes RBAC posture

The Helm chart creates a dedicated service account and a minimal Role. The app currently does not require Kubernetes API privileges; any future privilege expansion must be justified by a concrete controller/integration and documented here.

## Open gaps before real multi-tenant production

- Add UI/API for API key lifecycle and rotation.
- Add role diff/export for approval workflows.
- Add scheduled stale-admin and privilege-escalation reports.
- Add optional external IdP/OIDC group mapping.
