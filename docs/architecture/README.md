# 英语学习陪伴 Agent 架构文档目录

> 文档日期：2026-06-11  
> 项目方向：基于 LangGraph 的英语学习陪伴 Agent，优先落地英语四六级备考场景，兼顾长期英语能力提升。

本目录用于承载模块化技术方案。原有长文档仍保留为研究草案：

- `docs/langgraph-memory-multi-agent-architecture.md`：通用 LangGraph + Memory + 多智能体架构研究。
- `docs/english-learning-companion-agent-architecture.md`：英语学习陪伴场景完整草案。

## 文档索引

| 文档 | 作用 |
|---|---|
| [00-overview.md](./00-overview.md) | 项目总览、系统边界、架构图、模块关系 |
| [01-domain-product.md](./01-domain-product.md) | 英语学习领域建模、用户场景、学习闭环 |
| [02-langgraph-runtime.md](./02-langgraph-runtime.md) | LangGraph 编排层、状态机、节点、恢复机制 |
| [03-memory-system.md](./03-memory-system.md) | 长短期 Memory、错词错因、复习调度、Memory Curator |
| [04-multi-agent-collaboration.md](./04-multi-agent-collaboration.md) | Learning Supervisor 与各技能 Agent 协作方案 |
| [05-learning-tools-and-mcp.md](./05-learning-tools-and-mcp.md) | 学习工具、MCP Gateway、题库、词典、ASR/TTS |
| [06-data-model.md](./06-data-model.md) | 后端数据模型、核心表、索引与存储选型 |
| [07-evaluation-observability.md](./07-evaluation-observability.md) | 学习效果评估、Agent Eval、Tracing 与指标体系 |
| [08-mvp-roadmap.md](./08-mvp-roadmap.md) | MVP 范围、里程碑、验收标准、简历包装 |
| [09-model-provider-and-ollama.md](./09-model-provider-and-ollama.md) | 本地 LLM 优先策略、Ollama 默认接入、模型路由与降级 |

## 阅读顺序

首次阅读建议按以下顺序：

1. 先读 [00-overview.md](./00-overview.md)，理解整体架构。
2. 再读 [01-domain-product.md](./01-domain-product.md)，确认需求和学习闭环。
3. 然后读 [02-langgraph-runtime.md](./02-langgraph-runtime.md)、[03-memory-system.md](./03-memory-system.md)、[04-multi-agent-collaboration.md](./04-multi-agent-collaboration.md)，理解核心 AI Agent 架构。
4. 再读 [09-model-provider-and-ollama.md](./09-model-provider-and-ollama.md)，确认本地模型默认策略和云模型边界。
5. 最后读工具、数据、评估和 MVP 文档，用于后续实现拆解。

## 设计原则

- 技术必须服务学习效果，而不是为了堆栈而堆栈。
- 项目默认优先使用本地部署 LLM，当前以 Ollama 作为默认本地模型运行时；云模型只作为可配置 fallback 或特殊高难任务增强。
- AI 不替用户学习，而是引导用户主动输出。
- Memory 不存泛泛聊天摘要，而要沉淀错词、错因、掌握度、节奏和复习计划。
- 多智能体不是为了“角色多”，而是为了让词汇、听力、阅读、写作、口语和考试策略各自有清晰职责。
- 系统第一阶段优先证明“能持续陪伴并带来可见进步”，再扩展复杂工具生态。
