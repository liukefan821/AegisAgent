#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="$ROOT_DIR/frontend"
TEE_AGENT_DIR="$ROOT_DIR/tee-agent"
FRONTEND_ENV="$FRONTEND_DIR/.env.local"
TEE_ENV="$TEE_AGENT_DIR/.env.local"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
AGENT_PORT="${AGENT_PORT:-8080}"

VAULT_ADDRESS="0x4d046e39071b5650b6486e4997f7e5629cdf3f1d"
REGISTRY_ADDRESS="0x77c75bd03df409906130fde880b3c9303ff35227"
VERIFIER_ADDRESS="0x5c949780db9482ab63dd004a23d2d82b719176fd"
VAULT_DEPLOY_BLOCK="10879000"
MOCK_MR_ENCLAVE="0000000000000000000000000000000000000000000000000000000000000001"
MOCK_MR_ENCLAVE_HEX="0x${MOCK_MR_ENCLAVE}"

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

ensure_env_file() {
  local file="$1"
  local example="$2"
  if [[ ! -f "$file" ]]; then
    cp "$example" "$file"
  fi
}

get_env_value() {
  local file="$1"
  local key="$2"
  if [[ ! -f "$file" ]]; then
    return 0
  fi
  grep -E "^${key}=" "$file" | tail -n 1 | cut -d= -f2- || true
}

set_env_value() {
  local file="$1"
  local key="$2"
  local value="$3"
  local tmp
  tmp="$(mktemp)"
  touch "$file"
  awk -v key="$key" -v value="$value" '
    BEGIN { updated = 0 }
    $0 ~ "^" key "=" {
      print key "=" value
      updated = 1
      next
    }
    { print }
    END {
      if (updated == 0) {
        print key "=" value
      }
    }
  ' "$file" > "$tmp"
  mv "$tmp" "$file"
}

prompt_mode() {
  echo "Choose AegisAgent mode:" >&2
  echo "  1) Mock  - frontend mock data, no Gemini key required" >&2
  echo "  2) Live  - Sepolia contracts + tee-agent + Gemini" >&2
  echo >&2
  read -r -p "Input 1 for mock or 2 for live: " mode
  case "$mode" in
    1) printf "mock\n" ;;
    2) printf "live\n" ;;
    *)
      echo "Invalid choice. Please input 1 or 2." >&2
      exit 1
      ;;
  esac
}

LAN_IP="$(detect_lan_ip || true)"
if [[ -z "$LAN_IP" ]]; then
  echo "Could not detect a LAN IP. Rerun with LAN_IP=<your-ip> $0" >&2
  exit 1
fi

MODE="$(prompt_mode)"
FRONTEND_ORIGIN="http://${LAN_IP}:${FRONTEND_PORT}"
AGENT_URL="http://${LAN_IP}:${AGENT_PORT}"
FRONTEND_ORIGINS="http://localhost:${FRONTEND_PORT},http://127.0.0.1:${FRONTEND_PORT},${FRONTEND_ORIGIN}"

ensure_env_file "$FRONTEND_ENV" "$FRONTEND_DIR/.env.example"
ensure_env_file "$TEE_ENV" "$TEE_AGENT_DIR/.env.example"

set_env_value "$FRONTEND_ENV" "NEXT_PUBLIC_AGENT_URL" "$AGENT_URL"

if [[ "$MODE" == "mock" ]]; then
  set_env_value "$FRONTEND_ENV" "NEXT_PUBLIC_USE_MOCK" "true"
else
  set_env_value "$FRONTEND_ENV" "NEXT_PUBLIC_USE_MOCK" "false"
  set_env_value "$FRONTEND_ENV" "NEXT_PUBLIC_VAULT_ADDRESS" "$VAULT_ADDRESS"
  set_env_value "$FRONTEND_ENV" "NEXT_PUBLIC_REGISTRY_ADDRESS" "$REGISTRY_ADDRESS"
  set_env_value "$FRONTEND_ENV" "NEXT_PUBLIC_VERIFIER_ADDRESS" "$VERIFIER_ADDRESS"
  set_env_value "$FRONTEND_ENV" "NEXT_PUBLIC_VAULT_DEPLOY_BLOCK" "$VAULT_DEPLOY_BLOCK"

  set_env_value "$TEE_ENV" "LLM_PROVIDER" "gemini"
  set_env_value "$TEE_ENV" "GEMINI_MODEL" "gemini-2.5-flash-lite"
  set_env_value "$TEE_ENV" "AEGIS_MOCK_QUOTE" "true"
  set_env_value "$TEE_ENV" "ENCLAVE_IMAGE_HASH" "$MOCK_MR_ENCLAVE_HEX"
  set_env_value "$TEE_ENV" "MOCK_MR_ENCLAVE" "$MOCK_MR_ENCLAVE"
  set_env_value "$TEE_ENV" "AEGIS_FRONTEND_ORIGINS" "$FRONTEND_ORIGINS"

  if [[ -z "$(get_env_value "$TEE_ENV" "GEMINI_API_KEY")" ]]; then
    echo
    read -r -s -p "Enter Gemini API key: " gemini_key
    echo
    if [[ -z "$gemini_key" ]]; then
      echo "Gemini API key is required for live mode." >&2
      exit 1
    fi
    set_env_value "$TEE_ENV" "GEMINI_API_KEY" "$gemini_key"
  fi
fi

ensure_port_free "$FRONTEND_PORT"
if [[ "$MODE" == "live" ]]; then
  ensure_port_free "$AGENT_PORT"
fi

export NEXT_PUBLIC_AGENT_URL="$AGENT_URL"
export AEGIS_FRONTEND_ORIGINS="$FRONTEND_ORIGINS"

echo
echo "Starting AegisAgent in ${MODE} mode..."
echo
echo "Laptop frontend: http://localhost:${FRONTEND_PORT}"
echo "Phone frontend:  ${FRONTEND_ORIGIN}"
if [[ "$MODE" == "live" ]]; then
  echo "TEE agent:       ${AGENT_URL}"
else
  echo "TEE agent:       skipped in mock mode"
fi
echo

cleanup() {
  echo
  echo "Stopping AegisAgent dev servers..."
  if [[ -n "${AGENT_PID:-}" ]]; then
    kill "$AGENT_PID" 2>/dev/null || true
  fi
  if [[ -n "${FRONTEND_PID:-}" ]]; then
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

if [[ "$MODE" == "live" ]]; then
  (
    cd "$TEE_AGENT_DIR"
    uvicorn aegis_agent.main:app --host 0.0.0.0 --port "$AGENT_PORT"
  ) &
  AGENT_PID="$!"
fi

(
  cd "$FRONTEND_DIR"
  npm run dev -- --hostname 0.0.0.0 --port "$FRONTEND_PORT"
) &
FRONTEND_PID="$!"

if [[ "$MODE" == "live" ]]; then
  wait "$AGENT_PID" "$FRONTEND_PID"
else
  wait "$FRONTEND_PID"
fi
