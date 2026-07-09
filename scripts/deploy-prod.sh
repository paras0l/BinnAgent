#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="$ROOT_DIR/binnagent-frontend"

DEPLOY_HOST="${BINN_DEPLOY_HOST:-root@8.152.198.107}"
REMOTE_DIR="${BINN_DEPLOY_REMOTE_DIR:-/opt/binnagent}"
REMOTE_ENV_FILE="${BINN_DEPLOY_ENV_FILE:-$REMOTE_DIR/.env.production}"
REMOTE_TMP_DIR="${BINN_DEPLOY_TMP_DIR:-/tmp}"
ARCHIVE_NAME="binnagent-deploy-$(date +%Y%m%d-%H%M%S).tgz"
LOCAL_ARCHIVE="${TMPDIR:-/tmp}/$ARCHIVE_NAME"
REMOTE_ARCHIVE="$REMOTE_TMP_DIR/$ARCHIVE_NAME"

RUN_LINT="${BINN_DEPLOY_RUN_LINT:-true}"
RUN_NPM_CI="${BINN_DEPLOY_NPM_CI:-auto}"
DOCKER_BUILD_NO_CACHE="${BINN_DEPLOY_DOCKER_BUILD_NO_CACHE:-false}"
DRY_RUN=false

usage() {
  cat <<EOF
Usage: $(basename "$0") [--dry-run]

Environment variables:
  BINN_DEPLOY_HOST=root@8.152.198.107
  BINN_DEPLOY_REMOTE_DIR=/opt/binnagent
  BINN_DEPLOY_ENV_FILE=/opt/binnagent/.env.production
  BINN_DEPLOY_RUN_LINT=true|false
  BINN_DEPLOY_NPM_CI=auto|true|false
  BINN_DEPLOY_DOCKER_BUILD_NO_CACHE=true|false
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

run() {
  echo "+ $*"
  if [[ "$DRY_RUN" == "false" ]]; then
    "$@"
  fi
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

require_command npm
require_command tar
require_command scp
require_command ssh

echo "Deploy target: $DEPLOY_HOST:$REMOTE_DIR"
echo "Remote env:    $REMOTE_ENV_FILE"

cd "$FRONTEND_DIR"
if [[ "$RUN_NPM_CI" == "true" || ( "$RUN_NPM_CI" == "auto" && ! -d node_modules ) ]]; then
  run npm ci
fi

if [[ "$RUN_LINT" == "true" ]]; then
  run npm run lint
fi
run npm run build
run npm run build:console

cd "$ROOT_DIR"
echo "Creating deploy archive: $LOCAL_ARCHIVE"
if [[ "$DRY_RUN" == "false" ]]; then
  rm -f "$LOCAL_ARCHIVE"
  COPYFILE_DISABLE=1 tar \
    --exclude='.DS_Store' \
    --exclude='._*' \
    --exclude='.git' \
    --exclude='.venv' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='binnagent-frontend/node_modules' \
    --exclude='remotion-video/node_modules' \
    --exclude='var' \
    --exclude='.env' \
    --exclude='.env.production' \
    -czf "$LOCAL_ARCHIVE" \
    Dockerfile.prod \
    pyproject.toml \
    alembic.ini \
    alembic \
    books \
    scripts \
    src \
    binnagent-frontend
fi

run scp "$LOCAL_ARCHIVE" "$DEPLOY_HOST:$REMOTE_ARCHIVE"

REMOTE_SCRIPT=$(cat <<'EOS'
set -euo pipefail

REMOTE_DIR="$1"
REMOTE_ENV_FILE="$2"
REMOTE_ARCHIVE="$3"
DOCKER_BUILD_NO_CACHE="$4"

if [[ ! -f "$REMOTE_ENV_FILE" ]]; then
  echo "Missing remote env file: $REMOTE_ENV_FILE" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
. "$REMOTE_ENV_FILE"
set +a

mkdir -p "$REMOTE_DIR"
cd "$REMOTE_DIR"

rm -rf \
  src \
  alembic \
  scripts \
  books \
  binnagent-frontend/src \
  binnagent-frontend/public \
  binnagent-frontend/dist \
  binnagent-frontend/dist-dev-console

tar -xzf "$REMOTE_ARCHIVE" -C "$REMOTE_DIR"
chmod +x "$REMOTE_DIR/scripts/restart-prod-docker.sh"

BUILD_ARGS=(-f Dockerfile.prod -t binnagent-app:latest)
if [[ "$DOCKER_BUILD_NO_CACHE" == "true" ]]; then
  BUILD_ARGS+=(--no-cache)
fi
BUILD_ARGS+=("$REMOTE_DIR")
docker image rm -f binnagent-app:latest >/dev/null 2>&1 || true
docker build "${BUILD_ARGS[@]}"
docker run --rm binnagent-app:latest python -c "from alembic.config import main as alembic_main; import uvicorn; print('runtime dependency check ok:', alembic_main.__name__, uvicorn.__version__)"
"$REMOTE_DIR/scripts/restart-prod-docker.sh" "$REMOTE_ENV_FILE"

echo
echo "Smoke checks:"
curl -fsS -o /dev/null "http://127.0.0.1:${BINN_LEARNER_WEB_PORT:-${BINN_HTTP_PORT:-5173}}/"
echo "learner ok"
curl -fsS -o /dev/null "http://127.0.0.1:${BINN_DEV_CONSOLE_PORT:-5174}/"
echo "dev console ok"

rm -f "$REMOTE_ARCHIVE"
EOS
)

echo "Running remote deploy"
if [[ "$DRY_RUN" == "false" ]]; then
  ssh "$DEPLOY_HOST" "bash -s" -- "$REMOTE_DIR" "$REMOTE_ENV_FILE" "$REMOTE_ARCHIVE" "$DOCKER_BUILD_NO_CACHE" <<<"$REMOTE_SCRIPT"
else
  echo "+ ssh $DEPLOY_HOST bash -s -- $REMOTE_DIR $REMOTE_ENV_FILE $REMOTE_ARCHIVE $DOCKER_BUILD_NO_CACHE"
fi

if [[ "$DRY_RUN" == "false" ]]; then
  rm -f "$LOCAL_ARCHIVE"
fi

echo "Deploy complete."
