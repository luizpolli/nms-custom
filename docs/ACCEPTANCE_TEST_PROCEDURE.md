# NMS Custom — Acceptance Test Procedure (ATP)

Version: 1.1.0  
Date: 2026-05-23  
Author: Engineering Team

## Purpose

This document defines the functional acceptance test procedure for NMS Custom.
Each test case validates a specific user-facing feature. The ATP should be
executed against a running instance (Docker Compose or Kubernetes) before any
production release.

## Prerequisites

- NMS Custom stack running (API + frontend + workers + Redis + TimescaleDB)
- At least one test device reachable via SNMP (or use the built-in mock device simulator)
- `nms-traffic-sim` available for ingestion tests
- A browser (Chrome/Firefox/Edge) pointing at the frontend URL
- API credentials configured if `API_AUTH_ENABLED=true`

## Severity Legend

- **P0** — Must pass for production readiness
- **P1** — Should pass; acceptable with known workaround
- **P2** — Nice-to-have; cosmetic or advanced feature

---

## 1. Authentication & Authorization (P0)

| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 1.1 | API key authentication | Set `API_AUTH_ENABLED=true`, make request without key | 401 Unauthorized |
| 1.2 | Valid API key access | Set `X-API-Key` header with valid key | 200 OK |
| 1.3 | Hashed API key | Configure `sha256$<hex>` key in `API_KEYS`, authenticate | Works transparently |
| 1.4 | Role-based access | Use viewer-role key, attempt `POST /commands` | 403 Forbidden |
| 1.5 | Root web login | Enable `ROOT_WEB_LOGIN_ENABLED`, attempt browser login | Login form appears, auth succeeds |
| 1.6 | Session idle timeout | Wait past `IDLE_TIMEOUT_MINUTES`, make request | Session expired / re-auth required |
| 1.7 | ALLOWED_HOSTS enforcement | Send request with unknown `Host` header | 400 Bad Request |

## 2. Device Management (P0)

| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 2.1 | List devices | Navigate to Devices page | Table shows registered devices with name, IP, vendor, status |
| 2.2 | Create device | Click "Add Device", fill form, submit | Device appears in list |
| 2.3 | Edit device | Click Edit on a device, modify fields, save | Changes reflected |
| 2.4 | Delete device | Click Delete, confirm dialog | Device removed from list |
| 2.5 | Search/filter devices | Type in search box, select vendor/status filter | Table filters correctly |
| 2.6 | Pagination | Add 25+ devices, navigate pages | Pagination controls work |
| 2.7 | CSV import (simple) | Use template CSV, upload via Import modal | Devices created, count shown |
| 2.8 | CSV import (EPNM format) | Upload EPNM-format CSV with SNMP/CLI fields | Devices + credentials created |
| 2.9 | CSV import validation | Upload CSV with missing required fields | Error shown per row, valid rows still import |
| 2.10 | CSV export (standard) | Click Export CSV | Downloads CSV with EPNM columns (no credentials) |
| 2.11 | CSV export (with creds) | Root user exports with credentials checkbox | CSV includes username/password columns |
| 2.12 | CSV export (non-root) | Non-root user attempts credential export | Denied or credentials columns empty |
| 2.13 | Verify credentials | Open Add Device form, fill SNMP fields, click Verify | Shows sysDescr on success, error on failure |
| 2.14 | Poll device | Click Poll button on a device | KPIs written, status updated |
| 2.15 | View interfaces | Open device detail, check Interfaces tab | Live IF-MIB interface rows displayed |
| 2.16 | Discover neighbors | Click "Discover Neighbors" | LLDP/CDP neighbors listed |
| 2.17 | Device detail page | Click Eye icon on device row | Detail page with all fields, tabs for interfaces/KPIs/alarms |
| 2.18 | Device tags | Add tags during create/edit | Tags displayed, filter by tag works |

## 3. Credential Management (P0)

| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 3.1 | List credentials | Navigate to Credentials page | Table with credential profiles |
| 3.2 | Create credential | Fill form: name, hostname, username, SNMP version, community | Credential saved |
| 3.3 | SNMPv3 credential | Create with v3 auth/priv params | All v3 fields stored |
| 3.4 | Assign to device | Edit device, select credential profile | Device credential_id updated |
| 3.5 | Encrypted storage | Inspect DB directly | `auth_key` is encrypted blob, not plaintext |

## 4. Commands (P0)

| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 4.1 | Create command | Click "Create command", select device, enter name + CLI, save | Command saved, appears in list |
| 4.2 | Edit command | Click Edit, modify CLI, save | Changes reflected |
| 4.3 | Delete command | Click Delete, confirm | Command removed |
| 4.4 | Run saved command | Click Run on a command | Output displayed in modal |
| 4.5 | Run ad-hoc command | Enter device + CLI in ad-hoc section, run | Output displayed |
| 4.6 | Command allowlist | Try a blocked command (e.g. `reload`) | Rejected with allowlist error |
| 4.7 | Bulk run | Select multiple devices, run a command | Results per device shown |
| 4.8 | Run history | Click History tab, view past runs | Timestamped entries with stdout/stderr |
| 4.9 | Export runs | Export command runs as TXT/JSON/CSV | File downloaded with correct format |
| 4.10 | Command schedules | Create a scheduled command execution | Schedule saved, runs at specified time |

## 5. Alarms & Events (P0)

| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 5.1 | View alarms | Navigate to Alarms page | Table with severity badges, states, timestamps |
| 5.2 | Summary strip | Check top summary bar | Counts: critical/major/minor/warning by state |
| 5.3 | Filter by severity | Select "Critical" in severity dropdown | Only critical alarms shown |
| 5.4 | Filter by state | Select "Active" | Only active alarms |
| 5.5 | Text search | Type hostname or keyword in search | Matching alarms displayed |
| 5.6 | Date range filter | Set From/To dates | Alarms within range shown |
| 5.7 | Category filter | Filter by category (syslog, trap, etc.) | Filtered correctly |
| 5.8 | Source host filter | Filter by specific source host | Filtered correctly |
| 5.9 | Save filter preset | Click "Save Filter", name it, set public/private | Filter saved |
| 5.10 | Load saved filter | Select saved filter from dropdown | All filter fields populated |
| 5.11 | Delete saved filter | Click delete on owned filter | Filter removed |
| 5.12 | Acknowledge alarm | Click Ack, enter user, confirm | State changes to "acknowledged" |
| 5.13 | Clear alarm | Click Clear | State changes to "cleared", `cleared_at` set |
| 5.14 | Suppress alarm | Click Suppress, enter reason | State changes to "suppressed" |
| 5.15 | Unsuppress alarm | Click Unsuppress on suppressed alarm | State returns to "active" |
| 5.16 | Alarm detail drawer | Click on alarm row | Side panel with full details + varbinds |
| 5.17 | WebSocket live update | Generate alarm via traffic-sim while page open | New alarm flashes in table |
| 5.18 | Alarm ingest API | POST to `/alarms/ingest` with syslog/event payload | Alarm created and correlated |

## 6. MIB Management (P1)

| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 6.1 | List MIBs | Navigate to MIBs page | Table of registered MIBs |
| 6.2 | Create MIB (manual) | Click New MIB, fill name + OID root, save | MIB record created |
| 6.3 | Upload MIB file | Click Upload, select .mib file, upload | File stored, parsed summary shown |
| 6.4 | MIB summary | Click on uploaded MIB, view summary | Module name, notifications listed |
| 6.5 | Edit MIB | Modify name/description, save | Changes reflected |
| 6.6 | Delete MIB | Delete a MIB entry | Removed from list |
| 6.7 | Upload size limit | Upload file > `MIB_UPLOAD_MAX_BYTES` | 413 error shown |
| 6.8 | Extension validation | Upload file with `.exe` extension | 400 error: unsupported extension |

## 7. Topology (P1)

| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 7.1 | View topology graph | Navigate to Topology page | Graph rendered with device nodes + links |
| 7.2 | Rebuild topology | Click Rebuild | Graph refreshes from LLDP/CDP data |
| 7.3 | Node click | Click a device node | Device detail shown or navigates to detail page |
| 7.4 | Alarm overlay | Alarm on a device | Node shows severity color indicator |

## 8. Performance & Telemetry (P1) — Performance PENDING FOR TEST

Performance validation requires at least one reachable device with valid SNMP credentials and collected KPI samples. The page and API are present, but KPI charts/summaries should not be marked accepted until tested against real polling data.

| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 8.1 | View performance page | Navigate to Performance | Device picker + KPI charts |
| 8.2 | Select device | Pick a device from dropdown | KPI time series charts render |
| 8.3 | Time range | Change time range (1h/6h/24h/7d) | Charts update accordingly |
| 8.4 | Telemetry page | Navigate to Telemetry | Telemetry samples table/chart |
| 8.5 | Telemetry ingest | POST telemetry sample via API or receiver | Data appears in charts |

## 9. Services & Assurance (P1)

| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 9.1 | View services | Navigate to Services page | List of configured services |
| 9.2 | Create service | Add service with dependencies | Service created with score |
| 9.3 | Service score | Trigger alarm on dependent device | Service score degrades |
| 9.4 | Assurance page | Navigate to Assurance | Network score sparkline, service health |
| 9.5 | Service trend report | Generate service trend XLSX export | XLSX downloads with historical scores |

## 10. Reports (P1)

| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 10.1 | View reports page | Navigate to Reports | Available report types listed |
| 10.2 | Generate report | Select report type, set params, generate | Report generated |
| 10.3 | Download report | Click download on generated report | File downloads (XLSX/CSV) |
| 10.4 | Assurance trend report | Generate assurance_trend report | XLSX with snapshot history |
| 10.5 | Service trend report | Generate service_trend report | XLSX with service score history |

## 11. Settings Administration (P0)

| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 11.1 | Settings navigation | Open Settings, click each submenu | All sections accessible |
| 11.2 | Deep link | Navigate to `/settings?section=security` | Correct section opens |
| 11.3 | Search | Type in settings search bar | Matching submenus highlighted |
| 11.4 | Mail notification settings | Open Settings -> Notifications & Forwarding, edit SMTP host/port/from, save | Settings persisted |
| 11.5 | System job settings | Edit concurrency/retries, save | Settings persisted |
| 11.6 | System retention | Edit alarm/event/KPI retention days, save | Settings persisted |
| 11.7 | Network SNMP defaults | Edit community/version/timeout, save | Settings persisted |
| 11.8 | Alarm defaults | Edit severity/notification defaults, save | Settings persisted |
| 11.9 | User management | Create/edit/delete users | CRUD operations work |
| 11.10 | Role management | Create custom role, assign permissions | Role created with correct permissions |
| 11.11 | Permission visibility | User with viewer role navigates Settings | Restricted submenus hidden/locked |
| 11.12 | Profile export | Click Export Settings Profile | JSON file downloaded |
| 11.13 | Profile import | Upload exported JSON profile | Settings restored |
| 11.14 | Audit trail | View Settings audit log | Recent changes listed with timestamps |
| 11.15 | Mail notification test | Click Test Mail Notification under Notifications & Forwarding | SMTP settings validated and result shown |
| 11.16 | Event forwarding | Add forwarding target (IP + port) | Target saved |
| 11.17 | Forwarding enable/disable | Toggle forwarding target on/off | State persisted |

## 12. Event Forwarding (P0)

| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 12.1 | Create syslog UDP target | Add target: protocol=syslog_udp, host=10.0.0.1, port=514 | Target created |
| 12.2 | Create SNMP trap target | Add target: protocol=snmp_trap, host=10.0.0.2, port=162 | Target created |
| 12.3 | Create webhook target | Add target: protocol=http_webhook, host=http://hooks.example.com, port=443 | Target created |
| 12.4 | Event type filter | Set target to forward only traps | Only trap events forwarded |
| 12.5 | Severity filter | Set minimum severity to "major" | Only major+ events forwarded |
| 12.6 | Test connectivity | Click Test button | Test event sent, success/failure feedback |
| 12.7 | Enable/disable | Toggle target off | Events no longer forwarded to that target |
| 12.8 | Edit target | Modify host/port, save | Changes persisted |
| 12.9 | Delete target | Delete a forwarding target | Removed from list |
| 12.10 | Account audit forwarding | Add target with Account Audit event type, change a non-admin user's roles | External collector receives account_audit event |

## 13. Lab Health & Monitoring (P1)

| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 13.1 | Lab Health page | Navigate to Lab Health | EPS cards, distribution histograms |
| 13.2 | EPS monitoring | Generate traffic with nms-traffic-sim | EPS counters update in real-time |
| 13.3 | Worker health | Check `/api/system/health` | Workers reporting heartbeats |
| 13.4 | Prometheus metrics | GET `/metrics` | Prometheus-format counters |
| 13.5 | Export snapshot | Click Export JSON | Timestamped snapshot with scenario labels |

## 14. AI Operations (P2)

| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 14.1 | AI Ops page (disabled) | Navigate with LLM disabled | "AI Ops disabled" message |
| 14.2 | AI Ops advisory (enabled) | Enable LLM provider, ask for advisory | Response with citations |
| 14.3 | Redaction guard | Submit query with credential-like content | Sensitive data redacted |
| 14.4 | RBAC gating | Non-admin user attempts AI Ops | Access denied |

## 15. Discovery (P1)

| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 15.1 | SNMP scan | Enter IP range, community, start scan | Discovered devices listed |
| 15.2 | Add from scan | Select discovered device, add to inventory | Device created from scan result |
| 15.3 | Scan results table | View scan results | IP, sysDescr, reachability shown |

## 16. Monitoring Policies (P2)

| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 16.1 | List policies | Navigate to Monitoring Policies | Configured policies shown |
| 16.2 | Create policy | Add policy with polling interval, target device(s) | Policy created |
| 16.3 | Policy execution | Wait for policy interval | KPIs collected per policy |

## 17. IOS Version Management (P2)

| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 17.1 | View IOS versions | Navigate to IOS page | Software version records |
| 17.2 | Add IOS version | Upload/register a software version | Record created |

## 18. Infrastructure (P0)

| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 18.1 | Docker Compose up | `docker compose up -d` | All services healthy |
| 18.2 | Frontend loads | Open browser to frontend URL | Dashboard renders |
| 18.3 | API health | GET `/api/system/health` | Status: ok with worker heartbeats |
| 18.4 | Helm template | `helm template nms-custom ./helm/nms-custom` | Templates render without errors |
| 18.5 | Helm lint | `helm lint ./helm/nms-custom` | No errors |
| 18.6 | Backend tests | `pytest backend/tests -q` | All tests pass |
| 18.7 | Frontend build | `npm run build` in frontend/ | Build succeeds |
| 18.8 | DB migrations | `alembic upgrade head` | All migrations apply cleanly |

## 19. Cross-Cutting Concerns (P0)

| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 19.1 | Dark mode | Toggle dark mode | All pages render correctly |
| 19.2 | Audit trail | Perform various actions | Audit entries logged with actor/action/timestamp |
| 19.3 | Error handling | Trigger API error (e.g. invalid UUID) | Toast notification with error message |
| 19.4 | WebSocket reconnect | Disconnect and wait | Client reconnects automatically |
| 19.5 | CORS | Access from allowed origin | Requests succeed |
| 19.6 | CORS (blocked) | Access from unlisted origin | Requests blocked |
| 19.7 | TLS enforcement | Access with `HTTPS_ENABLED=true` | HTTPS redirect/enforcement active |
| 19.8 | Concurrent sessions | Open multiple tabs | Both sessions work independently |
| 19.9 | API pagination | Request with offset/limit params | Correct subset returned |

---

## Sign-Off

| Role | Name | Date | Signature |
|------|------|------|-----------|
| QA Lead | | | |
| Dev Lead | | | |
| Product Owner | | | |

## Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2026-05-23 | Engineering | Initial ATP |
| 1.1.0 | 2026-05-23 | Engineering | Added v1.1 features: forwarding, alarm filters, EPNM export/import |
