#!/usr/bin/env bash
# service-ctl.sh — Manage NMS_Custom containers and service health
#
# Usage:
#   ./scripts/service-ctl.sh status                  # Show all container statuses
#   ./scripts/service-ctl.sh status receivers         # Show only receivers
#   ./scripts/service-ctl.sh restart <name>           # Restart a container
#   ./scripts/service-ctl.sh restart workers          # Restart all worker containers
#   ./scripts/service-ctl.sh restart receivers        # Restart all receivers
#   ./scripts/service-ctl.sh logs <name> [-f]         # Tail container logs
#   ./scripts/service-ctl.sh health                   # Query /api/system/health

set -euo pipefail

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"
API_URL="${NMS_API_URL:-http://localhost:8000}"
API_KEY="${NMS_API_KEY:-}"

# ── Container groups ────────────────────────────────────────────────────────
WORKERS=(
    nms-worker-poller
    nms-worker-topology
    nms-worker-report
    nms-worker-alarm
    nms-worker-discovery
    nms-worker-telemetry
)

RECEIVERS=(
    nms-trap-receiver
    nms-syslog-receiver
    nms-telemetry-receiver
)

ALL_APP=(
    nms-app
    nms-frontend
    "${WORKERS[@]}"
    "${RECEIVERS[@]}"
)

# ── Helpers ─────────────────────────────────────────────────────────────────
_header() { echo -e "\n\033[1;36m── $* ──\033[0m"; }
_ok()     { echo -e "  \033[0;32m✓\033[0m $*"; }
_warn()   { echo -e "  \033[0;33m⚠\033[0m $*"; }
_err()    { echo -e "  \033[0;31m✗\033[0m $*"; }

_state_color() {
    case "$1" in
        Up*)      echo -e "\033[0;32m$1\033[0m" ;;
        Exited*)  echo -e "\033[0;31m$1\033[0m" ;;
        Restarting*) echo -e "\033[0;33m$1\033[0m" ;;
        *)        echo -e "\033[0;37m$1\033[0m" ;;
    esac
}

_container_status() {
    local name="$1"
    local status
    status=$(docker inspect --format '{{.State.Status}} ({{.State.Health.Status}})' "$name" 2>/dev/null || echo "not found")
    echo "$status"
}

cmd_status() {
    local filter="${1:-all}"
    _header "NMS Container Status"

    declare -A GROUPS=(
        [infrastructure]="nms-postgres nms-redis"
        [application]="nms-app nms-frontend"
        [workers]="${WORKERS[*]}"
        [receivers]="${RECEIVERS[*]}"
    )

    local show_groups
    case "$filter" in
        workers)    show_groups=(workers) ;;
        receivers)  show_groups=(receivers) ;;
        app)        show_groups=(application) ;;
        infra*)     show_groups=(infrastructure) ;;
        *)          show_groups=(infrastructure application workers receivers) ;;
    esac

    for group in "${show_groups[@]}"; do
        echo ""
        echo "  ${group^}:"
        printf "  %-35s %-30s\n" "Container" "State"
        printf "  %-35s %-30s\n" "---------" "-----"
        for name in ${GROUPS[$group]}; do
            local state
            state=$(docker inspect --format '{{.State.Status}}' "$name" 2>/dev/null || echo "not found")
            printf "  %-35s " "$name"
            _state_color "$state"
        done
    done
    echo ""
}

cmd_restart() {
    local target="${1:-}"
    if [[ -z "$target" ]]; then
        echo "Usage: $0 restart <container-name|workers|receivers|all-app>" >&2
        exit 1
    fi

    local containers=()
    case "$target" in
        workers)   containers=("${WORKERS[@]}") ;;
        receivers) containers=("${RECEIVERS[@]}") ;;
        all-app)   containers=("${ALL_APP[@]}") ;;
        *)         containers=("$target") ;;
    esac

    _header "Restarting: ${target}"
    for name in "${containers[@]}"; do
        if docker inspect "$name" &>/dev/null; then
            docker restart "$name" >/dev/null
            _ok "$name restarted"
        else
            _warn "$name not found — skipping"
        fi
    done
    echo ""
}

cmd_logs() {
    local name="${1:-}"
    if [[ -z "$name" ]]; then
        echo "Usage: $0 logs <container-name> [-f]" >&2
        exit 1
    fi
    shift
    local follow_flag=""
    [[ "${1:-}" == "-f" ]] && follow_flag="-f"
    docker logs ${follow_flag} --tail=100 "$name"
}

cmd_health() {
    _header "NMS System Health (API)"
    local headers=()
    [[ -n "$API_KEY" ]] && headers+=(-H "x-api-key: ${API_KEY}")
    if command -v curl &>/dev/null; then
        curl -sf "${headers[@]}" "${API_URL}/api/system/health" | python3 -m json.tool 2>/dev/null || \
        curl -sf "${headers[@]}" "${API_URL}/api/system/health"
    else
        echo "  curl not found — install curl to query the API" >&2
    fi
    echo ""
}

# ── Main ────────────────────────────────────────────────────────────────────
COMMAND="${1:-status}"
shift || true

case "$COMMAND" in
    status)  cmd_status "${1:-all}" ;;
    restart) cmd_restart "${1:-}" ;;
    logs)    cmd_logs "$@" ;;
    health)  cmd_health ;;
    help|--help|-h)
        echo "Usage: $0 <command> [args]"
        echo ""
        echo "Commands:"
        echo "  status [group]          Show container status (group: workers|receivers|app|infra)"
        echo "  restart <target>        Restart container(s) (target: name|workers|receivers|all-app)"
        echo "  logs <name> [-f]        Show container logs"
        echo "  health                  Query /api/system/health via API"
        echo ""
        echo "Environment:"
        echo "  NMS_API_URL             API base URL (default: http://localhost:8000)"
        echo "  NMS_API_KEY             API key for authenticated requests"
        ;;
    *)
        echo "Unknown command: $COMMAND. Run '$0 help' for usage." >&2
        exit 1
        ;;
esac
