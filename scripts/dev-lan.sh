#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
AGENT_PORT="${AGENT_PORT:-8080}"

detect_lan_ip() {
  if [[ -n "${LAN_IP:-}" ]]; then
    printf "%s\n" "$LAN_IP"
    return 0
  fi

  if command -v ipconfig >/dev/null 2>&1 && command -v route >/dev/null 2>&1; then
    local iface
    iface="$(route get default 2>/dev/null | awk '/interface:/{print $2; exit}')"
    if [[ -n "$iface" ]]; then
      ipconfig getifaddr "$iface" 2>/dev/null && return 0
    fi
  fi

  if command -v ip >/dev/null 2>&1; then
    ip route get 1.1.1.1 2>/dev/null \
      | awk '{for (i=1; i<=NF; i++) if ($i=="src") {print $(i+1); exit}}' \
      && return 0
  fi

  if command -v hostname >/dev/null 2>&1; then
    hostname -I 2>/dev/null | awk '{print $1; exit}' && return 0
  fi

  return 1
}

ensure_port_free() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1 && lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "Port $port is already in use. Stop that server first, then rerun this script." >&2
    lsof -nP -iTCP:"$port" -sTCP:LISTEN >&2
    exit 1
  fi
}

LAN_IP="$(detect_lan_ip || true)"
if [[ -z "$LAN_IP" ]]; then
  echo "Could not detect a LAN IP. Rerun with LAN_IP=<your-ip> $0" >&2
  exit 1
fi

ensure_port_free "$FRONTEND_PORT"
ensure_port_free "$AGENT_PORT"

FRONTEND_ORIGIN="http://${LAN_IP}:${FRONTEND_PORT}"
AGENT_URL="http://${LAN_IP}:${AGENT_PORT}"
export NEXT_PUBLIC_AGENT_URL="$AGENT_URL"
export AEGIS_FRONTEND_ORIGINS="http://localhost:${FRONTEND_PORT},http://127.0.0.1:${FRONTEND_PORT},${FRONTEND_ORIGIN}"

echo "Starting AegisAgent LAN dev servers..."
echo
echo "Laptop frontend: http://localhost:${FRONTEND_PORT}"
echo "Phone frontend:  ${FRONTEND_ORIGIN}"
echo "TEE agent:       ${AGENT_URL}"
echo
echo "If your phone cannot connect, check that it is on the same network and that your firewall allows Node/Python incoming connections."
echo

cleanup() {
  echo
  echo "Stopping LAN dev servers..."
  if [[ -n "${AGENT_PID:-}" ]]; then
    kill "$AGENT_PID" 2>/dev/null || true
  fi
  if [[ -n "${FRONTEND_PID:-}" ]]; then
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

(
  cd "$ROOT_DIR/tee-agent"
  uvicorn aegis_agent.main:app --host 0.0.0.0 --port "$AGENT_PORT"
) &
AGENT_PID="$!"

(
  cd "$ROOT_DIR/frontend"
  npm run dev -- --hostname 0.0.0.0 --port "$FRONTEND_PORT"
) &
FRONTEND_PID="$!"

wait "$AGENT_PID" "$FRONTEND_PID"
