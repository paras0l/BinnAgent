#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="$ROOT_DIR/binnagent-frontend"
LEARNER_PORT="${BINN_LEARNER_PORT:-5173}"
DEV_CONSOLE_PORT="${BINN_DEV_CONSOLE_PORT:-5174}"
START_DEV_CONSOLE="${BINN_START_DEV_CONSOLE:-true}"
FRONTEND_HOST="${BINN_FRONTEND_HOST:-0.0.0.0}"
LEARNER_LOG="${TMPDIR:-/tmp}/binnagent-learner-vite.log"
DEV_CONSOLE_LOG="${TMPDIR:-/tmp}/binnagent-dev-console-vite.log"
FRONTEND_PIDS=()
FEISHU_MCP_DIR="$ROOT_DIR/var/feishu-mcp"
FEISHU_MCP_CONFIG="$FEISHU_MCP_DIR/config.json"
FEISHU_MCP_LOG="$FEISHU_MCP_DIR/server.log"
FEISHU_MCP_PID_FILE="$FEISHU_MCP_DIR/server.pid"
FEISHU_MCP_PORT="${BINN_FEISHU_MCP_PORT:-8765}"
FEISHU_MCP_PID=""

CHAT_MODEL_FROM_ENV="${BINN_OLLAMA_CHAT_MODEL:-}"
EMBEDDING_MODEL_FROM_ENV="${BINN_OLLAMA_EMBEDDING_MODEL:-}"
CHAT_MODEL="${CHAT_MODEL_FROM_ENV:-gemma4:e2b}"
EMBEDDING_MODEL="${EMBEDDING_MODEL_FROM_ENV:-nomic-embed-text:latest}"

info() {
  printf "\033[1;34m==>\033[0m %s\n" "$*"
}

warn() {
  printf "\033[1;33mWARN:\033[0m %s\n" "$*" >&2
}

die() {
  printf "\033[1;31mERROR:\033[0m %s\n" "$*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"
}

usage() {
  cat <<EOF
Usage: ./scripts/dev.sh [options]

Options:
  --no-console      Start only the Learner App frontend.
  --help            Show this help.

Environment:
  BINN_START_DEV_CONSOLE=false   Same as --no-console.
  BINN_DEBUG_CONSOLE_TOKEN=dev    Token used by backend and Dev Console.
  BINN_LEARNER_PORT=5173          Learner App port.
  BINN_DEV_CONSOLE_PORT=5174      Dev Console port.
  BINN_FEISHU_MCP_ENABLED=true    Start Feishu/Lark MCP sidecar.
  BINN_FEISHU_APP_ID=cli_xxx      Feishu/Lark Open Platform app id.
  BINN_FEISHU_APP_SECRET=xxx      Feishu/Lark Open Platform app secret.
EOF
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --no-console)
        START_DEV_CONSOLE=false
        shift
        ;;
      --help|-h)
        usage
        exit 0
        ;;
      *)
        die "Unknown option: $1"
        ;;
    esac
  done
}

parse_env_value() {
  local value="$1"
  value="${value%%#*}"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  value="${value%\"}"
  value="${value#\"}"
  value="${value%\'}"
  value="${value#\'}"
  printf "%s" "$value"
}

compose_cmd() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
  elif command -v docker-compose >/dev/null 2>&1; then
    docker-compose "$@"
  else
    die "Docker Compose is required. Install Docker Desktop or docker-compose."
  fi
}

ensure_env_file() {
  if [[ ! -f "$ROOT_DIR/.env" && -f "$ROOT_DIR/.env.example" ]]; then
    info "Creating .env from .env.example"
    cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
  fi

  if [[ -f "$ROOT_DIR/.env" ]]; then
    while IFS='=' read -r key value; do
      case "$key" in
        BINN_OLLAMA_CHAT_MODEL)
          if [[ -z "$CHAT_MODEL_FROM_ENV" ]]; then
            CHAT_MODEL="$(parse_env_value "$value")"
          fi
          ;;
        BINN_OLLAMA_EMBEDDING_MODEL)
          if [[ -z "$EMBEDDING_MODEL_FROM_ENV" ]]; then
            EMBEDDING_MODEL="$(parse_env_value "$value")"
          fi
          ;;
      esac
    done < <(grep -E '^[A-Za-z_][A-Za-z0-9_]*=' "$ROOT_DIR/.env" || true)
  fi
}

configure_local_debug_console() {
  export BINN_DEBUG_CONSOLE_ENABLED="${BINN_DEBUG_CONSOLE_ENABLED:-true}"
  export BINN_DEBUG_CONSOLE_TOKEN="${BINN_DEBUG_CONSOLE_TOKEN:-dev}"
  export BINN_DEBUG_CONSOLE_ALLOWED_ORIGINS="${BINN_DEBUG_CONSOLE_ALLOWED_ORIGINS:-[\"http://localhost:${DEV_CONSOLE_PORT}\",\"http://127.0.0.1:${DEV_CONSOLE_PORT}\"]}"
  export VITE_DEBUG_CONSOLE_TOKEN="${VITE_DEBUG_CONSOLE_TOKEN:-$BINN_DEBUG_CONSOLE_TOKEN}"
}

env_file_value() {
  local wanted_key="$1"
  if [[ ! -f "$ROOT_DIR/.env" ]]; then
    return
  fi
  while IFS='=' read -r key value; do
    if [[ "$key" == "$wanted_key" ]]; then
      parse_env_value "$value"
      return
    fi
  done < <(grep -E '^[A-Za-z_][A-Za-z0-9_]*=' "$ROOT_DIR/.env" || true)
}

effective_env_value() {
  local key="$1"
  local current="${!key:-}"
  if [[ -n "$current" ]]; then
    printf "%s" "$current"
  else
    env_file_value "$key"
  fi
}

is_truthy() {
  case "$(printf "%s" "$1" | tr '[:upper:]' '[:lower:]')" in
    true|1|yes|y|on) return 0 ;;
    *) return 1 ;;
  esac
}

write_feishu_mcp_config() {
  local app_id="$1"
  local app_secret="$2"

  mkdir -p "$FEISHU_MCP_DIR"
  APP_ID="$app_id" APP_SECRET="$app_secret" MCP_PORT="$FEISHU_MCP_PORT" CONFIG_PATH="$FEISHU_MCP_CONFIG" python3 - <<'PY'
import json
import os
from pathlib import Path

config = {
    "appId": os.environ["APP_ID"],
    "appSecret": os.environ["APP_SECRET"],
    "mode": "streamable",
    "host": "localhost",
    "port": os.environ["MCP_PORT"],
    "toolNameCase": "dot",
    "language": "en",
    "tokenMode": "tenant_access_token",
    "tools": [
        "im.v1.chat.list",
        "im.v1.chat.search",
        "im.v1.chatMembers.get",
        "im.v1.message.list",
    ],
}

path = Path(os.environ["CONFIG_PATH"])
path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
path.chmod(0o600)
PY
}

install_feishu_mcp_sidecar() {
  local package_dir="$FEISHU_MCP_DIR/package"
  local bin_path="$package_dir/node_modules/.bin/lark-mcp"
  if [[ -x "$bin_path" ]]; then
    return
  fi

  info "Installing Feishu/Lark MCP sidecar"
  mkdir -p "$package_dir"
  (
    cd "$package_dir"
    if [[ ! -f package.json ]]; then
      npm init -y >/dev/null 2>&1
    fi
    npm install @larksuiteoapi/lark-mcp@0.5.1
  )
}

start_feishu_mcp_sidecar() {
  local enabled app_id app_secret
  enabled="$(effective_env_value BINN_FEISHU_MCP_ENABLED)"
  if ! is_truthy "$enabled"; then
    return
  fi

  app_id="$(effective_env_value BINN_FEISHU_APP_ID)"
  app_secret="$(effective_env_value BINN_FEISHU_APP_SECRET)"
  if [[ -z "$app_id" || -z "$app_secret" ]]; then
    warn "BINN_FEISHU_MCP_ENABLED=true but BINN_FEISHU_APP_ID / BINN_FEISHU_APP_SECRET is missing; Feishu MCP sidecar not started."
    return
  fi

  if [[ -f "$FEISHU_MCP_PID_FILE" ]]; then
    local old_pid
    old_pid="$(cat "$FEISHU_MCP_PID_FILE" 2>/dev/null || true)"
    if [[ -n "$old_pid" ]] && kill -0 "$old_pid" >/dev/null 2>&1; then
      info "Stopping previous Feishu MCP sidecar pid $old_pid"
      kill "$old_pid" >/dev/null 2>&1 || true
    fi
  fi

  if is_port_listening "$FEISHU_MCP_PORT"; then
    warn "Feishu MCP port $FEISHU_MCP_PORT is already in use; leaving the existing process untouched."
    return
  fi

  write_feishu_mcp_config "$app_id" "$app_secret"
  install_feishu_mcp_sidecar

  : > "$FEISHU_MCP_LOG"
  info "Starting Feishu MCP sidecar on http://localhost:${FEISHU_MCP_PORT}/mcp"
  "$FEISHU_MCP_DIR/package/node_modules/.bin/lark-mcp" mcp --config "$FEISHU_MCP_CONFIG" > "$FEISHU_MCP_LOG" 2>&1 &
  FEISHU_MCP_PID="$!"
  echo "$FEISHU_MCP_PID" > "$FEISHU_MCP_PID_FILE"

  local attempts=20
  while [[ "$attempts" -gt 0 ]]; do
    if is_port_listening "$FEISHU_MCP_PORT"; then
      info "Feishu MCP sidecar ready: http://localhost:${FEISHU_MCP_PORT}/mcp"
      return
    fi
    attempts=$((attempts - 1))
    sleep 1
  done

  warn "Feishu MCP sidecar did not start. Last log lines:"
  tail -n 40 "$FEISHU_MCP_LOG" >&2 || true
}

ensure_ollama_model() {
  local model="$1"

  if ! command -v ollama >/dev/null 2>&1; then
    warn "ollama command not found. Backend will still start, but LLM calls may fail."
    return
  fi

  if ! ollama list >/dev/null 2>&1; then
    warn "Ollama is not reachable. Start Ollama before using LLM features."
    return
  fi

  if ! ollama list | awk 'NR > 1 {print $1}' | grep -Fxq "$model"; then
    info "Pulling Ollama model: $model"
    ollama pull "$model"
  fi
}

install_frontend_deps() {
  if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
    info "Installing frontend dependencies"
    if [[ -f "$FRONTEND_DIR/package-lock.json" ]]; then
      (cd "$FRONTEND_DIR" && npm ci)
    else
      (cd "$FRONTEND_DIR" && npm install)
    fi
  fi
}

is_port_listening() {
  local port="$1"
  if ! command -v lsof >/dev/null 2>&1; then
    return 1
  fi
  lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
}

start_vite_server() {
  local name="$1"
  local port="$2"
  local npm_script="$3"
  local log_file="$4"

  if is_port_listening "$port"; then
    warn "$name port $port is already in use; leaving the existing process untouched."
    return
  fi

  : > "$log_file"
  info "Starting $name on http://localhost:$port"
  (
    cd "$FRONTEND_DIR"
    npm run "$npm_script" -- --host "$FRONTEND_HOST" --port "$port" --strictPort > "$log_file" 2>&1
  ) &
  FRONTEND_PIDS+=("$!")
}

wait_for_url() {
  local name="$1"
  local url="$2"
  local log_file="$3"
  local attempts=30

  while [[ "$attempts" -gt 0 ]]; do
    if curl -fsS "$url" >/dev/null 2>&1; then
      info "$name ready: $url"
      return
    fi
    attempts=$((attempts - 1))
    sleep 1
  done

  warn "$name did not respond at $url. Last log lines:"
  tail -n 40 "$log_file" >&2 || true
}

cleanup_frontends() {
  local pid
  if [[ "${#FRONTEND_PIDS[@]}" -eq 0 ]]; then
    return
  fi
  info "Stopping frontend dev servers"
  for pid in "${FRONTEND_PIDS[@]}"; do
    if kill -0 "$pid" >/dev/null 2>&1; then
      kill "$pid" >/dev/null 2>&1 || true
    fi
  done
}

cleanup_feishu_mcp() {
  if [[ -z "$FEISHU_MCP_PID" ]]; then
    return
  fi
  if kill -0 "$FEISHU_MCP_PID" >/dev/null 2>&1; then
    info "Stopping Feishu MCP sidecar"
    kill "$FEISHU_MCP_PID" >/dev/null 2>&1 || true
  fi
}

cleanup_all() {
  cleanup_frontends
  cleanup_feishu_mcp
}

handle_shutdown() {
  cleanup_all
  exit 0
}

wait_for_frontends() {
  local pid
  if [[ "${#FRONTEND_PIDS[@]}" -eq 0 ]]; then
    info "No new frontend dev server was started because requested ports were already in use."
    return
  fi

  while true; do
    for pid in "${FRONTEND_PIDS[@]}"; do
      if ! kill -0 "$pid" >/dev/null 2>&1; then
        wait "$pid" || true
        die "A frontend dev server exited. Check logs in ${TMPDIR:-/tmp}/binnagent-*-vite.log"
      fi
    done
    sleep 1
  done
}

main() {
  parse_args "$@"
  require_command docker
  require_command npm
  require_command curl
  require_command python3

  ensure_env_file
  configure_local_debug_console
  start_feishu_mcp_sidecar
  ensure_ollama_model "$CHAT_MODEL"
  ensure_ollama_model "$EMBEDDING_MODEL"

  info "Starting Docker services: db, redis, app"
  (cd "$ROOT_DIR" && compose_cmd up -d --build db redis app)

  info "Running database migrations"
  (cd "$ROOT_DIR" && compose_cmd exec -T app alembic upgrade head)

  install_frontend_deps

  info "Backend API: http://localhost:8000/docs"
  info "Learner App: http://localhost:${LEARNER_PORT}"
  if [[ "$START_DEV_CONSOLE" == "true" ]]; then
    info "Dev Console: http://localhost:${DEV_CONSOLE_PORT}"
    info "Dev Console token: ${BINN_DEBUG_CONSOLE_TOKEN}"
  fi
  info "Press Ctrl+C to stop frontend dev servers and Feishu MCP sidecar."
  info "Docker services stay running. Stop them with: docker compose down"

  trap cleanup_all EXIT
  trap handle_shutdown INT TERM

  start_vite_server "Learner App" "$LEARNER_PORT" "dev" "$LEARNER_LOG"
  if [[ "$START_DEV_CONSOLE" == "true" ]]; then
    start_vite_server "Dev Console" "$DEV_CONSOLE_PORT" "dev:console" "$DEV_CONSOLE_LOG"
  fi

  wait_for_url "Learner App" "http://127.0.0.1:${LEARNER_PORT}/" "$LEARNER_LOG"
  if [[ "$START_DEV_CONSOLE" == "true" ]]; then
    wait_for_url "Dev Console" "http://127.0.0.1:${DEV_CONSOLE_PORT}/" "$DEV_CONSOLE_LOG"
  fi

  wait_for_frontends
}

main "$@"
