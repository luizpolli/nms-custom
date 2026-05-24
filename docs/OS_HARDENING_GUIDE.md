# NMS Custom — Server & OS Hardening Guide

Version: 1.0.0  
Date: 2026-05-23

## Purpose

This document provides a security hardening checklist for the server(s) hosting
NMS Custom. It covers OS-level, network-level, and application-level controls.
Follow this guide before exposing the system to production traffic.

---

## 1. Operating System Hardening (RHEL / Rocky / AlmaLinux)

### 1.1 Installation & Patching

| # | Control | Command / Action | Priority |
|---|---------|------------------|----------|
| 1 | Minimal install | Use "Minimal" or "Server" profile — no desktop, no dev tools | P0 |
| 2 | Patch management | `dnf update -y && dnf install -y dnf-automatic` | P0 |
| 3 | Auto-updates (security) | `systemctl enable --now dnf-automatic-install.timer` | P0 |
| 4 | Remove unused packages | `dnf remove -y $(rpm -qa \| grep -E 'telnet\|ftp\|rsh')` | P0 |
| 5 | EPEL / third-party repos | Disable or pin to security-only channels | P1 |

### 1.2 User & Access Control

| # | Control | Command / Action | Priority |
|---|---------|------------------|----------|
| 6 | Disable root SSH | `/etc/ssh/sshd_config`: `PermitRootLogin no` | P0 |
| 7 | SSH key-only auth | `PasswordAuthentication no`, `PubkeyAuthentication yes` | P0 |
| 8 | SSH protocol 2 only | `Protocol 2` (default on modern RHEL) | P0 |
| 9 | SSH idle timeout | `ClientAliveInterval 300`, `ClientAliveCountMax 2` | P1 |
| 10 | Limit SSH access | `AllowUsers nms-admin` or `AllowGroups wheel` | P0 |
| 11 | Fail2ban / SSHGuard | `dnf install -y fail2ban && systemctl enable --now fail2ban` | P0 |
| 12 | Strong passwords | `authselect select minimal with-faillock` | P1 |
| 13 | Sudo audit | `visudo`: limit sudoers, enable logging | P0 |
| 14 | Remove unnecessary users | Lock/remove default system users not needed | P1 |
| 15 | Disable SU for non-wheel | `/etc/pam.d/su`: `auth required pam_wheel.so use_uid` | P1 |

### 1.3 Filesystem & Kernel

| # | Control | Command / Action | Priority |
|---|---------|------------------|----------|
| 16 | Separate partitions | `/var`, `/var/log`, `/tmp`, `/home` on separate mounts | P1 |
| 17 | `noexec` on /tmp | `/etc/fstab`: `tmpfs /tmp tmpfs defaults,noexec,nosuid,nodev 0 0` | P0 |
| 18 | Restrict `/proc` | `hidepid=2` mount option on `/proc` | P2 |
| 19 | Kernel sysctl hardening | See section 1.3.1 below | P0 |
| 20 | Disable USB storage | `echo 'blacklist usb-storage' > /etc/modprobe.d/usb-storage.conf` | P2 |
| 21 | File integrity (AIDE) | `dnf install aide && aide --init && mv /var/lib/aide/aide.db.new.gz /var/lib/aide/aide.db.gz` | P1 |
| 22 | Audit daemon | `systemctl enable --now auditd` | P0 |

#### 1.3.1 Kernel sysctl Hardening

Add to `/etc/sysctl.d/99-nms-hardening.conf`:

```ini
# Disable IP forwarding (unless this box is a router)
net.ipv4.ip_forward = 0
net.ipv6.conf.all.forwarding = 0

# Ignore ICMP redirects
net.ipv4.conf.all.accept_redirects = 0
net.ipv4.conf.default.accept_redirects = 0
net.ipv6.conf.all.accept_redirects = 0

# Don't send ICMP redirects
net.ipv4.conf.all.send_redirects = 0
net.ipv4.conf.default.send_redirects = 0

# Enable SYN flood protection
net.ipv4.tcp_syncookies = 1

# Log martian packets
net.ipv4.conf.all.log_martians = 1
net.ipv4.conf.default.log_martians = 1

# Ignore broadcast ICMP
net.ipv4.icmp_echo_ignore_broadcasts = 1

# Disable source routing
net.ipv4.conf.all.accept_source_route = 0
net.ipv4.conf.default.accept_source_route = 0
net.ipv6.conf.all.accept_source_route = 0

# Enable RFC1337 TCP TIME-WAIT protection
net.ipv4.tcp_rfc1337 = 1

# Disable core dumps
fs.suid_dumpable = 0

# Randomize virtual address space
kernel.randomize_va_space = 2

# Restrict dmesg to root
kernel.dmesg_restrict = 1

# Restrict kernel pointer exposure
kernel.kptr_restrict = 2
```

Apply: `sysctl --system`

---

## 2. Firewall Configuration

### 2.1 firewalld (RHEL default)

```bash
# Enable firewall
systemctl enable --now firewalld

# Default deny
firewall-cmd --set-default-zone=drop

# Allow SSH (restrict to management VLAN if possible)
firewall-cmd --permanent --zone=drop --add-rich-rule='rule family="ipv4" source address="10.0.0.0/8" service name="ssh" accept'

# NMS Frontend (HTTPS only)
firewall-cmd --permanent --zone=drop --add-port=443/tcp

# NMS API (if separate port)
firewall-cmd --permanent --zone=drop --add-port=8000/tcp

# SNMP trap receiver (from network devices only)
firewall-cmd --permanent --zone=drop --add-rich-rule='rule family="ipv4" source address="10.0.0.0/8" port port="1162" protocol="udp" accept'

# Syslog receiver
firewall-cmd --permanent --zone=drop --add-rich-rule='rule family="ipv4" source address="10.0.0.0/8" port port="5514" protocol="udp" accept'

# Telemetry gRPC receiver
firewall-cmd --permanent --zone=drop --add-rich-rule='rule family="ipv4" source address="10.0.0.0/8" port port="57400" protocol="tcp" accept'

# Reload
firewall-cmd --reload
firewall-cmd --list-all
```

### 2.2 Ports Summary

| Port | Protocol | Service | Direction | Notes |
|------|----------|---------|-----------|-------|
| 22 | TCP | SSH | Inbound | Management VLAN only |
| 443 | TCP | HTTPS (frontend + API) | Inbound | Via reverse proxy |
| 8000 | TCP | API (direct) | Inbound | Block if behind proxy |
| 1162 | UDP | SNMP traps | Inbound | From network devices |
| 5514 | UDP | Syslog | Inbound | From network devices |
| 57400 | TCP | gNMI telemetry | Inbound | From network devices |
| 5432 | TCP | PostgreSQL | Internal | Bind to 127.0.0.1 or pod network |
| 6379 | TCP | Redis | Internal | Bind to 127.0.0.1 or pod network |

---

## 3. Network Security

### 3.1 TLS Configuration

| # | Control | Details | Priority |
|---|---------|---------|----------|
| 1 | TLS 1.2+ only | Disable SSLv3, TLS 1.0, TLS 1.1 | P0 |
| 2 | Strong cipher suites | `ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM` | P0 |
| 3 | HSTS header | `Strict-Transport-Security: max-age=31536000; includeSubDomains` | P0 |
| 4 | cert-manager (K8s) | Enable `certManager.enabled=true` in Helm values | P0 |
| 5 | Certificate rotation | Automate via cert-manager or cron + certbot | P0 |

### 3.2 Reverse Proxy (nginx/Caddy)

Always front the NMS with a reverse proxy:

```nginx
server {
    listen 443 ssl http2;
    server_name nms.example.com;

    ssl_certificate /etc/pki/tls/certs/nms.pem;
    ssl_certificate_key /etc/pki/tls/private/nms.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers on;

    # Security headers
    add_header X-Frame-Options DENY always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy strict-origin-when-cross-origin always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=30r/s;

    location /api/ {
        limit_req zone=api burst=50 nodelay;
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location / {
        proxy_pass http://127.0.0.1:5173;
        proxy_set_header Host $host;
    }

    # WebSocket upgrade for alarms
    location /api/alarms/ws {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### 3.3 Network Segmentation

| Zone | Contains | Access From | Access To |
|------|----------|-------------|-----------|
| Management | SSH, admin UI | Admin VLAN only | All internal |
| Application | API, frontend, workers | Users, load balancer | DB, Redis |
| Data | PostgreSQL, Redis | Application zone only | None outbound |
| Collection | Trap/syslog/telemetry receivers | Network devices | Application zone |

---

## 4. Database Hardening (PostgreSQL/TimescaleDB)

| # | Control | Details | Priority |
|---|---------|---------|----------|
| 1 | Bind address | `listen_addresses = '127.0.0.1'` or pod IP only | P0 |
| 2 | pg_hba.conf | `hostssl` entries, reject `trust` and `md5`, prefer `scram-sha-256` | P0 |
| 3 | Strong password | Use 32+ character random password for `nms` user | P0 |
| 4 | Minimal privileges | `nms` user: `GRANT ALL ON DATABASE nms TO nms` only, no SUPERUSER | P0 |
| 5 | SSL required | `ssl = on` in `postgresql.conf` | P1 |
| 6 | Connection limit | `max_connections = 100` (tune per environment) | P1 |
| 7 | Backup encryption | Encrypt pg_dump output: `pg_dump nms \| gpg -e -r admin@example.com > backup.sql.gpg` | P1 |
| 8 | Audit logging | `log_statement = 'ddl'`, `log_connections = on`, `log_disconnections = on` | P1 |
| 9 | TimescaleDB retention | Ensure retention policies match `SystemRetentionSettings` | P1 |

---

## 5. Redis Hardening

| # | Control | Details | Priority |
|---|---------|---------|----------|
| 1 | Bind address | `bind 127.0.0.1` or pod IP only | P0 |
| 2 | Password | `requirepass <strong-random-password>` | P0 |
| 3 | Disable commands | `rename-command FLUSHALL ""`, `rename-command CONFIG ""` | P1 |
| 4 | No external exposure | Never expose port 6379 to non-application networks | P0 |
| 5 | TLS | Enable Redis TLS in production if traffic crosses network boundaries | P2 |
| 6 | Maxmemory policy | `maxmemory-policy allkeys-lru` with appropriate limit | P1 |

---

## 6. Container/Docker Hardening

### 6.1 Docker Daemon

| # | Control | Details | Priority |
|---|---------|---------|----------|
| 1 | Non-root containers | All NMS containers run as non-root user | P0 |
| 2 | Read-only rootfs | `read_only: true` in compose where possible | P1 |
| 3 | Drop capabilities | `cap_drop: [ALL]`, add only needed (`NET_BIND_SERVICE` for receivers) | P0 |
| 4 | No privileged | `privileged: false` always | P0 |
| 5 | Resource limits | Set `mem_limit` and `cpus` per service | P1 |
| 6 | Docker socket | Never mount `/var/run/docker.sock` in app containers | P0 |
| 7 | Image scanning | `trivy image nms-custom-backend:latest` before deploy | P1 |
| 8 | Signed images | Enable Docker Content Trust: `export DOCKER_CONTENT_TRUST=1` | P2 |

### 6.2 Docker Compose Security

```yaml
services:
  app:
    user: "1000:1000"
    read_only: true
    tmpfs:
      - /tmp
    cap_drop:
      - ALL
    security_opt:
      - no-new-privileges:true
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '1.0'
```

---

## 7. Kubernetes Hardening (Helm/K8s)

| # | Control | Details | Priority |
|---|---------|---------|----------|
| 1 | NetworkPolicy | Enable `networkPolicy.enabled=true` in Helm values | P0 |
| 2 | PodSecurityStandards | Apply `restricted` PSS to namespace | P0 |
| 3 | RBAC | Minimal ServiceAccount permissions | P0 |
| 4 | Secrets management | Use ExternalSecrets Operator, not plain K8s Secrets in git | P0 |
| 5 | Image pull policy | `Always` in production | P1 |
| 6 | Pod disruption budgets | `pdb.enabled=true`, `minAvailable: 1` | P1 |
| 7 | Node anti-affinity | `ha.podAntiAffinityMode: hard` for HA | P1 |
| 8 | Ingress TLS | cert-manager with Let's Encrypt or internal CA | P0 |
| 9 | Audit logging | Enable K8s audit policy for NMS namespace | P1 |
| 10 | Resource quotas | Set namespace ResourceQuota | P1 |

---

## 8. Application-Level Security

| # | Control | Details | Priority |
|---|---------|---------|----------|
| 1 | API authentication | `API_AUTH_ENABLED=true` in production | P0 |
| 2 | Hashed API keys | Use `sha256$<hex>` format for `API_KEYS` | P0 |
| 3 | Secret key | Set strong random `SECRET_KEY` (≥64 chars) | P0 |
| 4 | Credential encryption | Set `CREDENTIAL_ENCRYPTION_KEY` and `_IV` from HSM/vault | P0 |
| 5 | Command allowlist | Configure `COMMAND_ALLOWLIST` to restrict CLI commands | P0 |
| 6 | CORS origins | Set `CORS_ORIGINS` to exact frontend URL(s) | P0 |
| 7 | HTTPS enforcement | `HTTPS_ENABLED=true` | P0 |
| 8 | ALLOWED_HOSTS | Set to exact domain(s): `nms.example.com,localhost` | P0 |
| 9 | Debug mode | `DEBUG=false`, `APP_ENV=production` | P0 |
| 10 | Audit trail | Verify AuditLog captures all sensitive operations | P0 |
| 11 | Session limits | `MAX_PARALLEL_SESSIONS=5`, `IDLE_TIMEOUT_MINUTES=30` | P1 |
| 12 | MIB upload limits | Set appropriate `MIB_UPLOAD_MAX_BYTES` | P1 |
| 13 | Rate limiting | API rate limiting via reverse proxy or middleware | P1 |
| 14 | AI Ops guardrails | Keep `LLM_ENABLED=false` unless explicitly needed | P1 |

---

## 9. Logging & Monitoring

| # | Control | Details | Priority |
|---|---------|---------|----------|
| 1 | Centralized logging | Forward app + OS logs to SIEM/syslog collector | P1 |
| 2 | Log rotation | Configure `logrotate` for `/var/log` | P0 |
| 3 | Prometheus metrics | Expose `/metrics`, scrape with Prometheus | P1 |
| 4 | Alerting | Alert on: disk >85%, CPU >90% sustained, OOM kills, failed logins | P1 |
| 5 | Audit log retention | Keep audit logs ≥90 days | P0 |
| 6 | Access logs | nginx access logs with IP, user-agent, status | P1 |
| 7 | Failed auth alerts | Alert after 5 consecutive failed API key attempts | P1 |

---

## 10. Backup & Disaster Recovery

| # | Control | Details | Priority |
|---|---------|---------|----------|
| 1 | Database backup | Daily `pg_dump` with encryption, 30-day retention | P0 |
| 2 | Config backup | Version-control `.env`, Helm values, nginx configs | P0 |
| 3 | Backup verification | Monthly restore test to staging | P1 |
| 4 | RTO/RPO definition | Define per environment (e.g., RPO=1h, RTO=4h) | P1 |
| 5 | MIB file backup | Include `/data/mibs` in backup scope | P2 |

---

## 11. Compliance Checklist Summary

### Quick Audit Script

```bash
#!/bin/bash
# NMS Custom Security Audit — Quick Check
echo "=== OS Hardening Audit ==="

echo -n "SSH root login disabled: "
grep -q "^PermitRootLogin no" /etc/ssh/sshd_config && echo "✅" || echo "❌"

echo -n "SSH password auth disabled: "
grep -q "^PasswordAuthentication no" /etc/ssh/sshd_config && echo "✅" || echo "❌"

echo -n "Firewall active: "
systemctl is-active firewalld >/dev/null && echo "✅" || echo "❌"

echo -n "Fail2ban active: "
systemctl is-active fail2ban >/dev/null && echo "✅" || echo "❌"

echo -n "auditd active: "
systemctl is-active auditd >/dev/null && echo "✅" || echo "❌"

echo -n "SELinux enforcing: "
getenforce 2>/dev/null | grep -q "Enforcing" && echo "✅" || echo "⚠️ $(getenforce 2>/dev/null || echo 'not installed')"

echo -n "Auto-updates enabled: "
systemctl is-enabled dnf-automatic-install.timer 2>/dev/null && echo "✅" || echo "❌"

echo -n "Kernel hardening (syncookies): "
sysctl -n net.ipv4.tcp_syncookies 2>/dev/null | grep -q 1 && echo "✅" || echo "❌"

echo ""
echo "=== Application Security ==="

echo -n "API auth enabled: "
grep -q "API_AUTH_ENABLED=true" .env 2>/dev/null && echo "✅" || echo "❌"

echo -n "Debug disabled: "
grep -q "DEBUG=false" .env 2>/dev/null && echo "✅" || echo "⚠️ check .env"

echo -n "HTTPS enabled: "
grep -q "HTTPS_ENABLED=true" .env 2>/dev/null && echo "✅" || echo "❌"

echo -n "Secret key changed: "
grep -q "change-me" .env 2>/dev/null && echo "❌ using default!" || echo "✅"

echo ""
echo "=== Docker/Container ==="

echo -n "Containers running as non-root: "
docker compose ps -q 2>/dev/null | xargs -I{} docker inspect --format '{{.Config.User}}' {} 2>/dev/null | head -1
```

---

## 12. SELinux

| # | Control | Details | Priority |
|---|---------|---------|----------|
| 1 | SELinux enforcing | `setenforce 1 && sed -i 's/SELINUX=.*/SELINUX=enforcing/' /etc/selinux/config` | P0 |
| 2 | Custom policies | Create policies for NMS services if needed: `audit2allow` | P1 |
| 3 | Container SELinux | `:z` or `:Z` volume mount suffixes for proper labeling | P1 |

---

## References

- [CIS RHEL 8/9 Benchmark](https://www.cisecurity.org/benchmark/red_hat_linux)
- [NIST SP 800-123 — Guide to General Server Security](https://csrc.nist.gov/publications/detail/sp/800-123/final)
- [Docker Security Best Practices](https://docs.docker.com/engine/security/)
- [Kubernetes Security Hardening](https://kubernetes.io/docs/concepts/security/)
- [NMS Custom SECURITY_REVIEW.md](./SECURITY_REVIEW.md)
- [NMS Custom Helm Values](../helm/nms-custom/values.yaml)
