#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LANGFUSE_DIR="$ROOT_DIR/var/langfuse"
LANGFUSE_ENV="$LANGFUSE_DIR/.env"
APP_ENV="$ROOT_DIR/.env"
LANGFUSE_PROJECT="binnagent-langfuse"
LANGFUSE_UI_PORT=3100

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

langfuse_compose() {
  docker compose -p "$LANGFUSE_PROJECT" --env-file "$LANGFUSE_ENV" \
    -f "$LANGFUSE_DIR/docker-compose.yml" "$@"
}

app_compose() {
  docker compose -f "$ROOT_DIR/docker-compose.yml" "$@"
}

random_hex() {
  openssl rand -hex "$1"
}

env_value() {
  local key="$1"
  sed -n "s/^${key}=//p" "$LANGFUSE_ENV" | tail -n 1
}

upsert_app_env() {
  local key="$1"
  local value="$2"
  touch "$APP_ENV"
  local temp
  temp="$(mktemp)"
  awk -F= -v key="$key" '$1 != key { print }' "$APP_ENV" > "$temp"
  printf "%s=%s\n" "$key" "$value" >> "$temp"
  mv "$temp" "$APP_ENV"
}

check_resources() {
  local info_line memory_bytes memory_mib memory_display cpus
  info_line="$(docker info --format '{{.NCPU}} {{.MemTotal}}')"
  read -r cpus memory_bytes <<<"$info_line"
  memory_mib=$((memory_bytes / 1024 / 1024))
  memory_display="$(awk -v mib="$memory_mib" 'BEGIN { printf "%.1f", mib / 1024 }')"
  info "Docker resources: ${cpus} CPU, approximately ${memory_display} GiB memory"
  if (( cpus < 4 )); then
    warn "Langfuse local development is more reliable with at least 4 Docker CPUs."
  fi
  if (( memory_mib < 7680 )); then
    warn "Docker memory is below 8 GiB. Increase it before starting Langfuse."
  fi
  if command -v ollama >/dev/null 2>&1 && [[ -n "$(ollama ps 2>/dev/null | sed -n '2p')" ]]; then
    warn "An Ollama model is currently loaded. M2/16GB may become memory constrained."
  fi
}

patch_official_compose() {
  python3 - "$LANGFUSE_DIR/docker-compose.yml" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text()
replacements = {
    "      - 3000:3000": "      - 3100:3000",
    "      - 127.0.0.1:6379:6379": "      - 127.0.0.1:16379:6379",
    "      - 127.0.0.1:5432:5432": "      - 127.0.0.1:15432:5432",
}
for old, new in replacements.items():
    text = text.replace(old, new)
path.write_text(text)
PY
}

generate_langfuse_env() {
  if [[ -f "$LANGFUSE_ENV" ]]; then
    return
  fi

  local postgres_password clickhouse_password redis_auth minio_password
  local public_key secret_key admin_password
  postgres_password="$(random_hex 16)"
  clickhouse_password="$(random_hex 16)"
  redis_auth="$(random_hex 16)"
  minio_password="$(random_hex 16)"
  public_key="pk-lf-$(random_hex 16)"
  secret_key="sk-lf-$(random_hex 24)"
  admin_password="$(random_hex 12)"

  cat > "$LANGFUSE_ENV" <<EOF
NEXTAUTH_URL=http://localhost:${LANGFUSE_UI_PORT}
NEXTAUTH_SECRET=$(random_hex 32)
SALT=$(random_hex 32)
ENCRYPTION_KEY=$(random_hex 32)

POSTGRES_USER=postgres
POSTGRES_PASSWORD=${postgres_password}
POSTGRES_DB=postgres
DATABASE_URL=postgresql://postgres:${postgres_password}@postgres:5432/postgres

CLICKHOUSE_USER=clickhouse
CLICKHOUSE_PASSWORD=${clickhouse_password}
REDIS_AUTH=${redis_auth}

MINIO_ROOT_USER=minio
MINIO_ROOT_PASSWORD=${minio_password}
LANGFUSE_S3_EVENT_UPLOAD_ACCESS_KEY_ID=minio
LANGFUSE_S3_EVENT_UPLOAD_SECRET_ACCESS_KEY=${minio_password}
LANGFUSE_S3_MEDIA_UPLOAD_ACCESS_KEY_ID=minio
LANGFUSE_S3_MEDIA_UPLOAD_SECRET_ACCESS_KEY=${minio_password}
LANGFUSE_S3_BATCH_EXPORT_ACCESS_KEY_ID=minio
LANGFUSE_S3_BATCH_EXPORT_SECRET_ACCESS_KEY=${minio_password}

LANGFUSE_INIT_ORG_ID=binnagent-local
LANGFUSE_INIT_ORG_NAME=BinnAgent Local
LANGFUSE_INIT_PROJECT_ID=binnagent
LANGFUSE_INIT_PROJECT_NAME=BinnAgent
LANGFUSE_INIT_PROJECT_PUBLIC_KEY=${public_key}
LANGFUSE_INIT_PROJECT_SECRET_KEY=${secret_key}
LANGFUSE_INIT_USER_EMAIL=admin@binnagent.local
LANGFUSE_INIT_USER_NAME=BinnAgent Admin
LANGFUSE_INIT_USER_PASSWORD=${admin_password}

TELEMETRY_ENABLED=false
EOF
  chmod 600 "$LANGFUSE_ENV"
}

sync_app_credentials() {
  upsert_app_env BINN_LANGFUSE_PUBLIC_KEY "$(env_value LANGFUSE_INIT_PROJECT_PUBLIC_KEY)"
  upsert_app_env BINN_LANGFUSE_SECRET_KEY "$(env_value LANGFUSE_INIT_PROJECT_SECRET_KEY)"
  upsert_app_env BINN_LANGFUSE_BASE_URL "http://localhost:${LANGFUSE_UI_PORT}"
  upsert_app_env BINN_LANGFUSE_DOCKER_BASE_URL "http://host.docker.internal:${LANGFUSE_UI_PORT}"
  upsert_app_env BINN_LANGFUSE_ENVIRONMENT development
}

setup() {
  require_command docker
  require_command git
  require_command openssl
  require_command python3
  require_command curl
  check_resources

  if [[ ! -d "$LANGFUSE_DIR/.git" ]]; then
    info "Cloning official Langfuse repository into var/langfuse"
    mkdir -p "$(dirname "$LANGFUSE_DIR")"
    git clone --depth 1 https://github.com/langfuse/langfuse.git "$LANGFUSE_DIR"
  else
    info "Refreshing official Langfuse Docker Compose"
    git -C "$LANGFUSE_DIR" fetch --depth 1 origin main
    git -C "$LANGFUSE_DIR" checkout -- docker-compose.yml
    git -C "$LANGFUSE_DIR" pull --ff-only
  fi

  patch_official_compose
  generate_langfuse_env
  sync_app_credentials
  info "Langfuse prepared at $LANGFUSE_DIR"
  info "UI will use http://localhost:${LANGFUSE_UI_PORT}"
}

start() {
  setup
  upsert_app_env BINN_LANGFUSE_ENABLED true
  info "Starting Langfuse Web, Worker, ClickHouse, Postgres, Redis, and MinIO"
  langfuse_compose up -d
  info "Waiting for Langfuse UI"
  for _ in $(seq 1 60); do
    if curl -fsS "http://localhost:${LANGFUSE_UI_PORT}" >/dev/null 2>&1; then
      info "Langfuse is ready: http://localhost:${LANGFUSE_UI_PORT}"
      info "Recreating BinnAgent app with local Langfuse enabled"
      app_compose up -d --build app
      return
    fi
    sleep 3
  done
  langfuse_compose ps
  die "Langfuse did not become ready. Run: scripts/langfuse.sh logs"
}

stop() {
  [[ -f "$LANGFUSE_ENV" ]] || die "Langfuse is not set up."
  info "Stopping Langfuse while preserving local traces"
  langfuse_compose down
  upsert_app_env BINN_LANGFUSE_ENABLED false
  if docker compose -f "$ROOT_DIR/docker-compose.yml" ps -q app | grep -q .; then
    info "Recreating BinnAgent app with tracing disabled"
    app_compose up -d app
  fi
}

status() {
  [[ -f "$LANGFUSE_ENV" ]] || die "Langfuse is not set up."
  langfuse_compose ps
  docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}'
}

logs() {
  [[ -f "$LANGFUSE_ENV" ]] || die "Langfuse is not set up."
  langfuse_compose logs -f langfuse-web langfuse-worker
}

credentials() {
  [[ -f "$LANGFUSE_ENV" ]] || die "Langfuse is not set up."
  printf "URL: http://localhost:%s\n" "$LANGFUSE_UI_PORT"
  printf "Email: %s\n" "$(env_value LANGFUSE_INIT_USER_EMAIL)"
  printf "Password: %s\n" "$(env_value LANGFUSE_INIT_USER_PASSWORD)"
}

reset() {
  [[ "${2:-}" == "--yes" ]] || die "This deletes all local traces. Re-run with: reset --yes"
  [[ -f "$LANGFUSE_ENV" ]] || die "Langfuse is not set up."
  langfuse_compose down -v
  info "Local Langfuse data volumes removed."
}

case "${1:-}" in
  setup) setup ;;
  start) start ;;
  stop) stop ;;
  status) status ;;
  logs) logs ;;
  credentials) credentials ;;
  reset) reset "$@" ;;
  *)
    cat <<EOF
Usage: scripts/langfuse.sh <command>

Commands:
  setup        Clone/configure official Langfuse without starting it
  start        Start Langfuse and enable BinnAgent tracing
  stop         Stop Langfuse, preserve data, disable tracing
  status       Show Langfuse containers and resource usage
  logs         Follow Langfuse web/worker logs
  credentials  Show the generated local admin login
  reset --yes  Delete all local Langfuse volumes and traces
EOF
    exit 1
    ;;
esac
