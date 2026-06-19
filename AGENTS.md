# Repository Guidelines

## Project Structure & Module Organization

This repository is currently an architecture-first documentation project for an English learning companion agent.

- `README.md`: repository overview and primary entry point.
- `docs/architecture/`: modular technical design documents.
  - `00-overview.md`: system overview.
  - `02-langgraph-runtime.md`: LangGraph runtime design.
  - `03-memory-system.md`: learner memory design.
  - `09-model-provider-and-ollama.md`: local LLM and Ollama-first strategy.
- `docs/docs/englishtips/`: domain reference materials for English learning.
- `docs/*.md`: longer research drafts and scenario-level architecture notes.

No application source code or tests exist yet. When implementation begins, prefer:

- `src/` for backend code.
- `tests/` for automated tests.
- `configs/` for non-secret configuration examples.

## 文档准则

### 核心原则

> README 只放引用和简要摘要，详细内容放在独立文档中。
**不要把所有内容塞进 README**。README 应该保持简洁，作为项目的入口索引。

> uv.lock 仅作为本地依赖缓存并已忽略；不要删除或提交，应跨测试复用。
### 文档组织

```
BinnAgent/
├── README.md                    # 项目概览 + 文档索引（简洁）
├── AGENTS.md                    # 开发规范与文档准则
├── docs/
│   ├── architecture/            # 架构设计文档
│   ├── web-frontend.md          # 前端文档
│   └── superpowers/specs/       # 设计规范
└── ...
```

### 文档编写规则

1. **README.md** — 只包含：
   - 项目一句话描述
   - 快速开始（3-5 行命令）
   - 文档索引（链接列表）
   - 技术栈概览

2. **详细文档** — 放在 `docs/` 下：
   - 架构设计：`docs/architecture/`
   - 功能文档：`docs/web-frontend.md` 等
   - 设计规范：`docs/superpowers/specs/`

3. **命名规范**：
   - 架构文档：`{序号}-{名称}.md`（如 `00-overview.md`）
   - 功能文档：`{功能名}.md`（如 `web-frontend.md`）
   - 设计规范：`{日期}-{名称}.md`（如 `2026-06-12-web-frontend-design.md`）

## Build, Test, and Development Commands

There is no build system yet. Useful commands for the current repository:

```bash
git status --short
find docs/architecture -maxdepth 1 -type f | sort
rg "Ollama|Memory|MCP" docs
```

When code is added, document setup and test commands in `README.md` before merging.

## Coding Style & Naming Conventions

Markdown documents should use clear numbered prefixes for architecture modules, for example `10-api-design.md`. Keep headings descriptive and avoid overly long sections.

Future Python code should prefer:

- 4-space indentation.
- `snake_case` for files, functions, and variables.
- `PascalCase` for classes and Pydantic models.
- Typed interfaces for model providers, tools, and memory stores.

## Testing Guidelines

No test framework is configured yet. Once code exists, add tests under `tests/` and name files as:

```text
test_<module_name>.py
```

Prioritize tests for LangGraph node behavior, Memory write/read rules, Ollama provider fallback, and dictionary provider normalization.

## Commit & Pull Request Guidelines

Current commit history uses concise conventional-style messages:

```text
docs: add english learning agent architecture
docs: add project readme
```

Use the same pattern:

- `docs: ...` for documentation.
- `feat: ...` for new functionality.
- `fix: ...` for bug fixes.
- `test: ...` for tests.

Pull requests should include a short summary, affected documents or modules, validation performed, and any follow-up work. For architecture changes, link the relevant file under `docs/architecture/`.

## Security & Configuration Tips

Do not commit API keys, tokens, model credentials, or provider secrets. Ollama should remain the default local LLM provider. External providers, including future Youdao dictionary integration, must use environment variables or a secret manager.
