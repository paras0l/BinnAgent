# BinnAgent Agent 应用开发面试拷问题

> 角色设定：面试官已经读过你的简历 HTML 和项目文档，对 Agent Runtime、LangGraph、Memory、PromptExecutor、RAG、Simulation、Dev Console 和 Learner Isolation 都比较熟。他不会只问“用了什么技术”，而会追问你为什么这么做、边界在哪里、失败时怎么兜底、如何证明它真的可靠。
>
> 简历靶点：TaskSpec / AgentEpisode / LearningEvent / ToolCallRecord / VerificationReport / Checkpoint、LangGraph Daily Lesson、ExerciseAttempt → Mastery → ReviewSchedule → Memory → Recommendation、Retain / Recall / Reflect / Control、Prompt Registry + Schema-first、Langfuse + Dev Console、deterministic learner simulation、飞书 MCP 群聊学习线索，以及 Java 后端经历如何迁移到 Agent 工程。

## 一、项目定位与系统边界

### 1. 你怎么用 2 分钟说明 BinnAgent 不是普通 Chatbot，而是一个 Agent 应用？

- 如果面试官说“这不就是套了个英语学习 prompt 吗”，你会怎么反驳？
- 你项目里的 Agent Runtime 和传统后端业务流最大的区别是什么？
- 哪些能力必须由状态机、工具调用、记忆和验证共同完成，不能只靠一次 LLM 调用？
- 你会把这个项目的核心闭环画成哪几个节点？

### 2. 你为什么把项目主线定义成“可解释、可验证、可持续个性化”的学习闭环？

- “个性化”在你的实现里具体由哪些数据驱动？
- 哪些东西不能被当作个性化依据？
- Memory、Mastery、Review、Recommendation 四者之间是什么关系？
- 如果只有聊天历史，没有 ExerciseAttempt 和 Mastery，这个系统会退化成什么？

### 3. 项目里教材解析、RAG、练习生成、群聊学习线索很多，你怎么解释产品主线没有发散？

- 哪些模块是核心 runtime，哪些只是知识来源或入口？
- 你为什么说教材解析不是主卖点？
- 面试官问“你做太多功能，是不是没聚焦”，你会怎么回答？
- 如果必须删掉一半功能保留面试展示价值，你会保留哪条链路？

### 4. 这个项目最能体现 Agent 工程能力的 3 个技术决策是什么？

- 为什么不是“接入 Ollama”或“做了 RAG”？
- 哪个决策最能体现你对可靠性的理解？
- 哪个决策最能体现你对用户数据边界的理解？
- 哪个决策如果重做，你会换方案？

### 5. 你如何定义这个系统里的“任务完成”？

- LLM 给了反馈就算完成吗？
- VerificationReport 为什么会影响 episode status？
- `completed`、`completed_with_warnings`、`verification_failed` 的差别是什么？
- 什么情况下你宁愿阻止 completed，也不让系统静默成功？

## 二、LangGraph Runtime 与学习任务编排

### 6. 你为什么选择 LangGraph 来编排 Daily Lesson？

- FastAPI service 里串几个函数不行吗？
- LangGraph 的状态机对 interrupt / resume 有什么帮助？
- 你现在用的是完整官方 interrupt 机制吗？如果不是，为什么？
- 当前实现和生产级 LangGraph checkpointer 之间还差什么？

### 7. Daily Lesson 的节点链路为什么是 `wait_for_answer -> grade_attempt -> update_mastery -> feedback -> memory -> review -> recommend -> verify`？

- 为什么 `wait_for_answer` 必须在评分前截断？
- 为什么反馈不应该先于 mastery 更新？
- 为什么 memory 写入要放在评分和 mastery 之后？
- 哪些节点产生的是业务副作用，哪些只是 graph state？

### 8. 你怎么设计“等待真实用户作答”的 checkpoint？

- `waiting_user` checkpoint 里保存哪些字段？
- `resume_from="grade_attempt"` 为什么合理？
- 用户刷新页面或服务重启后，如何恢复题面和 input schema？
- 如果用户重复提交答案，怎么避免重复写 ExerciseAttempt 和 Memory？

### 9. `LearningOrchestrator` 和 `daily_lesson_graph` 的职责怎么划分？

- 为什么真实 DB 写入不全部放进 graph node？
- `_select_question`、checkpoint 创建、episode event 记录应该归谁负责？
- graph node 返回的 `grade_result` 和 orchestrator 里的真实 `ExerciseAttempt` 有什么差异？
- 这种拆分会带来什么一致性风险？

### 10. `build_resume_graph(start_node="grade_attempt")` 的设计有什么优缺点？

- 为什么 resume graph 只允许部分 start nodes？
- 如果未来支持多步骤 lesson，这个 resume graph 会怎么演进？
- 如果中途在 `update_memory` 失败，你应该从哪里恢复？
- 怎么保证恢复时不会重复执行前面已经成功的副作用？

### 11. 你现在的 daily lesson 还是“单题单 active checkpoint”，这个限制会影响哪些场景？

- 多题 lesson 怎么表示多个 checkpoint？
- 用户同时打开两个 lesson 怎么处理？
- `abandon_waiting_checkpoints_for_learner` 的产品含义是什么？
- 如果要支持并行学习任务，你会改哪些表和 API？

### 12. LangGraph state 里哪些字段必须稳定，哪些只是调试辅助？

- `thread_id`、`episode_id`、`graph_run_id` 分别解决什么问题？
- `prompt_payload` 和 `required_input_schema` 为什么要持久化？
- `input_materials` 进入 trace 后有什么价值？
- 如果 state 结构变更，旧 checkpoint 怎么兼容？

### 13. 你如何处理 graph node 里的异常和降级？

- 模型调用失败应该在哪个层级捕获？
- 工具调用失败是否一定导致 episode failed？
- warning 和 critical failure 如何区分？
- 哪些失败可以允许 completed_with_warnings？

## 三、Memory、Mastery 与个性化学习

### 14. 你项目里的 Memory 为什么不是聊天历史？

- L1-L4 四层分别是什么？
- LearningEpisode 和 LearnerModelMemory 分别解决什么问题？
- 为什么低置信推断不能直接写成长程 learner model？
- 用户编辑或否认记忆后，后续 Recall 应该怎么受影响？

### 15. Retain / Recall / Reflect / Explain / Control 五个动作在代码里如何落地？

- `MemoryWriter.record_event()` 记录的是什么层级的数据？
- `MemoryRetriever.for_*()` 为什么要按场景拆方法？
- `MemoryCurator.reflect()` 什么时候触发比较合适？
- `MemoryOperation` 为什么也是一种需要保留的 evidence？

### 16. ExerciseAttempt、MasteryEngine、MemoryWriter 的调用顺序为什么重要？

- 如果先写 Memory 再评分，会有什么问题？
- Mastery 更新需要哪些 evidence？
- Memory 里应该记录原始答案、错因、分数还是全部？
- 怎么避免一次错误答案对长期画像造成过大影响？

### 17. 你如何设计掌握度更新，不让它变成简单的“答对 +1，答错 -1”？

- 题目难度、题型、hint、retry 是否应该影响 mastery delta？
- mastery score 应该是知识点维度、词汇维度还是技能维度？
- 如何处理“认识但不会拼写”这种多维掌握差异？
- 你现在实现中哪些地方还是简化版？

### 18. 场景化 Recall 为什么重要？

- Chat、daily lesson、vocabulary practice、essay review 需要的记忆有什么不同？
- MemoryContextLog 记录 loaded/excluded items 有什么调试价值？
- 如果 Recall 召回了错误或过期记忆，用户怎么纠正？
- 你怎么评估 Recall 的 hit-rate 或有效性？

### 19. 你如何解释 Memory 的可控性和安全边界？

- 用户删除、禁用、标记已改善分别有什么语义？
- 情绪/节奏记忆为什么要有开关？
- Memory Center 为什么从普通学习端移到 Dev Console 或弱化展示？
- 如果系统把用户贴上不准确标签，如何纠偏？

### 20. 你怎么证明 Memory 真的改善了学习体验？

- 你会设计哪些 A/B 或 simulation 指标？
- 哪些指标能证明推荐更准，而不是只是写了更多数据？
- Memory write count 高一定好吗？
- 如何发现 Memory 污染或过度召回？

## 四、PromptExecutor、Schema-first 与模型治理

### 21. 你为什么设计 Prompt Registry 和 PromptExecutor？

- 直接在业务代码里写 prompt 有什么问题？
- `PromptMetadata` 应该包含哪些治理字段？
- prompt hash 和 input hash 的价值是什么？
- prompt version 和 eval_set 怎么支持回归？

### 22. Schema-first 规则解决了什么真实风险？

- 哪些业务表绝不能接受未校验的 LLM 输出？
- `passed`、`repaired`、`fallback`、`failed` 的语义差别是什么？
- 为什么 regex fallback 默认 `review_required`，不能自动 accepted？
- 如果模型输出字段缺失但语义看起来正确，你怎么处理？

### 23. 你怎么解释 Langfuse 和本地 PromptExecutionRecord 的边界？

- 为什么不在本地存 raw prompt / raw output？
- Langfuse 不可用时业务流程应该失败吗？
- 本地记录需要回答什么问题？
- 这套边界对隐私和可观测性有什么取舍？

### 24. `execute_with_raw_output()` 为什么对 prompt eval 很关键？

- 它如何避免真实模型随机性？
- eval fixture 里应该覆盖哪些 case？
- schema pass rate 低于阈值时为什么要让脚本失败？
- prompt 改动和 simulation baseline 更新有什么不同？

### 25. 当前还有哪些直接 model 调用路径没有迁移到 PromptExecutor？

- vocabulary agent、exercise generation、essay scoring 这些路径迁移难点分别是什么？
- 对 HTML 生成类输出，schema-first 应该怎么做？
- 哪些模型调用可以只是 observability，不需要强 schema？
- 你会按什么优先级继续治理？

### 26. 你怎么处理本地 Ollama 的 JSON 输出不稳定问题？

- JSON repair retry 能解决哪些问题，不能解决哪些问题？
- schema validation 失败后是否应该让模型重试？
- retry 次数、fallback、人工 review 的边界怎么定？
- 如果本地模型质量不够，云模型 fallback 的权限和隐私怎么控制？

## 五、RAG、知识库与练习生成

### 27. BinnAgent 的 RAG 不是简单问答检索，它在学习闭环中承担什么角色？

- KnowledgeSource、CurriculumNode、KnowledgePoint、KnowledgeChunk 的关系是什么？
- RAG chunk 为什么要关联单元或知识点？
- 检索结果如何进入 evidence，而不只是进入 prompt？
- RAG 失败时为什么可以降级关键词匹配？

### 28. 教材上传解析链路为什么需要 ParserRun、QualityGate 和 ReviewQueue？

- 低质量解析如果直接进入知识库，会污染哪些下游模块？
- `published`、`review_required`、`partial_indexed`、`blocked` 的区别是什么？
- 哪些 review item 应该阻止发布？
- 你如何向面试官解释“解析质量治理”比“支持更多 PDF”更重要？

### 29. 单元覆盖计划、双重质量门禁和 rubric grader 的设计意图是什么？

- 为什么不能直接让 LLM 生成一批题后保存？
- 确定性门禁与独立 LLM reviewer 分别解决什么问题？
- 检查知识点覆盖、题型分布、场景性和主动输入比例有什么价值？
- 主观题为什么不能只用 exact match？
- hint / retry / next_review_signal 如何服务后续 mastery 和 review？

### 30. AI 生成练习为什么必须“可编辑、可确认、可追溯”后再保存？

- 这和 schema-first 的关系是什么？
- 用户确认前应该把内容放在哪里？
- 生成题的 provenance 应该记录哪些字段？
- 如果用户编辑了 AI 生成题，后续追责和质量评估怎么算？

### 31. 你如何评价当前 RAG 的技术选型？

- pgvector + HNSW cosine 的优点和限制是什么？
- 768 维向量和 embedding 模型绑定会带来什么迁移成本？
- hybrid retrieval 还没完成会影响哪些查询？
- 如果教材 chunk 没有页码或 evidence，Debug Console 怎么暴露问题？

### 32. Public textbook pack v2 为什么要物化为数据库结构，而不是只放 JSON 文件？

- 幂等 seed 要解决什么问题？
- 公共教材和 learner-owned private source 的权限边界在哪里？
- 多教材切换时，学习进度和推荐如何避免串源？
- 如果八/九年级教材解析质量不稳定，产品上怎么降级？

## 六、Simulation、Evaluation 与回归安全网

### 33. Agent 应用为什么需要 simulation，而不只是单元测试？

- 一次代码改动可能影响哪些跨模块链路？
- contract / integration / e2e 三种 mode 各自覆盖什么？
- 为什么 contract mode 可以进默认 CI？
- 哪些问题只有 integration 或 e2e 才能发现？

### 34. 你怎么设计一个 learner simulation scenario？

- persona、entrypoints、expected events、required metrics 分别是什么？
- module_tags 和 change_triggers 如何帮助选择受影响场景？
- scenario 的 assertion 应该验证行为结果还是实现细节？
- 如何避免 scenario 过度脆弱？

### 35. DeterministicFakeModelRouter 的价值是什么？

- 它和 mock HTTP response 有什么不同？
- 为什么 integration simulation 需要确定性模型？
- 如何模拟 schema-invalid 或 repaired JSON 输出？
- 真实 LLM e2e 失败时，怎么区分产品 bug 和模型波动？

### 36. baseline comparison 和 threshold gate 的边界是什么？

- 什么情况下可以更新 baseline？
- 什么情况下绝对不能用更新 baseline 掩盖问题？
- 哪些指标适合 directional regression？
- latency、memory_write_count、verification_pass_rate 的回归语义一样吗？

### 37. 对 LangGraph、Memory、Prompt、Knowledge 改动，你会怎么选择要跑的 simulation？

- `scripts/list_impacted_simulations.py` 基于什么信息推导？
- 如果改了 `src/graph/main_graph.py`，你预计跑哪些场景？
- 如果改了 prompt schema，除了 prompt eval 还要跑什么？
- PR 描述里应该怎么报告 impacted simulations？

### 38. VerificationReport 和 SimulationReport 有什么区别？

- VerificationReport 面向单个 episode 的哪些检查？
- SimulationReport 面向跨步骤场景的哪些指标？
- 两者如何互相补充？
- 如果 simulation 通过但 verification failure 增多，你怎么定位？

## 七、Observability、Dev Console 与可调试性

### 39. 复杂 Agent 为什么必须有 Dev Console？

- 普通用户端为什么不应该暴露 Memory / Runtime / Parser Debug 细节？
- Dev Console 最关键的三个调试入口是什么？
- EpisodeTraceView 应该能回答哪些问题？
- 如果用户说“系统为什么推荐这个练习”，你怎么从 trace 里查？

### 40. 你如何设计 EpisodeTrace、ToolCallRecord、EvidenceRef 的关系？

- event、tool call、evidence ref 分别记录什么？
- EvidenceRef 为什么不能只是字符串备注？
- tool success rate 如何影响 verification 或 simulation？
- 追踪太细会带来哪些存储和隐私问题？

### 41. Debug API 默认关闭且需要 token，这个设计够安全吗？

- debug token 和 learner ownership 是什么关系？
- 为什么 debug access 不应该绕过 learner scope？
- simulation report 文件可能包含什么隐私风险？
- 如果部署到远程环境，还需要哪些安全措施？

### 42. 你如何把 Langfuse、本地 runtime trace、PromptExecutionRecord 串起来排查一次坏输出？

- 从用户反馈到 episode_id 的排查路径是什么？
- 如何定位具体 prompt_id / version / input_hash？
- 如何判断是检索证据错、prompt 错、模型输出错，还是 schema fallback 错？
- 修复后如何防止同类问题回归？

## 八、Learner Isolation、安全与多用户边界

### 43. 为什么不能信任前端传来的 `learner_id`？

- 当前 `get_current_user()` 和 `get_current_learner()` 怎么工作？
- `Learner.tenant_id` 在当前阶段扮演什么临时角色？
- unowned legacy learner 为什么只允许 local-dev fallback？
- 如果进入 SaaS，多租户模型还差哪些设计？

### 44. Phase 1 learner-scoped isolation 已加固哪些高风险路径？

- Runtime trace、Daily Lesson、Memory、Explore、ExerciseAttempt 分别如何加固？
- Debug learners list 为什么只是 partially hardened？
- RAG debug search 的 `source_id` / `node_id` 还有什么风险？
- 哪些旧 router 还需要迁移？

### 45. 你怎么设计 scoped resource helper？

- `get_episode_for_learner` 和直接查 `episode_id` 的区别是什么？
- private textbook source 派生出的 node、chunk、question 如何做所有权校验？
- ToolCallRecord 通过 episode scope 访问有什么好处？
- helper 太多会不会让代码重复？你怎么抽象？

### 46. Learner-owned data 的隔离测试怎么写？

- API 测试应该构造哪些用户和 learner？
- 403、404、空列表三种返回语义怎么选择？
- Debug token + 非 owner learner 应该返回什么？
- 如何避免测试只覆盖 path learner，不覆盖下游 id-only lookup？

## 九、前端体验与产品工程

### 47. 为什么普通学习端主导航收敛为 `AI对话 / 探索 / 学习中心`？

- Memory 和 Runtime 调试为什么不适合做一级入口？
- Dashboard 从统计页变成今日学习驾驶舱有什么产品考虑？
- ExploreCapability 推荐卡片为什么要解释原因？
- 学习中心如何避免变成杂乱功能入口？

### 48. AI 或外部生成内容“保存前可确认、可编辑、可追溯”在前端怎么体现？

- 练习生成、写作好句导入、群聊学习线索分别如何做确认？
- 哪些内容可以自动沉淀，哪些必须用户确认？
- 前端 fallback 到 localStorage 时，怎么不破坏后端数据一致性？
- 你如何提示用户生成内容的来源和可信度？

### 49. Dev Console 和 Learner App 分离会带来哪些工程复杂度？

- 两套 Vite 入口或路由如何复用组件？
- Debug API token 如何在前端处理？
- 哪些 UI 组件应该共享，哪些应该只在 Dev Console 出现？
- 如何避免调试页面泄漏到普通用户导航？

### 50. 如果让你做 5-8 分钟项目 demo，你会怎么安排？

- 你会先展示学习端还是 Dev Console？
- 哪个场景最能证明 checkpoint / resume？
- 哪个 trace 最能证明 Memory / Mastery / Verification 闭环？
- 如果现场 Ollama 很慢或不可用，你的备用演示方案是什么？

## 十、简历靶向与反思追问

### 51. 你简历里写“将一次学习过程建模为 TaskSpec、AgentEpisode、LearningEvent、ToolCallRecord、VerificationReport 与 Checkpoint”，这些对象分别解决什么问题？

- 如果面试官让你现场打开代码，你会分别看哪些文件？
- TaskSpec 和 AgentEpisode 的边界是什么？
- LearningEvent 和 ToolCallRecord 为什么不合并成一个日志表？
- VerificationReport 和 Checkpoint 为什么都是 runtime 的一等对象？

### 52. 你简历里写 `ExerciseAttempt → Mastery → ReviewSchedule → Memory → Recommendation`，但文档里也出现过 Memory 和 Review 的不同顺序，你怎么解释真实业务顺序？

- 哪些步骤必须在同一事务或同一 episode trace 内可关联？
- 如果 ReviewSchedule 写成功但 Memory 写失败，episode 应该是什么状态？
- 推荐下一步时更应该依赖 Mastery、Memory，还是 Review due queue？
- 简历里为了表达清楚做了链路压缩，面试中如何补充精确边界？

### 53. 你简历里提到飞书 MCP 群聊学习线索捕捉，这条线和核心学习 Agent 有什么关系？

- 群聊消息为什么不能直接写入 Memory 或 Vocabulary？
- 显式标签即时抽取和低频 LLM 小批量抽取分别适合什么场景？
- 收件箱确认后沉淀为学习资产，如何保证 learner scope 和 provenance？
- 如果面试官质疑这个功能偏产品而非 Agent 技术，你会怎么把它拉回 evidence / memory / recommendation 闭环？

### 54. 你简历同时投 Agent 应用开发和 Java 后端开发，你怎么证明这些经历不是割裂的？

- 供应链系统、Flowable、Elasticsearch 导出、Excel 导入导出这些经历如何迁移到 Agent 工程？
- 你在 BinnAgent 里哪些设计体现了传统后端的事务、权限、索引、可观测性和可维护性意识？
- 如果面试官更偏 Java，会追问你哪些 SpringBoot / MyBatis / Redis / ES 基础？
- 你如何解释 Python FastAPI 项目也能体现后端工程能力？

### 55. 你如何把这个项目讲成一段有说服力的简历经历？

- 你会强调哪些量化指标或验证方式？
- 如何避免只罗列技术栈？
- 如何讲清楚“我解决了什么难题”？
- 如果面试官要求你讲当前不足，你会选择 remaining direct prompt paths、生产 PostgresSaver、learner scope 还是前端 polish？
