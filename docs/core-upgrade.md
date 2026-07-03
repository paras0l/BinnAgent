下面这些可以**直接复制给 Codex**。建议一次只给一个任务，按顺序执行，不要一次全塞进去。

---

# 通用约束 Prompt

每个任务前都可以先贴这一段，保证 Codex 不乱改。

```text
你正在维护我的项目 BinnAgent，这是一个基于 FastAPI、LangGraph、PostgreSQL/pgvector、SQLAlchemy、Ollama、Langfuse、React/TypeScript 的长期记忆型英语学习 Agent 系统。

本次任务目标是增强系统的 Agent Runtime / Harness 工程能力，而不是新增孤立业务功能。

请严格遵守以下约束：

1. 先阅读现有代码结构，再修改代码。
2. 不要大规模重构已有 API，不要破坏现有功能。
3. 优先复用现有模型、service、router、test 风格。
4. 后端新增代码尽量放在清晰的新模块中，例如：
   - src/runtime/
   - src/evidence/
   - src/mastery/
   - src/recommendation/
   - src/verification/
   - src/tools/
5. 所有新增核心类型优先使用 Pydantic model 定义输入输出结构。
6. 涉及数据库时使用现有 SQLAlchemy/Alembic 风格。
7. 每个任务都必须补充最小可运行测试。
8. 修改完成后运行：
   - ruff check .
   - pytest
   - 如涉及前端，运行 npm run lint 和 npm run build
9. 输出最终总结时说明：
   - 修改了哪些文件
   - 新增了哪些核心抽象
   - 哪些测试覆盖了新逻辑
   - 是否存在未完成项或技术债
```

---

# Task 1：新增 Agent Runtime 基础抽象

```text
请为 BinnAgent 新增 Agent Runtime 基础抽象，目标是把教材学习、练习、词汇、写作、Chat、Memory、RAG 等模块统一挂到一次可追踪的 AgentEpisode 上。

请完成以下内容：

一、新增模块

创建：

- src/runtime/
- src/runtime/task_spec.py
- src/runtime/events.py
- src/runtime/episode.py
- src/runtime/schemas.py

二、定义 TaskSpec

在 src/runtime/task_spec.py 中定义 Pydantic model：

1. TaskTarget
字段：
- target_type: str
- target_id: str | None
- label: str | None
- metadata: dict = {}

2. SuccessCriteria
字段：
- min_accuracy: float | None
- max_hint_count: int | None
- requires_explanation: bool = False
- required_outputs: list[str] = []

3. VerificationPolicy
字段：
- required_checks: list[str] = []
- allow_llm_judge: bool = False
- require_evidence: bool = True

4. TaskSpec
字段：
- task_id: str
- task_type: str
- source: str
  可选值不必强制 enum，但要支持 textbook_guided / recommendation / explore / chat_triggered / review
- objective: str
- target: TaskTarget
- difficulty: str | None
- required_inputs: list[str] = []
- expected_output: dict = {}
- allowed_tools: list[str] = []
- success_criteria: SuccessCriteria
- verification_policy: VerificationPolicy
- metadata: dict = {}

三、定义 LearningEvent

在 src/runtime/events.py 中定义：

LearningEventCreate:
- episode_id: str
- learner_id: str
- event_type: str
- source_module: str
- target_type: str | None
- target_id: str | None
- payload: dict = {}

LearningEventView:
- id: str
- episode_id: str
- learner_id: str
- event_type: str
- source_module: str
- target_type: str | None
- target_id: str | None
- payload: dict
- occurred_at: datetime

四、定义数据库模型

请根据项目现有 SQLAlchemy 风格新增数据库表：

1. AgentEpisode

表名：agent_episodes

字段建议：
- id: UUID primary key
- learner_id: UUID / String，保持项目现有 learner_id 类型风格
- source: str
- entrypoint: str
- status: str
  created / running / waiting_user / completed / failed / cancelled
- task_spec: JSON
- context_snapshot: JSON nullable
- memory_context_ids: JSON nullable
- rag_chunk_ids: JSON nullable
- tool_call_ids: JSON nullable
- verification_report: JSON nullable
- failure_type: str nullable
- error_message: str nullable
- started_at: datetime
- completed_at: datetime nullable
- created_at / updated_at，如果项目已有基类则复用

2. LearningEvent

表名：learning_events

字段：
- id
- episode_id
- learner_id
- event_type
- source_module
- target_type nullable
- target_id nullable
- payload JSON
- occurred_at

3. ToolCallRecord

表名：tool_call_records

字段：
- id
- episode_id
- tool_name
- input_hash
- output_hash nullable
- latency_ms nullable
- status
- error nullable
- metadata JSON
- created_at

五、实现 EpisodeRuntime service

在 src/runtime/episode.py 中实现：

class EpisodeRuntime:
    async def create_episode(...)
    async def append_event(...)
    async def record_tool_call(...)
    async def complete_episode(...)
    async def fail_episode(...)
    async def get_episode_trace(...)

要求：
- create_episode 接收 learner_id、source、entrypoint、TaskSpec，创建 AgentEpisode。
- append_event 写 LearningEvent。
- record_tool_call 写 ToolCallRecord，并把 tool_call id 追加到 episode.tool_call_ids。
- complete_episode 标记 completed，并允许写 verification_report。
- fail_episode 标记 failed，并记录 failure_type、error_message。
- get_episode_trace 返回 episode、events、tool_calls。

六、API

新增一个只读调试 API：

GET /api/runtime/episodes/{episode_id}

返回：
- episode
- events
- tool_calls

不要暴露数据库内部敏感字段。

七、测试

新增测试，覆盖：

1. 可以创建 episode。
2. 可以 append event。
3. 可以 record tool call。
4. 可以 complete episode。
5. get_episode_trace 能返回完整链路。

八、验收标准

完成后我应该能在后端创建一次 AgentEpisode，并看到：
- TaskSpec
- LearningEvent 列表
- ToolCallRecord 列表
- episode status 从 created/running 到 completed
```

---

# Task 2：把 Knowledge Exercise 接入 AgentEpisode

```text
请把 BinnAgent 现有 Knowledge Exercise / 教材练习提交流程接入 AgentEpisode Runtime。

目标：一次教材知识点练习不再只是保存 ExerciseAttempt，而是形成完整 episode trace：

TaskSpec
→ AgentEpisode
→ RAG / Exercise / Attempt / Grade / Mastery / Memory / Review
→ VerificationReport
→ Episode completed

请完成以下内容：

一、阅读现有代码

请先阅读以下相关模块：

- src/api/knowledge.py
- src/models/knowledge.py
- src/exercises/attempt_service.py
- src/memory/writer.py
- src/knowledge/rag.py
- src/runtime/ 目录，如果不存在说明先执行 Task 1

二、接入点选择

优先接入现有的知识点练习提交 API，例如 submit_exercise_attempt 或 record_knowledge_attempt 相关流程。

不要破坏现有 API 返回格式。可以在返回中新增 episode_id、episode_trace_url、verification_report 等可选字段。

三、创建 TaskSpec

当用户开始或提交一次知识点练习时，创建 TaskSpec：

task_type: "practice_knowledge_point"
source: "textbook_guided"
objective: 根据 question / knowledge_point 生成简短 objective
target:
  target_type: "knowledge_point" 或 "curriculum_node"
  target_id: 对应 knowledge_point_id / curriculum_node_id
allowed_tools:
  - exercise.grade
  - mastery.update
  - memory.write
  - review.schedule
  - verification.verify_episode

success_criteria:
  - min_accuracy: 1.0，单题可以用 correct 表示
  - requires_explanation: true

verification_policy:
  - required_checks:
    - exercise_attempt_saved
    - grading_result_exists
    - memory_event_written
    - mastery_update_valid
  - require_evidence: true

四、写入 LearningEvent

在流程中追加事件：

- episode_started
- exercise_answered
- exercise_graded
- mastery_updated，如果当前流程已有 mastery/state 更新
- memory_written，如果当前流程写入 MemoryEvent
- review_scheduled，如果当前流程安排复习
- episode_completed

每个事件 payload 中尽量包含：
- question_id
- attempt_id
- correct
- score
- error_type
- knowledge_point_id
- memory_event_id
- review_schedule_id
- mastery_before / mastery_after，如果可以拿到

五、记录 ToolCallRecord

不要强行把所有函数都改成 tool。先在关键节点记录 tool call record：

- exercise.grade
- memory.write
- review.schedule
- mastery.update，如果存在
- verification.verify_episode

input_hash / output_hash 可以先使用稳定 JSON hash 工具函数生成。如果项目已有 hash 方法，复用；否则新增一个小工具函数。

六、生成最小 VerificationReport

如果项目还没有 VerificationReport 模块，请在 src/verification/report.py 中新增最小实现：

verify_knowledge_exercise_episode(...)

检查：
1. exercise attempt 是否保存成功
2. grading result 是否存在
3. correct / score 字段是否合法
4. 如果 configured 为 should_create_memory_evidence，则 memory event 是否写入
5. mastery score 如果发生变化，是否在 0-1 范围内
6. episode events 是否包含 exercise_answered 和 exercise_graded

返回 JSON 结构：
- status: passed / failed
- checks: list
- failed_reason: str | None

七、返回结果

在知识点练习提交 API 的 response 中新增：
- episode_id
- verification_status
- runtime_events_count

保持向后兼容。

八、测试

新增或修改测试，覆盖：

1. 提交一次知识点练习后创建 AgentEpisode。
2. episode 中包含 exercise_answered、exercise_graded。
3. 如果写 memory，episode 中包含 memory_written。
4. API response 包含 episode_id。
5. VerificationReport status 为 passed。
6. 原有提交练习功能不回退。

九、验收标准

我应该可以通过一次教材练习提交，查询：

GET /api/runtime/episodes/{episode_id}

看到完整 trace：
- task_spec
- exercise_answered event
- exercise_graded event
- memory_written event，若存在
- tool_call_records
- verification_report
- completed status
```

---

# Task 3：新增 EvidenceRef / EvidenceBundle

```text
请为 BinnAgent 新增统一 EvidenceRef 抽象，用来连接 RAG chunk、ExerciseAttempt、MemoryEvent、KnowledgePoint、VocabularyAttempt 等证据。

目标：让推荐、反馈、记忆更新、掌握度更新都能携带可追溯证据，形成 Evidence-grounded Agent Runtime。

一、新增模块

创建：

- src/evidence/
- src/evidence/types.py
- src/evidence/resolver.py

二、定义 EvidenceRef

在 src/evidence/types.py 中定义 Pydantic models：

EvidenceRef:
- evidence_type: str
  支持但不强制 enum：
  memory_event / exercise_attempt / rag_chunk / knowledge_point / vocabulary_attempt / writing_attempt / review_schedule / learning_event
- evidence_id: str
- confidence: float = 1.0
- reason: str | None = None
- used_by: str | None = None
- metadata: dict = {}

EvidenceBundle:
- refs: list[EvidenceRef]
- summary: str | None = None
- confidence: float = 1.0

EvidenceResolution:
- ref: EvidenceRef
- found: bool
- title: str | None
- content: str | None
- source: str | None
- metadata: dict = {}

三、EvidenceResolver

在 src/evidence/resolver.py 中实现 EvidenceResolver。

功能：
- resolve_ref(ref: EvidenceRef)
- resolve_bundle(bundle: EvidenceBundle)

它应该能根据 evidence_type 查询现有数据库对象。

第一阶段至少支持：
- knowledge_point
- exercise_attempt
- memory_event
- rag_chunk
- learning_event

如果某种 evidence_type 暂时找不到模型，可以返回 found=false，不要抛异常。

四、工具函数

新增帮助函数：

- evidence_from_attempt(attempt)
- evidence_from_memory_event(memory_event)
- evidence_from_rag_chunk(chunk)
- evidence_from_knowledge_point(kp)
- evidence_from_learning_event(event)

五、接入 Runtime

把 AgentEpisode / LearningEvent 的 payload 设计中支持 evidence_refs。

至少保证：
- exercise_graded event payload 中可以包含 evidence_refs
- memory_written event payload 中可以包含 evidence_refs
- verification_report check 中可以包含 evidence_refs

六、API

新增只读 API：

POST /api/evidence/resolve

body:
- refs: list[EvidenceRef]

返回：
- resolutions: list[EvidenceResolution]

七、测试

测试至少覆盖：

1. EvidenceRef Pydantic 校验。
2. knowledge_point evidence 可以 resolve。
3. exercise_attempt evidence 可以 resolve。
4. 不存在的 evidence_id 返回 found=false。
5. LearningEvent payload 可以带 evidence_refs。

八、验收标准

一次练习提交后，我应该能在 episode trace 里看到 evidence_refs，并且可以调用 /api/evidence/resolve 把 evidence_id 解析成人类可读信息。
```

---

# Task 4：抽出 MasteryEngine

```text
请把 BinnAgent 中知识掌握度、词汇掌握度、写作句式掌握度的更新逻辑逐步收敛到统一 MasteryEngine。

目标：不要让每个 API 各自散落更新 mastery，而是通过统一 service 输出 MasteryUpdateResult，并把它作为 Recommendation、Review、Memory 的输入。

一、阅读现有代码

请先阅读：
- src/models/knowledge.py
- src/models/vocabulary.py
- src/api/knowledge.py
- src/exercises/attempt_service.py
- src/memory/curator.py
- 和任何已有 mastery / review 相关 service

二、新增模块

创建：

- src/mastery/
- src/mastery/types.py
- src/mastery/engine.py

三、定义类型

在 src/mastery/types.py 中定义：

AttemptSignal:
- learner_id: str
- target_type: str
- target_id: str
- correct: bool
- score: float | None
- error_type: str | None
- hint_count: int = 0
- retry_count: int = 0
- response_time_ms: int | None
- source: str
- evidence_refs: list[EvidenceRef] = []
- metadata: dict = {}

MasteryUpdateResult:
- learner_id: str
- target_type: str
- target_id: str
- previous_score: float | None
- new_score: float
- previous_confidence: float | None
- new_confidence: float
- mastery_delta: float
- weakness_tags: list[str] = []
- forgetting_risk: float | None
- next_review_at: datetime | None
- status: str | None
- evidence_refs: list[EvidenceRef] = []
- metadata: dict = {}

四、实现 MasteryEngine

在 src/mastery/engine.py 中实现：

class MasteryEngine:
    async def update_from_attempt(signal: AttemptSignal) -> MasteryUpdateResult

第一阶段至少支持：

1. target_type = "knowledge_point" 或 "curriculum_node"
   更新 LearnerKnowledgeState。

2. target_type = "vocabulary_item" 或 "vocabulary"
   如果现有 vocabulary mastery vector 更新逻辑比较复杂，可以先包装已有逻辑；不要破坏原功能。

3. target_type = "writing_phrase"
   如果已有 WritingPhraseMastery，则支持最小更新。

五、更新算法

先使用可解释规则，不引入复杂 ML。

建议：
- correct=true：mastery_score 小幅上升
- correct=false：mastery_score 下降或保持低位
- hint_count 越高，上升越小
- retry_count 越高，上升越小
- confidence 根据 exposure_count、correct_count、最近答题更新
- next_review_at 根据 mastery_score 和 correct 决定

保证 mastery_score 和 confidence 始终在 0-1。

六、接入 Knowledge Exercise

把知识点练习提交流程中的 mastery 更新逻辑迁移或包装到 MasteryEngine。

要求：
- 保持原有行为尽量不变。
- 允许 API 返回 mastery_update。
- 在 AgentEpisode 中追加 mastery_updated event。
- VerificationReport 检查 mastery_update 是否合法。

七、测试

新增测试：

1. correct attempt 会提升 mastery_score。
2. incorrect attempt 会产生 weakness tag 或降低 mastery。
3. hint_count 高时 mastery 提升更少。
4. mastery_score 永远在 0-1。
5. knowledge exercise 提交后会产生 MasteryUpdateResult。
6. episode trace 中包含 mastery_updated event。

八、验收标准

提交一次知识点练习后，系统应通过 MasteryEngine 更新 LearnerKnowledgeState，并返回可追踪 MasteryUpdateResult。
```

---

# Task 5：新增 RecommendationEngine 规则版

```text
请为 BinnAgent 新增规则版 RecommendationEngine，用于基于教材进度、掌握度、错因记忆、复习到期项和用户偏好生成 Daily LearningPlan / Next Best Learning Action。

目标：把推荐逻辑从 Memory、Knowledge、Daily Lesson 等模块中逐步收敛出来，形成统一推荐入口。

一、新增模块

创建：

- src/recommendation/
- src/recommendation/types.py
- src/recommendation/engine.py

二、定义类型

RecommendationInput:
- learner_id: str
- current_curriculum_node_id: str | None
- time_budget_minutes: int | None = None
- mode_hint: str | None = None
  textbook_guided / weakness_repair / review / explore
- metadata: dict = {}

RecommendationTask:
- task_spec: TaskSpec
- priority_score: float
- reason: str
- evidence_refs: list[EvidenceRef] = []
- estimated_minutes: int | None = None

RecommendationPlan:
- plan_id: str
- learner_id: str
- mode: str
- reason: str
- confidence: float
- tasks: list[RecommendationTask]
- evidence_refs: list[EvidenceRef] = []
- generated_at: datetime

三、实现 RecommendationEngine

在 src/recommendation/engine.py 中实现：

class RecommendationEngine:
    async def build_daily_plan(input: RecommendationInput) -> RecommendationPlan
    async def recommend_next_action(input: RecommendationInput) -> RecommendationTask | None
    async def rank_weak_points(...)
    async def rank_due_reviews(...)
    async def explain_recommendation(...)

四、规则优先级

先用可解释规则：

priority_score =
- weakness_score: 0.35
- forgetting_risk: 0.25
- curriculum_priority: 0.20
- recent_error_frequency: 0.10
- user_preference_match: 0.10

如果某些输入暂时没有，就用 0 或默认值，不要报错。

五、数据来源

第一阶段读取：

- LearnerKnowledgeState
- ReviewSchedule，如果存在
- MemoryRetriever.for_daily_plan 或类似方法
- recent ExerciseAttempt
- current curriculum node / knowledge point

不要求一次接入所有来源，但代码结构要方便扩展。

六、输出 TaskSpec

RecommendationEngine 输出的每个任务都必须包含 TaskSpec。

示例 task_type：
- learn_knowledge_point
- practice_knowledge_point
- review_due_item
- repair_weakness
- practice_vocabulary
- practice_writing_phrase

七、API

新增：

GET /api/recommendations/daily-plan?learner_id=...

返回 RecommendationPlan。

如果项目已有 learner 路由风格，请遵循现有风格。

八、接入前端或现有 API

如果已有 Knowledge overview / Memory Center 返回 recommendation_reason，可以先不大改前端，但至少让后端有统一 daily-plan API。

九、测试

新增测试：

1. learner 没有学习数据时，返回 textbook_guided 模式或空 plan，不报错。
2. 有低 mastery 的 knowledge state 时，推荐 repair_weakness。
3. 有 due review 时，推荐 review_due_item。
4. RecommendationTask 中包含 TaskSpec。
5. evidence_refs 可以解析。
6. priority_score 排序稳定。

十、验收标准

我可以调用 daily-plan API，得到：
- 推荐任务列表
- 每个任务的 TaskSpec
- priority_score
- reason
- evidence_refs
```

---

# Task 6：让 Daily Lesson 改为 Orchestrator 调度

```text
请把现有 Daily Lesson / LangGraph 学习流程逐步改造成由 RecommendationEngine + TaskSpec + AgentEpisode 驱动。

目标：Daily Lesson 不再只是线性 graph，而是从 RecommendationPlan 中选择 TaskSpec，创建 AgentEpisode，然后执行任务并记录 trace。

一、阅读现有代码

请阅读：
- src/graph/main_graph.py
- src/graph/state.py
- src/graph/nodes/
- src/recommendation/
- src/runtime/
- src/mastery/
- src/memory/

二、新增 LearningOrchestrator

创建：

- src/learning/
- src/learning/orchestrator.py
- src/learning/types.py

定义：

LearningPlanRequest:
- learner_id: str
- current_curriculum_node_id: str | None
- time_budget_minutes: int | None
- mode_hint: str | None
- metadata: dict = {}

LearningPlanResult:
- recommendation_plan: RecommendationPlan
- selected_task: TaskSpec | None
- episode_id: str | None
- status: str
- reason: str

实现：

class LearningOrchestrator:
    async def build_learning_plan(...)
    async def start_task(...)
    async def resume_task(...)
    async def complete_task(...)

三、start_task 行为

start_task 应该：
1. 接收 TaskSpec。
2. 创建 AgentEpisode。
3. append episode_started event。
4. 根据 task_type 分发到对应 handler。
5. 第一阶段可以只支持 practice_knowledge_point / learn_knowledge_point。
6. 不支持的 task_type 返回明确错误，不要静默失败。

四、Daily Lesson 接入

修改现有 daily lesson API 或 graph 节点，使其：

1. 先调用 RecommendationEngine.build_daily_plan。
2. 选择第一个任务作为 selected_task。
3. 调用 LearningOrchestrator.start_task。
4. 在 state 中保存：
   - recommendation_plan
   - selected_task
   - episode_id
   - answer_required
   - current_task_id

五、支持 answer_required

如果任务需要用户作答，Daily Lesson 不应该一次性跑完。

请在 LearningState 中新增或确认存在：
- answer_required: bool
- current_task_id: str | None
- episode_id: str | None
- resume_from: str | None
- checkpoint_status: str | None

第一阶段可以做到：
- start 返回 answer_required=true
- 用户提交 answer 后再走 grading / memory / mastery / review

如果完整 checkpoint 较复杂，可以先实现轻量版状态保存，但接口和状态字段要预留。

六、API

新增或调整 API：

POST /api/learners/{learner_id}/daily-lessons/start

返回：
- episode_id
- task_spec
- prompt / question
- answer_required
- recommendation_reason

POST /api/learners/{learner_id}/daily-lessons/{episode_id}/answer

body:
- answer: str
- metadata: dict

返回：
- feedback
- grading_result
- mastery_update
- memory_updates
- verification_status
- next_recommendation

七、测试

新增测试：

1. start daily lesson 会调用 RecommendationEngine。
2. start daily lesson 会创建 AgentEpisode。
3. start 返回 selected TaskSpec。
4. 如果任务需要用户作答，返回 answer_required=true。
5. submit answer 后 episode 变 completed。
6. submit answer 后包含 exercise_graded / mastery_updated / memory_written event。
7. 原有 graph smoke test 不应失败。

八、验收标准

我应该能演示：

start daily lesson
→ 系统推荐一个任务
→ 创建 episode
→ 返回题目等待用户回答
→ 用户提交答案
→ 系统评分、更新掌握度、写记忆、安排复习
→ episode completed
```

---

# Task 7：新增 Tool Registry 和 ToolCall 统一记录

```text
请为 BinnAgent 新增 Tool Registry，用于把系统内部能力统一封装为可观测、可追踪、可验证的工具调用。

目标：不是让 LLM 随意调用工具，而是让 Agent Runtime 调用 RAG、Memory、Exercise、Mastery、Review、Recommendation 等能力时，都有 schema、超时、错误、trace 和 episode 归因。

一、新增模块

创建：

- src/tools/
- src/tools/registry.py
- src/tools/types.py
- src/tools/executor.py

二、定义 ToolSpec

ToolSpec:
- name: str
- description: str
- input_schema: dict
- output_schema: dict
- risk_level: str
  low / medium / high
- timeout_ms: int = 30000
- retry_policy: dict = {}
- requires_approval: bool = False
- metadata: dict = {}

ToolExecutionInput:
- tool_name: str
- episode_id: str | None
- payload: dict
- metadata: dict = {}

ToolExecutionResult:
- tool_name: str
- status: str
  success / failed
- output: dict | None
- error: str | None
- latency_ms: int | None
- input_hash: str
- output_hash: str | None

三、ToolRegistry

实现：

class ToolRegistry:
    def register(spec: ToolSpec, handler: Callable)
    def get(name: str)
    def list_tools()
    async def execute(input: ToolExecutionInput) -> ToolExecutionResult

四、注册第一批工具

先注册以下工具：

- rag.retrieve
- exercise.grade
- memory.retrieve
- memory.write
- mastery.update
- review.schedule
- recommendation.plan
- verification.verify_episode

如果某些现有逻辑参数复杂，可以先做 wrapper，保证最小可用。

五、和 AgentEpisode 集成

当 ToolRegistry.execute 收到 episode_id 时：
- 自动写 ToolCallRecord
- 记录 input_hash、output_hash、latency_ms、status、error
- 出错时不要吞异常，返回 ToolExecutionResult failed，并允许上层决定是否 fail episode

六、API

新增调试 API：

GET /api/tools

返回已注册工具列表，不返回 handler 内部实现。

七、测试

新增测试：

1. 可以注册 tool。
2. 可以执行 tool。
3. tool 执行成功时写 ToolCallRecord。
4. tool 执行失败时写 failed ToolCallRecord。
5. /api/tools 返回工具列表。
6. episode trace 中能看到 tool calls。

八、验收标准

一次 Daily Lesson / Knowledge Exercise 执行后，episode trace 里应该能看到：
- exercise.grade
- memory.write
- mastery.update
- verification.verify_episode

每个 tool call 都有 status、latency、input_hash、output_hash。
```

---

# Task 8：新增 VerificationReport 系统

```text
请为 BinnAgent 新增 VerificationReport 系统，用于检查一次 AgentEpisode 是否真的完成了关键步骤。

目标：把 Agent 输出从“看起来完成”升级为“可验证完成”，增强项目的 Harness 工程属性。

一、新增模块

创建：

- src/verification/
- src/verification/types.py
- src/verification/report.py
- src/verification/checks.py

二、定义类型

VerificationCheck:
- name: str
- check_type: str
  deterministic / schema / business_rule / regression / llm_judge
- passed: bool
- expected: Any | None
- actual: Any | None
- evidence_refs: list[EvidenceRef] = []
- message: str | None = None

VerificationReport:
- episode_id: str
- task_id: str | None
- status: str
  passed / failed / partial
- checks: list[VerificationCheck]
- failed_reason: str | None
- generated_at: datetime
- metadata: dict = {}

三、实现通用检查

在 checks.py 中实现：

- check_event_exists(episode_trace, event_type)
- check_tool_call_success(episode_trace, tool_name)
- check_payload_field_exists(event, field)
- check_score_range(score)
- check_evidence_non_empty(evidence_refs)
- check_episode_completed(episode)

四、实现 verify_episode

在 report.py 中实现：

class VerificationService:
    async def verify_episode(episode_id: str) -> VerificationReport

根据 episode.task_spec.verification_policy.required_checks 执行对应检查。

先支持这些 check 名称：

- episode_started
- exercise_answered
- exercise_graded
- mastery_update_valid
- memory_event_written
- review_scheduled
- evidence_non_empty
- episode_completed

五、和 Runtime 集成

EpisodeRuntime.complete_episode 时可以接收 verification_report。

LearningOrchestrator 或 Knowledge Exercise 流程在结束前调用 VerificationService.verify_episode，把 report 写入 AgentEpisode.verification_report。

六、API

新增：

GET /api/runtime/episodes/{episode_id}/verification

返回 VerificationReport。

七、测试

新增测试：

1. 缺少 exercise_graded event 时 verification failed。
2. 有完整事件链时 verification passed。
3. score 不在 0-1 时 mastery_update_valid failed。
4. evidence required 但为空时 evidence_non_empty failed。
5. complete_episode 后 verification_report 写入 AgentEpisode。

八、验收标准

我可以查询任意 episode 的 verification report，看到每个 check 的 passed/failed 和证据。
```

---

# Task 9：新增 Simulation Regression for Episode Runtime

```text
请扩展 BinnAgent 现有 simulation / evaluation 体系，让它能够回归测试 AgentEpisode Runtime。

目标：通过模拟学习者执行一次教材知识点练习，验证完整链路：
RecommendationPlan
→ TaskSpec
→ AgentEpisode
→ ExerciseAttempt
→ MasteryUpdate
→ MemoryEvent
→ VerificationReport
→ Completed Episode

一、阅读现有代码

请阅读：
- src/simulation/learner_agent.py
- src/simulation/runner.py
- src/simulation/fixtures.py
- src/runtime/
- src/recommendation/
- src/mastery/
- src/verification/

二、新增 Scenario

在 fixtures 中新增一个 scenario：

episode_runtime_knowledge_practice

步骤建议：
1. create_learner
2. seed knowledge source / knowledge point，如果已有 fixture 方法则复用
3. build daily recommendation plan
4. start daily lesson
5. simulated learner answer
6. submit answer
7. fetch episode trace
8. fetch verification report

三、断言

新增 assertions：

- recommendation_plan exists
- selected_task exists
- episode_id exists
- episode status completed
- event exercise_answered exists
- event exercise_graded exists
- event mastery_updated exists
- verification_report.status == passed
- tool_call_records count >= 1

四、Runner 支持

如果现有 ScenarioRunner 不支持这些 action，请新增 action handler：

- daily_plan
- start_daily_lesson
- submit_daily_lesson_answer
- fetch_episode_trace
- fetch_verification_report

五、报告

Simulation report 中新增 runtime_metrics：

- episode_count
- completed_episode_count
- failed_episode_count
- verification_pass_count
- verification_fail_count
- avg_tool_latency_ms，如果可以计算

六、CI

如果测试耗时可控，把该 scenario 加入 lightweight simulation smoke test。

不要依赖真实 LLM 或外部服务。如果必须 mock model provider，请按项目现有测试风格 mock。

七、测试

新增测试：

1. scenario 可以运行完成。
2. report 包含 runtime_metrics。
3. verification passed。
4. 没有破坏旧 scenario。

八、验收标准

我可以运行 simulation，得到一个包含 AgentEpisode trace 和 VerificationReport 的回归测试结果。
```

---

# Task 10：前端新增 Episode Debug 页面

```text
请为 BinnAgent 前端新增 Episode Debug 页面，用于展示一次 AgentEpisode 的完整运行链路。

目标：面试演示时可以展示“系统为什么这么做、用了哪些证据、调用了哪些工具、最后是否通过验证”。

一、阅读前端结构

请先阅读：
- binnagent-frontend/src/pages/
- binnagent-frontend/src/components/
- binnagent-frontend/src/lib/api 或现有 API client
- MemoryCenterPage.tsx 的风格

二、新增页面

创建页面：

EpisodeDebugPage.tsx

路由建议：
/runtime/episodes/:episodeId

三、页面内容

展示：

1. Episode Summary
- episode_id
- learner_id
- status
- source
- entrypoint
- started_at
- completed_at
- failure_type

2. TaskSpec Card
- task_type
- objective
- target_type
- target_id
- allowed_tools
- success_criteria
- verification_policy

3. Timeline

按 occurred_at 展示 LearningEvent：

- event_type
- source_module
- target
- payload 摘要
- evidence_refs 数量

4. Tool Calls

表格展示：
- tool_name
- status
- latency_ms
- input_hash
- output_hash
- error

5. VerificationReport

展示每个 check：
- name
- check_type
- passed
- message
- evidence_refs

6. Raw JSON 折叠面板

方便调试，但默认折叠。

四、API

调用后端：

GET /api/runtime/episodes/{episode_id}
GET /api/runtime/episodes/{episode_id}/verification

如果 verification 已包含在 episode trace 中，可以只请求一个 API。

五、交互

- passed 用明显状态展示
- failed 显示 error message
- evidence_refs 可以先只展示 type/id/reason，不必第一阶段解析详情
- loading / error / empty 状态完整

六、测试 / 构建

如果项目已有前端测试风格，补充最小测试；否则至少保证：
- npm run lint
- npm run build

七、验收标准

我可以输入一个 episode_id，看到：
- TaskSpec
- event timeline
- tool calls
- verification checks
- raw JSON

这个页面用于技术面试演示 Agent Runtime / Harness 能力。
```

---

# Task 11：把 Explore Tab 入口统一接入 TaskSpec

```text
请把 BinnAgent 的 Explore Tab / 学习能力入口改造成统一 TaskSpec 入口。

目标：探索模块不再是孤立页面入口，而是每个入口都能生成标准 TaskSpec，并进入统一 AgentEpisode Runtime。

一、阅读前端和后端

请先阅读：
- Explore Tab 相关前端页面和组件
- 后端对应 explore / vocabulary / writing / knowledge API
- src/runtime/task_spec.py
- src/learning/orchestrator.py

二、定义 ExploreCapabilitySpec

在后端新增或扩展：

ExploreCapabilitySpec:
- capability_id: str
- feature_id: str
- title: str
- description: str
- category: str
- status: ready / todo
- action: chat / session / tool / vocabulary-detail / todo
- tool_target: str | None
- learning_skill: str
- task_type: str
- target_type: str | None
- default_difficulty: str | None
- estimated_minutes: int | None
- allowed_tools: list[str]
- produces:
  - attempt
  - memory_event
  - mastery_update
  - review_schedule
- metadata: dict

三、后端 API

新增：

GET /api/explore/capabilities

返回所有探索学习能力入口。

POST /api/explore/capabilities/{capability_id}/start

body:
- learner_id
- target_id optional
- difficulty optional
- metadata optional

返回：
- episode_id
- task_spec
- status
- answer_required
- prompt / initial_payload

四、TaskSpec 生成

每个 ExploreCapability 必须生成 TaskSpec。

第一阶段至少支持 3 个入口：

- vocabulary_practice
- writing_phrase_practice
- grammar_micro_lesson 或 knowledge_practice

五、Runtime 接入

调用 LearningOrchestrator.start_task。

如果某个 capability 还没有完整 handler，可以返回 not_implemented，但要保留 TaskSpec 和 episode_started event，方便后续扩展。

六、前端调整

Explore Tab 卡片点击后，不直接跳散落功能逻辑，而是调用 start API。

可以保留原页面，但 URL 中带 episode_id 或 task_id。

七、测试

新增测试：

1. GET /api/explore/capabilities 返回学习能力列表。
2. 每个 capability 都有 task_type 和 allowed_tools。
3. start vocabulary_practice 返回 TaskSpec。
4. start capability 创建 AgentEpisode。
5. 不支持的 capability 明确返回 not_implemented，不崩溃。

八、验收标准

Explore Tab 的入口和教材入口、推荐入口一样，最终都进入 TaskSpec + AgentEpisode Runtime。
```

---

# Task 12：补充简历导向架构文档

```text
请为 BinnAgent 新增一份面向技术面试的架构文档，重点展示 Agent Runtime / Harness 工程能力。

创建文件：

docs/interview/agent-runtime-harness.md

文档请包含以下内容：

一、项目定位

说明 BinnAgent 不是普通英语学习 Chatbot，而是一个面向学习场景的 Agent Runtime / Harness 工程实践。

核心技术主线：
- TaskSpec-based Orchestration
- AgentEpisode Runtime
- Event-driven Learning Pipeline
- Evidence-grounded Recommendation
- Long-term Memory
- Knowledge Tracing / Mastery Engine
- RAG-grounded Exercise Generation
- Tool Registry
- VerificationReport
- Simulation-based Regression Testing
- Langfuse Observability

二、架构图

用 Mermaid 画出：

User / Frontend
→ API
→ LearningOrchestrator
→ RecommendationEngine
→ TaskSpec
→ AgentEpisode
→ ToolRegistry
→ RAG / Exercise / Memory / Mastery / Review
→ LearningEvent
→ VerificationReport
→ Simulation / Observability

三、核心闭环

描述一次教材知识点练习的完整链路：

1. RecommendationEngine 生成 TaskSpec
2. AgentEpisode 创建运行上下文
3. RAG 检索教材证据
4. Exercise 生成 / 评分
5. MasteryEngine 更新掌握度
6. MemoryWriter 写学习证据
7. ReviewScheduler 安排复习
8. VerificationService 验证任务完成
9. Episode trace 可调试可回放

四、关键数据结构

列出并解释：

- TaskSpec
- AgentEpisode
- LearningEvent
- EvidenceRef
- MasteryUpdateResult
- RecommendationPlan
- ToolCallRecord
- VerificationReport

五、面试讲法

给出 3 分钟技术介绍稿，突出：
- 为什么不是普通 RAG
- 为什么不是简单 Chat
- 为什么有长期记忆价值
- 为什么 Agent 行为可解释、可验证、可回归

六、当前边界和后续计划

如实说明：
- 当前哪些模块已实现
- 哪些是第一阶段 runtime 接入
- 后续会增强 checkpoint/resume、权限、多用户隔离、在线 eval

七、验收标准

文档应能让技术面试官快速理解：
- 系统复杂度
- 工程抽象能力
- Agent Harness 能力
- 可靠性设计
```

---

# 最推荐执行顺序

```text
1. Task 1：Agent Runtime 基础抽象
2. Task 3：EvidenceRef
3. Task 8：VerificationReport
4. Task 2：Knowledge Exercise 接入 AgentEpisode
5. Task 4：MasteryEngine
6. Task 5：RecommendationEngine
7. Task 6：Daily Lesson Orchestrator
8. Task 7：Tool Registry
9. Task 9：Simulation Regression
10. Task 10：Episode Debug 页面
11. Task 11：Explore Tab 接入 TaskSpec
12. Task 12：面试架构文档
```

实际执行时，**先做 1、2、3、8、12 就已经很有面试展示价值**。这几项能最快把项目从“学习功能集合”包装成“Agent Runtime / Harness 工程项目”。
