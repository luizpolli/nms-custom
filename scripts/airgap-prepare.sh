#!/usr/bin/env bash
# airgap-prepare.sh — Package NMS_Custom + nms-traffic-sim for air-gapped deployment.
#
# Run this on a machine WITH internet access. It produces a self-contained
# tarball that can be transferred to the target server and installed with
# scripts/airgap-install.sh.
#
# Usage:
#   ./scripts/airgap-prepare.sh
#   ./scripts/airgap-prepare.sh --out /tmp/nms-airgap --sim-dir ../nms-traffic-sim
#   ./scripts/airgap-prepare.sh --skip-sim     # skip nms-traffic-sim packaging
#   ./scripts/airgap-prepare.sh --skip-images  # skip Docker image export (already transferred)
#
# Requirements on the build machine:
#   docker, docker compose, python3, pip, node >=20, npm

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SIM_DIR="${REPO_DIR}/../nms-traffic-sim"
OUT_BASE="${REPO_DIR}/dist/airgap"
SKIP_SIM=false
SKIP_IMAGES=false
PYTHON_VERSION="3.12"
ARCH="linux_x86_64"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --out)         OUT_BASE="$2"; shift 2 ;;
        --sim-dir)     SIM_DIR="$2";  shift 2 ;;
        --skip-sim)    SKIP_SIM=true; shift ;;
        --skip-images) SKIP_IMAGES=true; shift ;;
        *) echo "Unknown option: $1" >&2; exit 1 ;;
    esac
done

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
STAGE="${OUT_BASE}/stage"
mkdir -p "$STAGE"

echo "=== NMS_Custom Air-Gap Packager ==="
echo "Repo:   ${REPO_DIR}"
echo "Output: ${OUT_BASE}"

# ── 1. Docker images ──────────────────────────────────────────────────────────
if [[ "$SKIP_IMAGES" == false ]]; then
    echo ""
    echo "▶ [1/5] Building and exporting Docker images..."
    cd "$REPO_DIR"

    docker compose build --no-cache
    docker compose pull --ignore-buildable 2>/dev/null || docker compose pull 2>/dev/null || true

    # Collect image names from compose
    BASE_IMAGES=(
        "timescale/timescaledb:latest-pg16"
        "redis:7-alpine"
        "prom/prometheus:latest"
        "prom/alertmanager:latest"
        "grafana/grafana:latest"
    )
    APP_IMAGES=(
        "nms-custom-app"
        "nms-custom-frontend"
    )

    echo "  Exporting base images..."
    docker save "${BASE_IMAGES[@]}" | gzip > "${STAGE}/nms_images_base.tar.gz"
    echo "  ✓ nms_images_base.tar.gz ($(du -sh "${STAGE}/nms_images_base.tar.gz" | cut -f1))"

    echo "  Exporting app images..."
    docker save "${APP_IMAGES[@]}" 2>/dev/null | gzip > "${STAGE}/nms_images_app.tar.gz" || \
        echo "  WARN: app images not found — run 'docker compose build' first"
    if [[ -s "${STAGE}/nms_images_app.tar.gz" ]]; then
        echo "  ✓ nms_images_app.tar.gz ($(du -sh "${STAGE}/nms_images_app.tar.gz" | cut -f1))"
    fi
fi

# ── 2. Python wheels (backend) ────────────────────────────────────────────────
echo ""
echo "▶ [2/5] Downloading Python wheels for backend..."
PY_WHEELS="${STAGE}/py_wheels_nms"
mkdir -p "$PY_WHEELS"
pip download \
    --dest "$PY_WHEELS" \
    --python-version "$PYTHON_VERSION" \
    --platform "$ARCH" \
    --only-binary=:all: \
    -r "${REPO_DIR}/backend/requirements.txt" \
    --quiet
echo "  ✓ $(ls "$PY_WHEELS" | wc -l | xargs) wheels downloaded"

# ── 3. npm node_modules (frontend) ───────────────────────────────────────────
echo ""
echo "▶ [3/5] Installing and archiving frontend node_modules..."
cd "${REPO_DIR}/frontend"
npm ci --prefer-offline --quiet
echo "  Building production bundle (included in archive)..."
npm run build --silent
tar czf "${STAGE}/nms_npm_modules.tar.gz" node_modules/
echo "  ✓ nms_npm_modules.tar.gz ($(du -sh "${STAGE}/nms_npm_modules.tar.gz" | cut -f1))"
# Also include the dist/ build artifact so the target doesn't need to rebuild
tar czf "${STAGE}/nms_frontend_dist.tar.gz" dist/
echo "  ✓ nms_frontend_dist.tar.gz ($(du -sh "${STAGE}/nms_frontend_dist.tar.gz" | cut -f1))"

# ── 4. nms-traffic-sim wheels ─────────────────────────────────────────────────
if [[ "$SKIP_SIM" == false ]]; then
    echo ""
    echo "▶ [4/5] Downloading Python wheels for nms-traffic-sim..."
    if [[ -d "$SIM_DIR" ]]; then
        SIM_WHEELS="${STAGE}/py_wheels_sim"
        mkdir -p "$SIM_WHEELS"
        pip download \
            --dest "$SIM_WHEELS" \
            --python-version "$PYTHON_VERSION" \
            --platform "$ARCH" \
            --only-binary=:all: \
            -r "${SIM_DIR}/requirements.txt" \
            --quiet 2>/dev/null || \
        pip download \
            --dest "$SIM_WHEELS" \
            --python-version "$PYTHON_VERSION" \
            --platform "$ARCH" \
            --only-binary=:all: \
            $(cd "$SIM_DIR" && python3 -c "import tomllib; d=tomllib.load(open('pyproject.toml','rb')); print(' '.join(d['project']['dependencies']))" 2>/dev/null || echo "") \
            --quiet
        echo "  ✓ $(ls "$SIM_WHEELS" | wc -l | xargs) wheels downloaded"
    else
        echo "  WARN: nms-traffic-sim not found at '${SIM_DIR}' — skipping"
        echo "        Use --sim-dir to specify the correct path"
    fi
else
    echo ""
    echo "▶ [4/5] Skipping nms-traffic-sim (--skip-sim)"
fi

# ── 5. Source code archive ────────────────────────────────────────────────────
echo ""
echo "▶ [5/5] Archiving source code..."
cd "$REPO_DIR"
git archive \
    --format=tar.gz \
    --prefix=nms-custom/ \
    -o "${STAGE}/nms_code.tar.gz" \
    HEAD
echo "  ✓ nms_code.tar.gz ($(du -sh "${STAGE}/nms_code.tar.gz" | cut -f1))"

# Include nms-traffic-sim code if available
if [[ "$SKIP_SIM" == false && -d "$SIM_DIR" ]]; then
    (cd "$SIM_DIR" && git archive \
        --format=tar.gz \
        --prefix=nms-traffic-sim/ \
        -o "${STAGE}/nms_sim_code.tar.gz" \
        HEAD 2>/dev/null) && \
    echo "  ✓ nms_sim_code.tar.gz ($(du -sh "${STAGE}/nms_sim_code.tar.gz" | cut -f1))" || \
    echo "  WARN: could not archive nms-traffic-sim (not a git repo?)"
fi

# ── Manifest ──────────────────────────────────────────────────────────────────
{
    echo "NMS_Custom Air-Gap Bundle"
    echo "Created:    ${TIMESTAMP}"
    echo "NMS version: $(cd "$REPO_DIR" && git describe --tags --always 2>/dev/null || echo 'unknown')"
    echo ""
    echo "Contents:"
    ls -lh "$STAGE"
    echo ""
    echo "Install with:"
    echo "  tar xzf nms_airgap_*.tar.gz"
    echo "  cd nms_airgap_*/"
    echo "  ./scripts/airgap-install.sh"
} > "${STAGE}/MANIFEST.txt"

cp "${REPO_DIR}/scripts/airgap-install.sh" "${STAGE}/airgap-install.sh"
chmod +x "${STAGE}/airgap-install.sh"

# ── Final tarball ─────────────────────────────────────────────────────────────
BUNDLE="${OUT_BASE}/nms_airgap_${TIMESTAMP}.tar.gz"
cd "$OUT_BASE"
tar czf "$BUNDLE" -C stage .
BUNDLE_SIZE=$(du -sh "$BUNDLE" | cut -f1)

echo ""
echo "=== Package complete ==="
echo "Bundle: ${BUNDLE}"
echo "Size:   ${BUNDLE_SIZE}"
echo ""
echo "Transfer to target server, then:"
echo "  tar xzf $(basename "$BUNDLE")"
echo "  chmod +x airgap-install.sh"
echo "  ./airgap-install.sh"
