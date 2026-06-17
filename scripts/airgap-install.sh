#!/usr/bin/env bash
# airgap-install.sh — Install NMS_Custom on an air-gapped server.
#
# Run this script from the extracted air-gap bundle directory (the one
# produced by airgap-prepare.sh).  It expects these files alongside it:
#
#   nms_images_base.tar.gz   — timescaledb, redis, prometheus, alertmanager, grafana
#   nms_images_app.tar.gz    — nms-custom-app, nms-custom-frontend
#   nms_code.tar.gz          — NMS_Custom source (prefix: nms-custom/)
#   py_wheels_nms/           — Python .whl files for requirements.txt
#   nms_npm_modules.tar.gz   — node_modules for the frontend
#   nms_frontend_dist.tar.gz — pre-built frontend dist/
#
# Optional (nms-traffic-sim):
#   nms_sim_code.tar.gz      — nms-traffic-sim source
#   py_wheels_sim/           — Python .whl files for nms-traffic-sim
#
# Requirements on the target server:
#   docker (>=24), docker compose plugin, python3 (3.12+), python3-venv

set -euo pipefail

BUNDLE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_BASE="${NMS_INSTALL_DIR:-/opt/nms}"
INSTALL_DIR="${INSTALL_BASE}/nms-custom"
SIM_INSTALL_DIR="${INSTALL_BASE}/nms-traffic-sim"

echo "=== NMS_Custom Air-Gap Installer ==="
echo "Bundle: ${BUNDLE_DIR}"
echo "Target: ${INSTALL_DIR}"
echo ""

# ── Preflight checks ──────────────────────────────────────────────────────────
for cmd in docker python3; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "ERROR: '$cmd' not found. Install it before running this script." >&2
        exit 1
    fi
done

if ! docker compose version &>/dev/null; then
    echo "ERROR: 'docker compose' plugin not found." >&2
    exit 1
fi

# ── 1. Load Docker images ─────────────────────────────────────────────────────
echo "▶ [1/6] Loading Docker images..."
for IMG in nms_images_base.tar.gz nms_images_app.tar.gz; do
    if [[ -f "${BUNDLE_DIR}/${IMG}" ]]; then
        echo "  Loading ${IMG}..."
        docker load < "${BUNDLE_DIR}/${IMG}"
        echo "  ✓ ${IMG}"
    else
        echo "  SKIP: ${IMG} not found"
    fi
done

# ── 2. Extract source code ────────────────────────────────────────────────────
echo ""
echo "▶ [2/6] Extracting NMS_Custom source..."
mkdir -p "$INSTALL_BASE"
tar xzf "${BUNDLE_DIR}/nms_code.tar.gz" -C "$INSTALL_BASE"
# git archive uses prefix nms-custom/ — rename if needed
if [[ -d "${INSTALL_BASE}/nms-custom" && "$INSTALL_DIR" != "${INSTALL_BASE}/nms-custom" ]]; then
    mv "${INSTALL_BASE}/nms-custom" "$INSTALL_DIR"
fi
echo "  ✓ Source extracted to ${INSTALL_DIR}"

# ── 3. Configure environment ──────────────────────────────────────────────────
echo ""
echo "▶ [3/6] Configuring environment..."
if [[ ! -f "${INSTALL_DIR}/.env" ]]; then
    if [[ -f "${INSTALL_DIR}/.env.example" ]]; then
        cp "${INSTALL_DIR}/.env.example" "${INSTALL_DIR}/.env"
        echo "  Created .env from .env.example"
        echo "  ⚠  IMPORTANT: Edit ${INSTALL_DIR}/.env before starting the stack!"
        echo "     Minimum required: POSTGRES_PASSWORD, CREDENTIAL_ENCRYPTION_KEY"
    else
        echo "  WARN: no .env.example found — create ${INSTALL_DIR}/.env manually"
    fi
else
    echo "  .env already exists — skipping"
fi

# ── 4. Frontend: restore node_modules + pre-built dist ───────────────────────
echo ""
echo "▶ [4/6] Restoring frontend assets..."
FRONT="${INSTALL_DIR}/frontend"

if [[ -f "${BUNDLE_DIR}/nms_npm_modules.tar.gz" ]]; then
    tar xzf "${BUNDLE_DIR}/nms_npm_modules.tar.gz" -C "$FRONT"
    echo "  ✓ node_modules restored"
fi

if [[ -f "${BUNDLE_DIR}/nms_frontend_dist.tar.gz" ]]; then
    tar xzf "${BUNDLE_DIR}/nms_frontend_dist.tar.gz" -C "$FRONT"
    echo "  ✓ frontend dist/ restored (no build needed)"
fi

# ── 5. Backend: install Python wheels ────────────────────────────────────────
echo ""
echo "▶ [5/6] Installing backend Python dependencies (offline)..."
BACK="${INSTALL_DIR}/backend"
WHEELS="${BUNDLE_DIR}/py_wheels_nms"

if [[ -d "$WHEELS" ]]; then
    python3 -m venv "${BACK}/.venv" --quiet
    "${BACK}/.venv/bin/pip" install \
        --no-index \
        --find-links="$WHEELS" \
        --quiet \
        -r "${BACK}/requirements.txt"
    echo "  ✓ Backend venv ready at ${BACK}/.venv"
else
    echo "  WARN: py_wheels_nms/ not found — skipping Python install"
    echo "        The Docker image already includes dependencies if using containers."
fi

# ── 5b. nms-traffic-sim (optional) ───────────────────────────────────────────
if [[ -f "${BUNDLE_DIR}/nms_sim_code.tar.gz" ]]; then
    echo ""
    echo "▶ [5b] Installing nms-traffic-sim..."
    mkdir -p "$INSTALL_BASE"
    tar xzf "${BUNDLE_DIR}/nms_sim_code.tar.gz" -C "$INSTALL_BASE"
    if [[ -d "${INSTALL_BASE}/nms-traffic-sim" && "$SIM_INSTALL_DIR" != "${INSTALL_BASE}/nms-traffic-sim" ]]; then
        mv "${INSTALL_BASE}/nms-traffic-sim" "$SIM_INSTALL_DIR"
    fi

    SIM_WHEELS="${BUNDLE_DIR}/py_wheels_sim"
    if [[ -d "$SIM_WHEELS" ]]; then
        python3 -m venv "${SIM_INSTALL_DIR}/.venv" --quiet
        "${SIM_INSTALL_DIR}/.venv/bin/pip" install \
            --no-index \
            --find-links="$SIM_WHEELS" \
            --quiet \
            "${SIM_INSTALL_DIR}"
        echo "  ✓ nms-traffic-sim installed at ${SIM_INSTALL_DIR}"
    fi
fi

# ── 6. Start the stack ────────────────────────────────────────────────────────
echo ""
echo "▶ [6/6] Starting the stack..."
cd "$INSTALL_DIR"

echo "  Running DB migrations..."
docker compose up -d postgres redis
echo "  Waiting for postgres to be healthy..."
for i in $(seq 1 30); do
    docker compose exec postgres pg_isready -U "${POSTGRES_USER:-nms}" -q && break
    sleep 2
done

docker compose run --rm app alembic upgrade head 2>/dev/null || \
    echo "  WARN: migration run skipped (run manually: make migrate)"

docker compose up -d
echo "  ✓ Stack started"

echo ""
echo "=== Installation complete ==="
docker compose ps
echo ""
echo "Next steps:"
echo "  1. Edit ${INSTALL_DIR}/.env if you haven't already"
echo "  2. Run 'make migrate' if migrations were skipped"
echo "  3. Open https://<host>:${FRONTEND_PORT:-5173} in your browser"
echo "  4. Restore a database backup: ./scripts/restore.sh --dir <backup-dir>"
