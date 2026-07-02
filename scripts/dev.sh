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

handle_shutdown() {
  cleanup_frontends
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

  ensure_env_file
  configure_local_debug_console
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
  info "Press Ctrl+C to stop frontend dev servers."
  info "Docker services stay running. Stop them with: docker compose down"

  trap cleanup_frontends EXIT
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
