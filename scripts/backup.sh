#!/usr/bin/env bash
# backup.sh — NMS_Custom backup: PostgreSQL + Redis + named volumes
#
# Usage:
#   ./scripts/backup.sh              # full backup to ./backups/YYYYMMDD_HHMMSS/
#   ./scripts/backup.sh --dir /mnt/nas/nms-backups
#   ./scripts/backup.sh --skip-redis
#   ./scripts/backup.sh --volumes    # also archive pg_data/redis_data volumes
#
# Restore: see scripts/restore.sh

set -euo pipefail

# ── Defaults ────────────────────────────────────────────────────────────────
BACKUP_DIR="./backups"
SKIP_REDIS=false
INCLUDE_VOLUMES=false
PG_CONTAINER="${POSTGRES_CONTAINER:-nms-postgres}"
REDIS_CONTAINER="${REDIS_CONTAINER:-nms-redis}"
PG_USER="${POSTGRES_USER:-nms}"
PG_DB="${POSTGRES_DB:-nms}"

# ── Argument parsing ─────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dir)        BACKUP_DIR="$2"; shift 2 ;;
        --skip-redis) SKIP_REDIS=true; shift ;;
        --volumes)    INCLUDE_VOLUMES=true; shift ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUT="${BACKUP_DIR}/${TIMESTAMP}"
mkdir -p "$OUT"

echo "=== NMS_Custom Backup — ${TIMESTAMP} ==="
echo "Output: ${OUT}"

# ── PostgreSQL ───────────────────────────────────────────────────────────────
echo ""
echo "▶ PostgreSQL — pg_dump (custom format, compressed)"
if ! docker inspect "$PG_CONTAINER" &>/dev/null; then
    echo "  ERROR: container '$PG_CONTAINER' not found. Is the stack running?" >&2
    exit 1
fi

DUMP_FILE="nms_postgres_${TIMESTAMP}.dump"
docker exec "$PG_CONTAINER" pg_dump \
    -U "$PG_USER" \
    --format=custom \
    --compress=9 \
    -f "/tmp/${DUMP_FILE}" \
    "$PG_DB"
docker cp "${PG_CONTAINER}:/tmp/${DUMP_FILE}" "${OUT}/${DUMP_FILE}"
docker exec "$PG_CONTAINER" rm -f "/tmp/${DUMP_FILE}"
SIZE=$(du -sh "${OUT}/${DUMP_FILE}" | cut -f1)
echo "  ✓ ${DUMP_FILE} (${SIZE})"

# ── Redis ────────────────────────────────────────────────────────────────────
if [[ "$SKIP_REDIS" == false ]]; then
    echo ""
    echo "▶ Redis — BGSAVE + copy RDB"
    if docker inspect "$REDIS_CONTAINER" &>/dev/null; then
        docker exec "$REDIS_CONTAINER" redis-cli BGSAVE >/dev/null
        # Wait for background save to complete (max 10s)
        for i in $(seq 1 10); do
            STATUS=$(docker exec "$REDIS_CONTAINER" redis-cli LASTSAVE)
            sleep 1
            NEW_STATUS=$(docker exec "$REDIS_CONTAINER" redis-cli LASTSAVE)
            [[ "$NEW_STATUS" != "$STATUS" ]] && break
        done
        RDB_FILE="nms_redis_${TIMESTAMP}.rdb"
        docker cp "${REDIS_CONTAINER}:/data/dump.rdb" "${OUT}/${RDB_FILE}"
        SIZE=$(du -sh "${OUT}/${RDB_FILE}" | cut -f1)
        echo "  ✓ ${RDB_FILE} (${SIZE})"
    else
        echo "  WARN: container '$REDIS_CONTAINER' not found — skipping Redis backup"
    fi
fi

# ── Volume archives (optional) ───────────────────────────────────────────────
if [[ "$INCLUDE_VOLUMES" == true ]]; then
    echo ""
    echo "▶ Docker volumes — raw tar archives"
    for VOL in nms-custom_pg_data nms-custom_redis_data; do
        if docker volume inspect "$VOL" &>/dev/null; then
            VFILE="${VOL}_${TIMESTAMP}.tar.gz"
            docker run --rm \
                -v "${VOL}:/data:ro" \
                -v "$(pwd)/${OUT}:/backup" \
                alpine tar czf "/backup/${VFILE}" -C /data . 2>/dev/null
            SIZE=$(du -sh "${OUT}/${VFILE}" | cut -f1)
            echo "  ✓ ${VFILE} (${SIZE})"
        else
            echo "  SKIP: volume '${VOL}' not found"
        fi
    done
fi

# ── Manifest ─────────────────────────────────────────────────────────────────
MANIFEST="${OUT}/MANIFEST.txt"
{
    echo "NMS_Custom backup — ${TIMESTAMP}"
    echo "Host:       $(hostname)"
    echo "PG version: $(docker exec "$PG_CONTAINER" psql -U "$PG_USER" -tAc 'SELECT version();' | head -1)"
    echo "Contents:"
    ls -lh "$OUT"
} > "$MANIFEST"

echo ""
echo "=== Backup complete ==="
echo "Files:"
ls -lh "$OUT"
echo ""
echo "To restore:"
echo "  ./scripts/restore.sh --dir ${OUT}"
