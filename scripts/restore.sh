#!/usr/bin/env bash
# restore.sh — NMS_Custom restore from a backup directory produced by backup.sh
#
# Usage:
#   ./scripts/restore.sh --dir ./backups/20260616_143000
#   ./scripts/restore.sh --dir ./backups/20260616_143000 --skip-redis
#   ./scripts/restore.sh --dir ./backups/20260616_143000 --drop-existing
#
# Safety: the script stops ALL app containers before restoring so no active
# connections interfere with pg_restore. Postgres and Redis stay running.

set -euo pipefail

# ── Defaults ────────────────────────────────────────────────────────────────
BACKUP_DIR=""
SKIP_REDIS=false
DROP_EXISTING=false
PG_CONTAINER="${POSTGRES_CONTAINER:-nms-postgres}"
REDIS_CONTAINER="${REDIS_CONTAINER:-nms-redis}"
PG_USER="${POSTGRES_USER:-nms}"
PG_DB="${POSTGRES_DB:-nms}"

# ── Argument parsing ─────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dir)          BACKUP_DIR="$2"; shift 2 ;;
        --skip-redis)   SKIP_REDIS=true; shift ;;
        --drop-existing) DROP_EXISTING=true; shift ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

if [[ -z "$BACKUP_DIR" ]]; then
    echo "Usage: $0 --dir <backup-directory>" >&2
    exit 1
fi

if [[ ! -d "$BACKUP_DIR" ]]; then
    echo "ERROR: backup directory '$BACKUP_DIR' not found." >&2
    exit 1
fi

echo "=== NMS_Custom Restore ==="
echo "Source: ${BACKUP_DIR}"

# ── Find dump file ────────────────────────────────────────────────────────────
DUMP_FILE=$(ls "${BACKUP_DIR}"/nms_postgres_*.dump 2>/dev/null | head -1)
if [[ -z "$DUMP_FILE" ]]; then
    echo "ERROR: no PostgreSQL dump found in '${BACKUP_DIR}'" >&2
    exit 1
fi
echo "Dump: ${DUMP_FILE}"

# ── Stop app services (keep postgres + redis) ─────────────────────────────────
echo ""
echo "▶ Stopping application containers (postgres and redis stay up)..."
APP_SERVICES=$(docker compose ps --services 2>/dev/null | grep -v -E "^postgres$|^redis$" || true)
if [[ -n "$APP_SERVICES" ]]; then
    # shellcheck disable=SC2086
    docker compose stop $APP_SERVICES
    echo "  Stopped: $(echo $APP_SERVICES | tr '\n' ' ')"
fi

# ── PostgreSQL restore ────────────────────────────────────────────────────────
echo ""
echo "▶ PostgreSQL — restoring from $(basename "$DUMP_FILE")"

if ! docker inspect "$PG_CONTAINER" &>/dev/null; then
    echo "ERROR: container '$PG_CONTAINER' not running." >&2
    exit 1
fi

docker cp "$DUMP_FILE" "${PG_CONTAINER}:/tmp/restore.dump"

if [[ "$DROP_EXISTING" == true ]]; then
    echo "  Dropping and recreating database '${PG_DB}'..."
    docker exec "$PG_CONTAINER" psql -U "$PG_USER" -c "DROP DATABASE IF EXISTS ${PG_DB};" postgres
    docker exec "$PG_CONTAINER" psql -U "$PG_USER" -c "CREATE DATABASE ${PG_DB};" postgres
fi

docker exec "$PG_CONTAINER" pg_restore \
    -U "$PG_USER" \
    -d "$PG_DB" \
    --clean \
    --if-exists \
    --no-owner \
    --no-privileges \
    /tmp/restore.dump
docker exec "$PG_CONTAINER" rm -f /tmp/restore.dump
echo "  ✓ PostgreSQL restore complete"

# ── Redis restore ─────────────────────────────────────────────────────────────
if [[ "$SKIP_REDIS" == false ]]; then
    RDB_FILE=$(ls "${BACKUP_DIR}"/nms_redis_*.rdb 2>/dev/null | head -1)
    if [[ -n "$RDB_FILE" ]]; then
        echo ""
        echo "▶ Redis — restoring from $(basename "$RDB_FILE")"
        docker exec "$REDIS_CONTAINER" redis-cli SHUTDOWN NOSAVE 2>/dev/null || true
        sleep 1
        docker start "$REDIS_CONTAINER" 2>/dev/null || true
        sleep 2
        docker cp "$RDB_FILE" "${REDIS_CONTAINER}:/data/dump.rdb"
        docker restart "$REDIS_CONTAINER"
        echo "  ✓ Redis restore complete"
    else
        echo "  INFO: no Redis RDB found in backup — skipping"
    fi
fi

# ── Restart app services ──────────────────────────────────────────────────────
echo ""
echo "▶ Restarting application containers..."
docker compose up -d
echo "  ✓ Stack restarted"

echo ""
echo "=== Restore complete ==="
echo "Run 'docker compose ps' to verify service health."
