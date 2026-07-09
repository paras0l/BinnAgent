#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${1:-$ROOT_DIR/.env.production}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing env file: $ENV_FILE" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
set +a

backfill_feishu_secret_from_dotenv() {
  local key="$1"
  local current="${!key:-}"
  local dotenv="$ROOT_DIR/.env"
  if [[ -n "$current" || ! -f "$dotenv" ]]; then
    return
  fi
  local line value
  line="$(grep -E "^${key}=" "$dotenv" | tail -n 1 || true)"
  if [[ -z "$line" ]]; then
    return
  fi
  value="${line#*=}"
  value="${value%%#*}"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  value="${value%\"}"
  value="${value#\"}"
  value="${value%\'}"
  value="${value#\'}"
  export "$key=$value"
}

backfill_feishu_secret_from_dotenv BINN_FEISHU_APP_ID
backfill_feishu_secret_from_dotenv BINN_FEISHU_APP_SECRET

NETWORK_NAME="${BINN_DOCKER_NETWORK:-binnagent}"
FEISHU_MCP_DIR="$ROOT_DIR/var/feishu-mcp"
FEISHU_MCP_CONFIG="$FEISHU_MCP_DIR/config.json"
FEISHU_MCP_PORT="${BINN_FEISHU_MCP_PORT:-8765}"
FEISHU_MCP_URL_FOR_APP="${BINN_FEISHU_MCP_URL:-}"

is_truthy() {
  case "$(printf "%s" "${1:-}" | tr '[:upper:]' '[:lower:]')" in
    true|1|yes|y|on) return 0 ;;
    *) return 1 ;;
  esac
}

write_feishu_mcp_config() {
  mkdir -p "$FEISHU_MCP_DIR"
  APP_ID="${BINN_FEISHU_APP_ID:?set BINN_FEISHU_APP_ID when BINN_FEISHU_MCP_ENABLED=true}" \
  APP_SECRET="${BINN_FEISHU_APP_SECRET:?set BINN_FEISHU_APP_SECRET when BINN_FEISHU_MCP_ENABLED=true}" \
  MCP_PORT="$FEISHU_MCP_PORT" \
  CONFIG_PATH="$FEISHU_MCP_CONFIG" \
  python3 - <<'PY'
import json
import os
from pathlib import Path

config = {
    "appId": os.environ["APP_ID"],
    "appSecret": os.environ["APP_SECRET"],
    "mode": "streamable",
    "host": "0.0.0.0",
    "port": os.environ["MCP_PORT"],
    "toolNameCase": "dot",
    "language": "en",
    "tokenMode": "tenant_access_token",
    "tools": [
        "im.v1.chat.list",
        "im.v1.chat.search",
        "im.v1.chatMembers.get",
        "im.v1.message.list",
        "im.v1.message.create",
    ],
}

path = Path(os.environ["CONFIG_PATH"])
path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
path.chmod(0o600)
PY
}

start_feishu_mcp_sidecar() {
  if ! is_truthy "${BINN_FEISHU_MCP_ENABLED:-false}"; then
    docker rm -f binnagent-feishu-mcp >/dev/null 2>&1 || true
    return
  fi

  if [[ -n "${BINN_FEISHU_MCP_URL:-}" ]]; then
    FEISHU_MCP_URL_FOR_APP="$BINN_FEISHU_MCP_URL"
    return
  fi

  write_feishu_mcp_config
  docker volume create binnagent_feishu_mcp_package >/dev/null
  docker rm -f binnagent-feishu-mcp >/dev/null 2>&1 || true
  docker run -d \
    --name binnagent-feishu-mcp \
    --restart unless-stopped \
    --network "$NETWORK_NAME" \
    -v "$FEISHU_MCP_CONFIG:/config/config.json:ro" \
    -v binnagent_feishu_mcp_package:/srv/feishu-mcp \
    -w /srv/feishu-mcp \
    node:22-alpine \
    sh -c 'if [ ! -x node_modules/.bin/lark-mcp ]; then npm init -y >/dev/null 2>&1; npm install @larksuiteoapi/lark-mcp@0.5.1; fi; exec ./node_modules/.bin/lark-mcp mcp --config /config/config.json' >/dev/null

  FEISHU_MCP_URL_FOR_APP="http://binnagent-feishu-mcp:${FEISHU_MCP_PORT}/mcp"
}

wait_for_feishu_mcp_sidecar() {
  if ! is_truthy "${BINN_FEISHU_MCP_ENABLED:-false}" || [[ -n "${BINN_FEISHU_MCP_URL:-}" ]]; then
    return
  fi

  for i in $(seq 1 60); do
    if docker run --rm --network "$NETWORK_NAME" node:22-alpine \
      node -e "fetch('http://binnagent-feishu-mcp:${FEISHU_MCP_PORT}/mcp').then(() => process.exit(0)).catch(() => process.exit(1))" \
      >/dev/null 2>&1; then
      return
    fi
    sleep 2
    if [[ "$i" == "60" ]]; then
      echo "Feishu MCP sidecar did not become reachable" >&2
      docker logs binnagent-feishu-mcp >&2 || true
      exit 1
    fi
  done
}

docker network inspect "$NETWORK_NAME" >/dev/null 2>&1 || docker network create "$NETWORK_NAME" >/dev/null
docker volume create binnagent_pgdata >/dev/null
docker volume create binnagent_knowledge >/dev/null

docker start binnagent-db >/dev/null 2>&1 || docker run -d \
  --name binnagent-db \
  --restart unless-stopped \
  --network "$NETWORK_NAME" \
  -e POSTGRES_USER="${POSTGRES_USER:-binn}" \
  -e POSTGRES_PASSWORD="${POSTGRES_PASSWORD:?set POSTGRES_PASSWORD}" \
  -e POSTGRES_DB="${POSTGRES_DB:-binn_agent}" \
  -v binnagent_pgdata:/var/lib/postgresql/data \
  pgvector/pgvector:pg16 >/dev/null

docker start binnagent-redis >/dev/null 2>&1 || docker run -d \
  --name binnagent-redis \
  --restart unless-stopped \
  --network "$NETWORK_NAME" \
  redis:7-alpine >/dev/null

for i in $(seq 1 60); do
  if docker exec binnagent-db pg_isready \
    -U "${POSTGRES_USER:-binn}" \
    -d "${POSTGRES_DB:-binn_agent}" >/dev/null 2>&1; then
    break
  fi
  sleep 2
  if [[ "$i" == "60" ]]; then
    echo "Postgres did not become ready" >&2
    docker logs binnagent-db >&2 || true
    exit 1
  fi
done

start_feishu_mcp_sidecar
wait_for_feishu_mcp_sidecar
FEISHU_ENV_ARGS=()
if [[ -n "$FEISHU_MCP_URL_FOR_APP" ]]; then
  FEISHU_ENV_ARGS=(-e "BINN_FEISHU_MCP_URL=$FEISHU_MCP_URL_FOR_APP")
fi

docker run --rm binnagent-app:latest python -c "from alembic.config import main as alembic_main; import uvicorn; print('runtime dependency check ok:', alembic_main.__name__, uvicorn.__version__)"

docker run --rm \
  --network "$NETWORK_NAME" \
  --env-file "$ENV_FILE" \
  "${FEISHU_ENV_ARGS[@]}" \
  -v binnagent_knowledge:/app/var/knowledge \
  binnagent-app:latest \
  python scripts/run_alembic.py upgrade head

docker rm -f binnagent-app binnagent-web >/dev/null 2>&1 || true

docker run -d \
  --name binnagent-app \
  --restart unless-stopped \
  --network "$NETWORK_NAME" \
  --network-alias app \
  --env-file "$ENV_FILE" \
  "${FEISHU_ENV_ARGS[@]}" \
  -v binnagent_knowledge:/app/var/knowledge \
  binnagent-app:latest >/dev/null

if [[ -d "$ROOT_DIR/binnagent-frontend/dist" && -d "$ROOT_DIR/binnagent-frontend/dist-dev-console" ]]; then
  docker run -d \
    --name binnagent-web \
    --restart unless-stopped \
    --network "$NETWORK_NAME" \
    -p "${BINN_LEARNER_WEB_PORT:-${BINN_HTTP_PORT:-5173}}:80" \
    -p "${BINN_DEV_CONSOLE_PORT:-5174}:5174" \
    -v "$ROOT_DIR/binnagent-frontend/nginx.prod.conf:/etc/nginx/conf.d/default.conf:ro" \
    -v "$ROOT_DIR/binnagent-frontend/dist:/usr/share/nginx/learner:ro" \
    -v "$ROOT_DIR/binnagent-frontend/dist-dev-console:/usr/share/nginx/dev-console:ro" \
    nginx:1.27-alpine >/dev/null
else
  docker run -d \
    --name binnagent-web \
    --restart unless-stopped \
    --network "$NETWORK_NAME" \
    -p "${BINN_LEARNER_WEB_PORT:-${BINN_HTTP_PORT:-5173}}:80" \
    -p "${BINN_DEV_CONSOLE_PORT:-5174}:5174" \
    binnagent-web:latest >/dev/null
fi

docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"
