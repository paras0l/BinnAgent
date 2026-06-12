#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="$ROOT_DIR/binnagent-frontend"

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

main() {
  require_command docker
  require_command npm

  ensure_env_file
  ensure_ollama_model "$CHAT_MODEL"
  ensure_ollama_model "$EMBEDDING_MODEL"

  info "Starting Docker services: db, redis, app"
  (cd "$ROOT_DIR" && compose_cmd up -d --build db redis app)

  info "Running database migrations"
  (cd "$ROOT_DIR" && compose_cmd exec -T app alembic upgrade head)

  install_frontend_deps

  info "Backend API: http://localhost:8000/docs"
  info "Frontend:    http://localhost:3000"
  info "Starting frontend dev server. Press Ctrl+C to stop it."
  info "Docker services stay running. Stop them with: docker compose down"

  (cd "$FRONTEND_DIR" && npm run dev -- --host 0.0.0.0)
}

main "$@"
