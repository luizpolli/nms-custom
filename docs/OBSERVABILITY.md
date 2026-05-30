# Observability — Self-Monitoring Stack (P2.11)

NMS-Custom ships with an optional Prometheus + Alertmanager + Grafana stack
to scrape the backend's `/metrics` endpoint, evaluate alert rules, and
visualize the result.

These services run in the **`monitoring` Compose profile** so they do not
start with the default `docker compose up`. Bring them up explicitly:

```bash
docker compose --profile monitoring up -d
```

To stop just the monitoring stack:

```bash
docker compose --profile monitoring down
```

## Endpoints

| Service       | Default URL                | Notes                                              |
|---------------|----------------------------|----------------------------------------------------|
| Prometheus    | http://localhost:9090      | TSDB + alert rule evaluation                       |
| Alertmanager  | http://localhost:9093      | Alert routing / inhibition / silencing             |
| Grafana       | http://localhost:3000      | Dashboards (provisioned datasource + NMS folder)   |

Override the host ports via `.env` (`PROMETHEUS_PORT`, `ALERTMANAGER_PORT`,
`GRAFANA_PORT`).

## Grafana Login

Default credentials:

- User: `admin`
- Password: value of `GRAFANA_ADMIN_PASSWORD` (defaults to `admin` — change it
  in `.env` for any non-local deployment).

Anonymous access and sign-ups are disabled. The Prometheus datasource and the
**NMS Overview** dashboard are provisioned automatically from
`infra/grafana/provisioning/` and `infra/grafana/dashboards/`.

## Scraped Metrics

The backend exports these series (see
`backend/app/services/observability/metrics.py`):

- `nms_http_requests_total{method,endpoint,status}`
- `nms_http_request_duration_seconds_bucket` (Histogram)
- `nms_db_query_duration_seconds_bucket` (Histogram)
- `nms_kpi_rows`
- `nms_telemetry_raw_rows`
- `nms_telemetry_samples_total`
- `nms_telemetry_dropped_total`
- `nms_event_queue_depth{stream}`
- `nms_worker_stale{kind}`
- `nms_worker_runs_total{kind}`
- `nms_worker_errors_total{kind}`

Prometheus scrapes the backend over HTTPS at `app:8000/metrics` every 15s.
The dev config uses `insecure_skip_verify: true` because the backend ships a
self-signed cert; swap in a real CA bundle for production.

## Alert Rules

Defined in `infra/prometheus/rules/nms-alerts.yml`:

| Alert                  | Group       | Severity | Trigger                                                                  |
|------------------------|-------------|----------|--------------------------------------------------------------------------|
| `NmsApiHigh5xx`        | api_health  | critical | 5xx ratio > 5% over 5m                                                   |
| `NmsApiLatencyP95High` | api_health  | warning  | p95 HTTP latency > 2s for 10m                                            |
| `NmsWorkerStale`       | workers     | warning  | `nms_worker_stale == 1` for 5m (per `kind`)                              |
| `NmsWorkerErrorBurst`  | workers     | warning  | `rate(nms_worker_errors_total[5m]) > 0.1` for 10m                        |
| `NmsEventQueueBacklog` | queue       | warning  | `nms_event_queue_depth > 10000` for 10m                                  |
| `NmsTelemetryDropRate` | telemetry   | warning  | drop rate > 5% of sample rate for 10m                                    |
| `NmsDbQuerySlow`       | db          | warning  | p95 DB query duration > 1s for 10m                                       |

Critical alerts inhibit warnings of the same `alertname` via Alertmanager
inhibit rules.

### Adding a New Alert Rule

1. Edit `infra/prometheus/rules/nms-alerts.yml` and add a new entry under an
   existing group (or create a new group with `interval: 30s`).
2. Validate locally (requires Docker):
   ```bash
   docker run --rm -v "$PWD/infra/prometheus:/etc/prometheus:ro" \
     prom/prometheus:latest \
     promtool check rules /etc/prometheus/rules/nms-alerts.yml
   ```
3. Reload Prometheus:
   ```bash
   docker compose --profile monitoring kill -s HUP prometheus
   ```

## Dashboards

The provisioned **NMS Overview** dashboard
(`infra/grafana/dashboards/nms-overview.json`) covers HTTP rate / 5xx ratio /
p95 latency, DB p95 query time, event queue depth by stream, worker run vs
error rate, KPI rows, and telemetry accept vs drop rate.

### Adding a Panel

1. Edit the dashboard in the Grafana UI (it is provisioned with
   `allowUiUpdates: true`).
2. Export the JSON model (Dashboard settings → JSON Model) and overwrite
   `infra/grafana/dashboards/nms-overview.json`.
3. Validate it parses:
   ```bash
   python -m json.tool infra/grafana/dashboards/nms-overview.json > /dev/null
   ```
4. Commit the change. Grafana reloads provisioned dashboards every 30s.

### Adding a New Dashboard

Drop a new `*.json` file into `infra/grafana/dashboards/`. The provider in
`infra/grafana/provisioning/dashboards/dashboards.yml` picks it up
automatically.

## Configuring a Real Alertmanager Receiver

The shipped `infra/alertmanager/alertmanager.yml` only points at a placeholder
webhook (`http://webhook-sink/alerts`). Replace the `default` receiver with a
real integration. Examples:

### Slack

```yaml
receivers:
  - name: default
    slack_configs:
      - api_url: https://hooks.slack.com/services/T000/B000/XXXX
        channel: '#nms-alerts'
        send_resolved: true
        title: '{{ .CommonLabels.alertname }} ({{ .CommonLabels.severity }})'
        text: '{{ range .Alerts }}{{ .Annotations.summary }}\n{{ .Annotations.description }}\n{{ end }}'
```

### Email

```yaml
global:
  smtp_smarthost: smtp.example.com:587
  smtp_from: nms-alerts@example.com
  smtp_auth_username: nms-alerts@example.com
  smtp_auth_password: change-me

receivers:
  - name: default
    email_configs:
      - to: oncall@example.com
        send_resolved: true
```

### Generic Webhook (Microsoft Teams / custom service)

```yaml
receivers:
  - name: default
    webhook_configs:
      - url: https://example.com/alerts/incoming
        send_resolved: true
        http_config:
          authorization:
            type: Bearer
            credentials: <token>
```

After editing, reload Alertmanager:

```bash
docker compose --profile monitoring kill -s HUP alertmanager
```

## Hardening Notes

All three monitoring containers follow the repo-wide hardening pattern:

- Non-root UID/GID (`65534:65534` for Prometheus/Alertmanager, `472:472` for
  Grafana).
- `read_only: true` root filesystem.
- All Linux capabilities dropped, `no-new-privileges:true`.
- `tmpfs` mounts for ephemeral scratch directories.
- Persistent state in named volumes (`prom_data`, `alertmanager_data`,
  `grafana_data`).

Do not weaken any of these in shared deployments.
