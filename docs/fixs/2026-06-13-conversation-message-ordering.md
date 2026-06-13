# 对话消息顺序偶现错乱修复复盘

## 背景

BinnAgent 的聊天能力已经接入 learner 身份、历史会话、可见化 Memory 和 SSE 流式输出。用户在使用过程中发现：同一个会话中，历史对话偶尔会出现 user / assistant 消息顺序不对的情况。

这类问题会直接破坏 Agent 体验，因为 Memory 不只是“存下来”，还必须以正确顺序回放给用户和 LLM。顺序一旦错乱，前端历史展示、继续对话上下文、长回答续写和后续摘要都会被污染。

## 问题描述

现象包括：

- 历史会话中偶现 assistant 回复出现在 user 提问前。
- 刷新页面或重新加载 thread 后，消息顺序与发送时看到的不一致。
- 流式回答完成后，短时间内刷新更容易暴露顺序问题。

问题不是稳定复现，而是“偶现”。这说明它更可能来自排序依据不稳定、异步写入时序或数据库时间精度，而不是单纯的前端渲染错误。

## 根因分析

原实现中，历史消息主要按 `created_at ASC, id ASC` 排序。

这个方案存在三个隐患：

1. `created_at` 由数据库 `now()` 生成，不同数据库和运行环境的时间精度不完全一致。
2. SSE 流式路径中，user message 先写入并提交，assistant message 在流式完成后由另一个独立事务写入。
3. 消息主键是 UUID。UUID 适合全局唯一标识，但不代表业务发生顺序，不能作为稳定的同时间排序依据。

因此，当 user 和 assistant 写入时间非常接近，或者时间戳精度不足时，`created_at` 可能相同或无法表达真实业务顺序。此时再用 UUID 兜底排序，就会出现偶发乱序。

## 解决思路

对话消息顺序是业务语义，不应该依赖数据库时间戳或随机主键推断。更合理的设计是为每个 thread 引入显式的消息序号。

核心原则：

- 同一 `thread_id` 内，消息顺序由业务字段 `sequence` 决定。
- 写入消息时分配递增 `sequence`。
- 读取历史、构造 LLM 上下文、生成会话列表摘要时统一使用 `sequence` 排序。
- 时间戳继续用于展示、活跃时间和审计，但不再承担消息主排序职责。

## 解决方法

本次修复新增了 `conversation_messages.sequence` 字段。

主要改动：

- `src/models/runtime.py`
  - `ConversationMessage` 增加 `sequence: int`。
- `src/api/chat.py`
  - 新增 `_next_message_sequence()`，基于当前 thread 内最大 `sequence` 生成下一个序号。
  - `/api/chat/send` 写入 user message 时分配序号，assistant message 使用下一位序号。
  - `/api/chat/stream` 写入 user message 时分配序号，流式完成后持久化 assistant message 时重新读取最新序号。
  - `_conversation_history()` 改为按 `sequence` 排序，确保 LLM 上下文顺序稳定。
- `src/api/conversations.py`
  - 历史消息接口改为按 `sequence ASC` 返回。
  - 响应体暴露 `sequence`，方便前端和调试定位。
- `alembic/versions/8d3e4f5a6b7c_add_conversation_message_sequence.py`
  - 为旧数据回填 `sequence`。
  - 增加 `(thread_id, sequence)` 唯一约束。
  - 增加 `(learner_id, thread_id, sequence)` 查询索引。

## 迁移策略

旧消息没有 `sequence`，迁移时使用窗口函数回填：

```sql
row_number() OVER (
  PARTITION BY thread_id
  ORDER BY created_at ASC, id ASC
)
```

这个回填只能基于旧数据已有信息恢复一个稳定顺序，无法百分百还原所有历史真实发生顺序。但迁移后，新写入的数据会由业务序号保证稳定。

部署时需要执行：

```bash
.venv/bin/alembic upgrade head
```

然后重启后端服务，让新的模型字段和排序逻辑生效。

## 验证

本次补充了回归测试：

- 构造两条 `created_at` 完全相同、UUID 顺序相反的消息。
- 验证历史接口仍按 `sequence=1,2` 返回。
- 验证迁移文件包含回填逻辑、唯一约束和查询索引。

已通过验证：

```bash
.venv/bin/python -m pytest tests/ -v
.venv/bin/ruff check src tests alembic --select F --exclude '**/__pycache__'
cd binnagent-frontend && npm run lint
cd binnagent-frontend && npm run build
```

结果：

- 后端测试：113 passed
- Ruff：All checks passed
- 前端 lint：通过
- 前端 build：通过

## 思考

Agent 系统里的 Memory 不是简单的日志存储。它至少有三层要求：

1. 可追溯：用户能看到自己过去说过什么。
2. 可复用：LLM 能按正确顺序拿到上下文。
3. 可演化：摘要、画像、错因和学习计划能基于可靠历史生成。

如果底层消息顺序不稳定，Memory 会从“增强能力”变成“污染源”。这次问题提醒我们：凡是具备业务语义的顺序、状态和归属关系，都应显式建模，而不是从技术字段中推断。

后续可以继续增强：

- 在高并发同 thread 写入时引入行级锁或数据库序列，避免并发请求同时拿到相同 `sequence`。
- 将 message persistence 抽成 `ConversationStore`，统一非流式、流式、工具调用和未来多 Agent 子任务的落库逻辑。
- 为 SSE 中断、用户取消、模型失败分别设计消息状态，区分 complete / interrupted / failed。
- 在前端按 `sequence` 做二次稳定排序，作为展示层防御。

本次修复的核心判断是：技术实现必须服务于学习陪伴场景。英语学习 Agent 的对话历史既是用户信任的证据，也是个性化教学的输入，所以消息顺序属于核心数据一致性问题，不能只当成 UI 小瑕疵处理。
