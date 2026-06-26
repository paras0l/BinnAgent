# Repository Guidelines

## Project Structure & Module Organization

BinnAgent is now a runnable FastAPI + LangGraph/Ollama + React project with architecture docs.

- `src/`: backend application code.
  - `api/`: FastAPI routers.
  - `graph/`: LangGraph daily lesson runtime.
  - `knowledge/`: textbook parsing, RAG, exercises.
  - `memory/`: learner memory extraction and stores.
  - `models/`: SQLAlchemy models.
  - `providers/`: Ollama/model routing.
  - `tools/`: dictionary, SRS, pronunciation, scoring helpers.
- `tests/`: pytest suites for API, graph, memory, tools, providers, database migrations, and integration flows.
- `alembic/`: database migrations.
- `binnagent-frontend/`: React 19 + TypeScript + Vite frontend.
- `browser-extension/`: optional grammar autofill browser extension.
- `docs/architecture/`: modular architecture documents.
- `docs/superpowers/`: design specs and implementation plans.

## 文档准则

### 核心原则

> README 只放引用和简要摘要，详细内容放在独立文档中。

不要把所有内容塞进 README。README 应该保持简洁，作为项目入口索引。

> uv.lock 仅作为本地依赖缓存并已忽略；不要删除或提交，应跨测试复用。

### 文档组织

```text
BinnAgent/
├── README.md
├── AGENTS.md
├── src/
├── tests/
├── alembic/
├── binnagent-frontend/
└── docs/
    ├── architecture/
    ├── web-frontend.md
    └── superpowers/
```

### 文档编写规则

1. `README.md` 只包含项目描述、快速开始、文档索引、当前状态摘要和技术栈概览。
2. 详细文档放在 `docs/` 下。
3. 架构文档使用 `{序号}-{名称}.md`，例如 `13-current-scope-and-status.md`。
4. 当实现状态变化时，同步更新 README 的摘要和 `docs/architecture/13-current-scope-and-status.md`。

## Build, Test, and Development Commands

Backend:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
python -m pytest tests/ -v
ruff check .
```

Frontend:

```bash
cd binnagent-frontend
npm install
npm run dev
npm run lint
npm run build
```

Docker development:

```bash
./scripts/dev.sh
docker compose exec app alembic upgrade head
docker compose exec app python -m pytest tests/ -v
```

Useful inspection commands:

```bash
git status --short
rg "Ollama|Memory|MCP|RAG" docs src tests
find docs/architecture -maxdepth 1 -type f | sort
```

High-frequency command fixes:

```bash
# Local macOS may map python/python3 to interpreters without project deps.
.venv/bin/python -m pytest tests/simulation -q
.venv/bin/ruff check src/simulation tests/simulation scripts/run_learner_simulation.py

# Run deterministic learner simulation through the repo wrapper.
./scripts/run_learner_simulation.sh --persona grade7_low_vocab --scenario smoke_learning_journey
./scripts/run_learner_simulation.sh --test
```

- Prefer `.venv/bin/python -m pytest ...` over bare `python -m pytest` or `python3 -m pytest` in this repo.
- Prefer `.venv/bin/ruff ...` when checking local edits; the global `ruff` may be absent or a different version.
- Use `./scripts/run_learner_simulation.sh` for simulation runs so the correct interpreter is selected automatically.

## Coding Style & Naming Conventions

Markdown documents should use clear numbered prefixes for architecture modules. Keep headings descriptive and avoid overly long sections.

Python:

- 4-space indentation.
- `snake_case` for files, functions, and variables.
- `PascalCase` for classes and Pydantic models.
- Typed interfaces for model providers, tools, memory stores, and API schemas.
- Prefer structured parsers and SQLAlchemy expressions over ad hoc string manipulation.

Frontend:

- React 19 + TypeScript.
- Keep components aligned with existing `pages/`, `components/`, and `hooks/` layout.
- Use `lucide-react` for icons.
- Keep operational screens dense, readable, and task-focused.

## Testing Guidelines

Add or update tests with every behavior change.

- API tests: `tests/api/test_<feature>.py`.
- Graph tests: `tests/graph/test_<node_or_flow>.py`.
- Provider tests: `tests/providers/test_<provider>.py`.
- Migration tests: `tests/db/test_migrations.py`.
- Frontend changes should pass `npm run lint` and `npm run build`.

Prioritize tests for learner authorization boundaries, LangGraph node behavior, Memory write/read rules, RAG indexing and retrieval modes, Ollama provider fallback/repair, and dictionary normalization.

## Commit & Pull Request Guidelines

Use concise conventional-style messages:

```text
docs: align project status documents
feat: expose rag retrieval mode
fix: scope private textbook uploads by learner
test: cover model json repair retry
```

Pull requests should include a short summary, affected documents or modules, validation performed, and follow-up work. For architecture changes, link the relevant file under `docs/architecture/`.

## Security & Configuration Tips

Do not commit API keys, tokens, model credentials, or provider secrets. Ollama remains the default local LLM provider. External providers, including dictionary integrations, must use environment variables or a secret manager.

Learner-owned data must not trust arbitrary `learner_id` values once the project moves beyond local MVP. Prefer a unified current-learner dependency and add authorization tests for chat, memory, knowledge, vocabulary, sessions, and dashboard APIs.
