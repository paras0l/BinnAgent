# Cloud Deployment

This is the lightweight deployment path for family/friend testing.

## Recommended Server

- 2 vCPU
- 4 GB RAM
- 50 GB or larger SSD
- No GPU
- Docker

Use external chat APIs in production. Keep Ollama for local development and leave RAG embeddings isolated on the Ollama path until a separate cloud embedding plan is chosen.

## First Deploy

```bash
git clone <repo-url> /opt/binnagent
cd /opt/binnagent
cp .env.production.example .env.production
```

Edit `.env.production` and set:

- `POSTGRES_PASSWORD`
- `BINN_DEBUG_CONSOLE_TOKEN`
- `BINN_MODEL_PROVIDER`
- `BINN_DEEPSEEK_API_KEY` or `BINN_LONGCAT_API_KEY`
- `BINN_DEBUG_CONSOLE_ALLOWED_ORIGINS`

For Feishu group-learning sync, also set:

- `BINN_FEISHU_MCP_ENABLED=true`
- `BINN_FEISHU_APP_ID`
- `BINN_FEISHU_APP_SECRET`

When `BINN_FEISHU_MCP_ENABLED=true` and `BINN_FEISHU_MCP_URL` is empty, `scripts/restart-prod-docker.sh`
starts a `binnagent-feishu-mcp` sidecar container and points the backend at
`http://binnagent-feishu-mcp:8765/mcp`. Set `BINN_FEISHU_MCP_URL` only when using an external MCP endpoint.

Then start:

```bash
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build
```

If Docker Compose is not available on a small server, use the same images with `docker build`
and `docker run`. The production backend image uses `Dockerfile.prod`, which intentionally skips
OCR system packages while RAG / textbook parsing is isolated.

```bash
docker build -f Dockerfile.prod -t binnagent-app:latest .
docker build -f binnagent-frontend/Dockerfile -t binnagent-web:latest .
./scripts/restart-prod-docker.sh .env.production
```

Learner app:

```text
http://SERVER_IP/
```

Dev Console:

```text
http://SERVER_IP:5174/
```

## Update

```bash
cd /opt/binnagent
git pull
docker compose --env-file .env.production -f docker-compose.prod.yml up -d --build
```
