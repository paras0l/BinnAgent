# BinnAgent

基于 LangGraph 的英语学习陪伴 Agent 系统技术方案。项目优先落地英语四级、六级备考场景，目标是构建一个能长期陪伴学习者、持续记录错词错因、动态调整计划并形成复习闭环的 AI 英语私教系统。

当前仓库处于架构设计阶段，主要输出模块化技术文档，暂不包含代码实现。

## 核心定位

BinnAgent 不是简单的英语问答机器人，也不是单纯刷题工具。它的核心是学习闭环：

```text
诊断 -> 计划 -> 训练 -> 反馈 -> 复习 -> 复盘 -> 记忆更新 -> 下一次训练
```

系统围绕真实学习需求设计：

- 以四六级备考为优先落地场景。
- 通过 LangGraph 编排每日学习 session。
- 通过长期 Memory 记录错词、错因、学习节奏和能力变化。
- 通过多智能体拆分词汇、听力、阅读、写作、口语和考试策略。
- 默认优先使用本地 Ollama 部署的开源 LLM。
- 为后续 MCP 工具接入预留接口，包括有道词典 provider。

## 架构文档

模块化文档入口：

- [Architecture README](docs/architecture/README.md)
- [00. Overview](docs/architecture/00-overview.md)
- [01. Domain & Product](docs/architecture/01-domain-product.md)
- [02. LangGraph Runtime](docs/architecture/02-langgraph-runtime.md)
- [03. Memory System](docs/architecture/03-memory-system.md)
- [04. Multi-agent Collaboration](docs/architecture/04-multi-agent-collaboration.md)
- [05. Learning Tools & MCP](docs/architecture/05-learning-tools-and-mcp.md)
- [06. Data Model](docs/architecture/06-data-model.md)
- [07. Evaluation & Observability](docs/architecture/07-evaluation-observability.md)
- [08. MVP Roadmap](docs/architecture/08-mvp-roadmap.md)
- [09. Model Provider & Ollama](docs/architecture/09-model-provider-and-ollama.md)

研究草案：

- [LangGraph Memory Multi-agent Architecture](docs/langgraph-memory-multi-agent-architecture.md)
- [English Learning Companion Agent Architecture](docs/english-learning-companion-agent-architecture.md)

领域参考资料：

- [English Tips](docs/docs/englishtips/)

## 技术关键词

- LangGraph
- Long-term Memory
- Multi-agent Collaboration
- Ollama-first Local LLM
- MCP Tool Gateway
- Spaced Repetition
- CET-4 / CET-6 Learning Companion
- Agent Evaluation
- Learning Analytics

## 当前阶段

- 已完成总体技术调研。
- 已完成英语学习陪伴场景化方案。
- 已完成模块化架构文档拆分。
- 已补充本地 Ollama 优先策略。
- 已预留有道词典 MCP/provider 接口。

下一阶段建议进入 MVP 设计和代码实现：

1. FastAPI 项目骨架。
2. Ollama Model Provider。
3. LangGraph 每日课程 runtime。
4. Vocabulary Memory 和间隔复习。
5. Reading/Writing Agent MVP。

