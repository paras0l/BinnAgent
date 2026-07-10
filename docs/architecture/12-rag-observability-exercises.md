# 12. 教材 RAG、Langfuse 与练习题

## 1. 教材 PDF RAG

教材上传与结构化知识点流程保持不变，ingest 阶段新增 RAG 索引：

1. 使用 `pypdf` 提取每页文本。
2. 按 900 字符、150 字符重叠切块。
3. 根据单元起始页把 chunk 关联到 `curriculum_node_id`。
4. 调用 Ollama `/api/embed` 和 `nomic-embed-text:latest` 生成 768 维向量。
5. 写入 PostgreSQL `knowledge_chunks`，使用 pgvector HNSW cosine 索引。

向量服务不可用时仍保存文本块，检索自动降级为关键词匹配。重新 ingest 会删除该
教材旧 chunk 并重建索引。

检索接口：

```text
GET /api/knowledge/search
  ?learner_id=<uuid>
  &query=<question>
  &source_id=<optional uuid>
  &curriculum_node_id=<optional uuid>
  &limit=5
```

## 2. Langfuse 可观测性

Langfuse 是可选能力，默认关闭。启用配置：

```bash
BINN_LANGFUSE_ENABLED=true
BINN_LANGFUSE_PUBLIC_KEY=pk-lf-...
BINN_LANGFUSE_SECRET_KEY=sk-lf-...
BINN_LANGFUSE_BASE_URL=http://localhost:3100
BINN_LANGFUSE_DOCKER_BASE_URL=http://host.docker.internal:3100
BINN_LANGFUSE_ENVIRONMENT=development
```

当前记录 Ollama 对话、流式对话、embedding、教材索引和教材检索。模型 observation
包含模型名、任务类型、延迟、输入输出 token；教材 observation 包含 source、chunk
数量、检索模式和召回数量。每日课程 LangGraph 使用 Langfuse CallbackHandler，
可以查看 graph node、LLM 调用和父子 observation。

本项目默认只指向本机 Langfuse，不使用 Langfuse Cloud。教材正文和对话会进入本地
观测数据库，应仍然限制本机账号和端口访问。

### 2.1 本地启停

项目使用官方 Langfuse v3 Docker Compose，并自动把 UI 改到 3100、Postgres 改到
15432、Redis 改到 16379，避免与 BinnAgent 冲突：

```bash
./scripts/langfuse.sh setup
./scripts/langfuse.sh start
./scripts/langfuse.sh status
./scripts/langfuse.sh logs
./scripts/langfuse.sh stop
```

`setup` 会把官方仓库克隆到已忽略的 `var/langfuse/`，生成随机密钥及本地管理员，
并把项目 API Key 同步到 BinnAgent `.env`。`start` 会启用 tracing，`stop` 会保留
traces 并关闭 tracing。查看本地管理员账号：

```bash
./scripts/langfuse.sh credentials
```

完全删除本地 trace 数据必须显式确认：

```bash
./scripts/langfuse.sh reset --yes
```

### 2.2 M2 / 16GB 资源策略

- Docker Desktop 建议至少 4 CPU、8GB memory、50GB disk，并开启 Resource Saver。
- 日常 Agent 调试时启动 Langfuse。
- 本地模型压力测试或长时间生成时停止 Langfuse。
- `gemma4:e2b` 与 Langfuse 同时运行时避免再启动其他大型模型。

## 3. 教材练习题

`exercise_questions` 保存题干、选项、答案、解析、题型和关联知识点；
`metadata` 保存 interaction、scenario、rubric、source evidence 和 estimated seconds。
`exercise_attempts` 保存学习者答案、正确性、耗时和课程 session。

单元练习使用 PostgreSQL 持久化题池和独立 `exercise-worker`。API 不同步等待 LLM；有题时立即返回当前最佳题并按需入队补池，完全无题时返回 `202 Accepted`，前端轮询题池状态。详细可靠性、容量和评分设计见
[异步练习题池与质量排序](./exercise-generation-pool.md)。

- `choice_context`：带语境的选择题。
- `fill_blank`：填空题。
- `dialogue_complete`：补全对话。
- `error_fix`：找错并修改。

生成链路已经升级为：

```text
knowledge points
  -> deterministic coverage plan
  -> exercise.unit_candidates (LLM)
  -> schema + deterministic quality gate
  -> exercise.unit_review (independent LLM review)
  -> six-dimension score + hard thresholds
  -> published unit pool
  -> mastery-aware selection
```

生成前会从单元知识点中优先选择 sentence pattern、grammar、phrase 和核心 vocabulary，
避免大量按插入顺序排列的词汇项淹没核心句式。确定性 coverage plan 约束知识点、题型、认知层级和难度覆盖。直接识记题不超过 25%，
`production` / `transfer` 至少占 50%，并要求至少 4 种题型和 50% 主动输入题。
候选题必须通过以下门禁：

- knowledge point ID 必须来自当前单元；
- 题干不得包含“目标：使用……”等答案泄露提示；
- 选择题必须有 4 个唯一同类选项，且正确答案恰好出现一次；
- 填空和对话题必须有明确空格，文本题不能混入选择项；
- 题干、答案、解释、scenario 和 rubric 必须完整；
- 整套题不能重复，认知层级和题型比例必须达标；
- 独立 reviewer 再检查语境连贯、答案唯一、干扰项质量、知识点对齐和难度合理性。

候选生成或审题失败由持久化任务有限重试。仍失败时只回退到已存在的教材原题或人工题（题量可少于默认值），旧的
固定模板不会再作为 learner-facing fallback。旧模板生成题只有在
新题池成功通过门禁后才会归档，避免失败时破坏已有可用数据。

题池默认低于 16 题触发补充，目标容量为 24，一次返回最多 8 题。Reviewer 对知识对齐、可作答性、自然度、干扰项、解析和创新度评分，前两项低于 0.75 直接拒绝。返回给学习者的题目由
质量分和 `LearnerKnowledgeState.mastery_score` 共同决定，同时优先保证题型和知识点多样性。
生成和审题都通过 `PromptExecutor`，使用独立 schema、版本化模板、PromptExecutionRecord
和离线 eval set。

```text
POST /api/learners/{learner_id}/knowledge-base/units/{node_id}/exercises
GET  /api/learners/{learner_id}/knowledge-base/units/{node_id}/exercise-pool
POST /api/learners/{learner_id}/knowledge-base/exercises/{question_id}/attempts
```

提交答案后返回 score、passed、feedback、hint、can_retry、error_type 和
next_review_signal。主观输入使用 rubric 判分，不只做 exact match。答题结果写入
`knowledge_learning_events`，事件类型为 `exercise_answered`，payload 包含
question_type、score、error_type、hint_used、attempt_index 和 next_review_signal，便于后续掌握度与复习策略消费。

## 4. 部署

```bash
ollama pull nomic-embed-text:latest
alembic upgrade head
```

如果更换 embedding 模型且维度不是 768，需要同步修改数据库向量列维度并重建
`knowledge_chunks`。
