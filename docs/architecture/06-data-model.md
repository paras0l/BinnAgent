# 06. 数据模型方案

## 1. 模块目标

数据模型需要同时服务三类需求：

- 学习业务：课程、任务、题目、复习、成绩。
- Agent Runtime：thread、run、event、checkpoint。
- Memory：长期学习画像、错词错因、错误模式。
- Model Provider：本地 Ollama、模型调用记录、fallback 轨迹。
- Tool Provider：词典 provider、有道词典接入配置引用、MCP 工具调用记录。

## 2. 存储选型

### 2.1 PostgreSQL — 核心数据库

选择 PostgreSQL 作为主数据库的理由：

| 需求 | PostgreSQL 优势 | 替代方案的问题 |
|------|----------------|---------------|
| 半结构化数据（词汇释义、错因证据、模考诊断） | 原生 JSONB，支持索引和查询 | MySQL JSON 性能差；拆表会增加维护成本 |
| 向量检索（材料相似、错题匹配） | pgvector 扩展，一体化 | 单独引入 Qdrant/Milvus 增加运维复杂度 |
| 事务一致性（session → task → vocabulary → review） | ACID 保证，单库事务 | MySQL + Redis + 向量库跨系统一致性难保证 |
| Agent State 持久化 | LangGraph Checkpointer 原生支持 PostgreSQL | SQLite 不支持并发写入，不适合生产 |
| 多租户数据隔离 | Row Level Security | 需要在应用层实现，容易出错 |
| 复杂查询（复习调度、错题统计） | 索引能力强，支持 `(learner_id, next_review_at)` 排序过滤 | NoSQL 不擅长复杂聚合查询 |

**一句话总结：一个 PostgreSQL 同时搞定 JSONB、向量检索、事务、Agent state，运维复杂度最低。**

MVP 阶段可用 SQLite 开发（SQLAlchemy 兼容），生产环境切 PostgreSQL 只需改连接串。

### 2.2 Redis — 缓存层

- 短期缓存：会话状态、限流计数器。
- 异步任务状态：生成周报、批量评估等耗时任务的进度追踪。
- 非必需：MVP 阶段可跳过，用内存字典替代。

### 2.3 Object Storage — 文件存储

- 音频文件（口语音频、听力材料）。
- 作文附件和原始材料文件。
- MVP 阶段不涉及，后续接入。

### 2.4 存储选型总结

```text
PostgreSQL (主)  ─── 核心业务 + JSONB + pgvector 向量 + LangGraph state
Redis (可选)     ─── 缓存 + 限流 + 异步任务
Object Storage   ─── 大文件（音频、附件）— 后续接入
```

### 2.5 部署方式

本地开发和生产部署均通过 Docker Compose 管理：

```bash
# 一键启动所有依赖
docker compose up -d

# 查看服务状态
docker compose ps
```

详见 README.md 中的 Docker 部署章节。

## 3. 核心表

### 3.1 learners

```text
id
tenant_id
nickname
email
created_at
updated_at
```

### 3.2 learner_profiles

```text
id
learner_id
target_exam
target_score
exam_date
current_level
daily_time_budget_minutes
preferred_study_time
interest_topics jsonb
weak_skills jsonb
created_at
updated_at
```

### 3.3 learning_sessions

```text
id
learner_id
thread_id
run_id
session_type
active_skill
today_goal
status
started_at
completed_at
summary
```

### 3.4 learning_tasks

```text
id
learner_id
session_id
task_type
skill
title
difficulty
estimated_minutes
status
input_ref
output_ref
feedback_ref
created_at
completed_at
```

### 3.5 vocabulary_items

```text
id
learner_id
word
phonetic
level
meanings jsonb
collocations jsonb
examples jsonb
source_ref
status
confidence
review_count
last_reviewed_at
next_review_at
created_at
updated_at
```

索引：

```text
(learner_id, word)
(learner_id, next_review_at)
(learner_id, status)
```

### 3.6 review_schedules

```text
id
learner_id
item_type
item_id
scheduled_at
completed_at
result
response_time_ms
confidence_before
confidence_after
recommended_next_drill
```

### 3.7 error_patterns

```text
id
learner_id
skill
pattern
description
frequency
severity
evidence_refs jsonb
recommended_drill
last_seen_at
created_at
updated_at
```

索引：

```text
(learner_id, skill)
(learner_id, pattern)
(learner_id, severity)
```

### 3.8 materials

```text
id
material_type
exam_type
title
content_ref
difficulty
word_count
audio_ref
tags jsonb
source
metadata jsonb
embedding vector
created_at
```

### 3.9 question_attempts

```text
id
learner_id
session_id
question_id
exam_type
section
question_type
answer
is_correct
time_spent_seconds
mistake_reason
feedback jsonb
created_at
```

### 3.10 writing_submissions

```text
id
learner_id
session_id
prompt
draft_text
revised_text
score
max_score
feedback_json
error_pattern_ids jsonb
created_at
updated_at
```

### 3.11 speaking_submissions

```text
id
learner_id
session_id
prompt
audio_ref
transcript
feedback_json
error_pattern_ids jsonb
created_at
```

### 3.12 exam_mock_results

```text
id
learner_id
exam_type
total_score
section_scores jsonb
section_time jsonb
diagnosis jsonb
created_at
```

## 4. Agent Runtime 表

### 4.1 agent_threads

```text
id
learner_id
status
metadata jsonb
created_at
updated_at
```

### 4.2 agent_runs

```text
id
thread_id
session_id
graph_name
status
model_usage jsonb
cost
latency_ms
started_at
completed_at
error
```

`model_usage` 至少记录：

```json
{
  "default_provider": "ollama",
  "models": [
    {
      "provider": "ollama",
      "model": "gemma4:e2b",
      "task_type": "writing_feedback",
      "latency_ms": 1830,
      "prompt_chars": 2400,
      "completion_chars": 900,
      "fallback": false
    }
  ]
}
```

### 4.3 agent_events

```text
id
run_id
event_type
node_name
payload jsonb
created_at
```

### 4.4 tool_calls

```text
id
run_id
node_name
tool_name
input_summary
output_summary
status
latency_ms
error
created_at
```

## 5. Model Provider 表

### 5.1 model_call_logs

```text
id
run_id
node_name
task_type
provider
model
local_only
prompt_chars
completion_chars
latency_ms
status
retry_count
fallback_from
fallback_reason
error
created_at
```

用途：

- 观察 Ollama 本地模型延迟。
- 分析哪些节点最耗时。
- 追踪 fallback 是否发生。
- 为模型替换和 prompt 优化提供依据。

### 5.2 model_provider_configs

```text
id
provider
enabled
base_url
default_chat_model
default_utility_model
default_embedding_model
fallback_enabled
metadata jsonb
created_at
updated_at
```

注意：

- API key 不入库明文。
- 有密钥需求的云 provider 只保存环境变量名或 secret 引用。
- Ollama 默认配置可由环境变量覆盖。

## 6. Tool Provider 表

### 6.1 tool_provider_configs

```text
id
tool_type
provider
enabled
priority
config_ref
metadata jsonb
created_at
updated_at
```

示例：

```json
{
  "tool_type": "dictionary",
  "provider": "youdao",
  "enabled": false,
  "priority": 20,
  "config_ref": "env:YOUDAO_APP_KEY,YOUDAO_APP_SECRET"
}
```

有道词典相关密钥必须通过环境变量或 secret manager 管理。

## 7. Memory 存储关系

长期 Memory 可以同时落：

- 业务表：便于查询和产品展示。
- LangGraph store：便于 Agent 读取。
- vector index：便于相似检索。

例如一个错词：

- `vocabulary_items` 存结构化状态。
- store namespace 存 Agent 可读 JSON。
- embedding index 存例句和上下文。

## 8. 数据生命周期

### 6.1 热数据

- 最近 30 天 session。
- 当前复习队列。
- 高频错因。

### 6.2 温数据

- 历史练习记录。
- 历史写作。
- 历史模考。

### 6.3 可归档数据

- 原始 Agent events。
- 老旧工具调用详情。
- 低价值临时材料。

## 9. 隐私与合规

需要支持：

- 用户删除学习记忆。
- 用户导出词汇和错题。
- 音频文件过期清理。
- 敏感字段脱敏。
- 多租户数据隔离。

禁止：

- 跨用户读取 Memory。
- 将用户作文或音频默认用于公共训练集。
- 把情绪推断作为强事实存储。
