#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"
CONFIRM_VALUE=""
DRY_RUN=0
ALLOW_NON_LOCAL=0
DOCKER_VOLUME=0

info() {
  printf "\033[1;34m==>\033[0m %s\n" "$*"
}

die() {
  printf "\033[1;31mERROR:\033[0m %s\n" "$*" >&2
  exit 1
}

compose_cmd() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
  elif command -v docker-compose >/dev/null 2>&1; then
    docker-compose "$@"
  else
    die "Docker Compose is required for --docker-volume mode."
  fi
}

wait_for_database() {
  local attempt
  for attempt in {1..30}; do
    if (cd "$ROOT_DIR" && compose_cmd exec -T db pg_isready -U binn -d binn_agent >/dev/null 2>&1); then
      return 0
    fi
    sleep 1
  done
  die "Database did not become ready in time."
}

usage() {
  cat <<'USAGE'
Usage:
  bash scripts/reset_data.sh [--dry-run] [--confirm RESET_ALL_DATA]
  bash scripts/reset_data.sh --docker-volume --confirm RESET_ALL_DATA

Options:
  --dry-run              Inspect table row counts without clearing data.
  --confirm VALUE        Required destructive confirmation token: RESET_ALL_DATA.
  --allow-non-local      Allow reset against a non-local database URL.
  --docker-volume        Recreate Docker database volume, then run migrations.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --confirm)
      CONFIRM_VALUE="${2:-}"
      [[ -n "$CONFIRM_VALUE" ]] || die "--confirm requires a value"
      shift 2
      ;;
    --allow-non-local)
      ALLOW_NON_LOCAL=1
      shift
      ;;
    --docker-volume)
      DOCKER_VOLUME=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "Unknown argument: $1"
      ;;
  esac
done

[[ -x "$PYTHON_BIN" ]] || PYTHON_BIN="python"

if [[ "$DOCKER_VOLUME" -eq 1 ]]; then
  [[ "$CONFIRM_VALUE" == "RESET_ALL_DATA" ]] || die "--docker-volume requires --confirm RESET_ALL_DATA"

  info "Stopping Docker services and removing volumes"
  (cd "$ROOT_DIR" && compose_cmd down -v)

  info "Starting database and Redis"
  (cd "$ROOT_DIR" && compose_cmd up -d db redis)
  wait_for_database

  info "Running database migrations"
  (cd "$ROOT_DIR" && "$PYTHON_BIN" -m alembic upgrade head)

  info "Docker data volume has been recreated."
  exit 0
fi

ARGS=()
if [[ "$DRY_RUN" -eq 1 ]]; then
  ARGS+=(--dry-run)
fi
if [[ -n "$CONFIRM_VALUE" ]]; then
  ARGS+=(--confirm "$CONFIRM_VALUE")
fi
if [[ "$ALLOW_NON_LOCAL" -eq 1 ]]; then
  ARGS+=(--allow-non-local)
fi

info "Resetting application data with safety guards"
if [[ "${#ARGS[@]}" -eq 0 ]]; then
  (cd "$ROOT_DIR" && "$PYTHON_BIN" scripts/reset_data.py)
else
  (cd "$ROOT_DIR" && "$PYTHON_BIN" scripts/reset_data.py "${ARGS[@]}")
fi
