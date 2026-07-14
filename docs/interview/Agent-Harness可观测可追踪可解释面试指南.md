# Agent Harness：可观测、可追踪、可解释面试指南

> 目标：把 Agent Harness 讲成一套控制 Agent 运行、记录决策路径、绑定证据、验证结果并支持调试回归的工程系统，而不是“接了一个日志平台”。
>
> 适用场景：Agent 应用开发、LLM Runtime、LangGraph、Tool Runtime、Memory、Evaluation、Langfuse、Dev Console。

## 1. 面试官真正想判断什么

当候选人说自己做过 Agent Harness，我会判断：

1. 是否能定义 Harness，而不是把它等同于框架或 tracing SDK。
2. 是否能区分可观测、可追踪、可解释、可审计和可复现。
3. 是否能设计 episode、event、span、tool call、prompt execution 和 evidence 的关联模型。
4. 是否知道 logs、metrics、traces 和 business events 各自回答什么问题。
5. 是否能跨 HTTP、LangGraph、模型、工具、后台任务和 checkpoint 传播上下文。
6. 是否处理异步、并行、streaming、resume 导致的乱序和重复执行。
7. 是否把解释建立在证据、规则和版本上，而不是让模型事后编一个理由。
8. 是否知道隐藏思维过程不是产品解释接口。
9. 是否能平衡 raw data 调试价值与隐私、成本和保留期限。
10. 是否能从 trace 反推测试、SLO、告警和回归评估。
11. 是否能诚实指出当前系统“能看见什么、看不见什么、可能记录错什么”。

深入的标志不是埋点数量，而是每一类记录都有明确语义、稳定关联键和可验证用途。

## 2. 什么是 Agent Harness

### 2.1 一句话定义

> Agent Harness 是包围模型与工作流的工程运行层：它接收任务，注入上下文和工具，约束执行预算，记录轨迹与业务事件，管理暂停恢复，验证结果，并把一次非确定 Agent 行为变成可调试、可审计、可回归的 episode。

### 2.2 Harness 通常包含什么

```text
Task Contract
  ├─ objective / target / allowed tools
  ├─ success criteria / verification policy
  └─ budget / risk policy

Runtime
  ├─ orchestration / state / checkpoint
  ├─ prompt execution / model routing
  ├─ tool gateway / approval / retry
  ├─ memory / evidence / domain writes
  └─ stop / failure / recovery

Assurance
  ├─ logs / metrics / traces
  ├─ business events / audit records
  ├─ evidence provenance
  ├─ verification report
  ├─ simulation / evaluation
  └─ debug console
```

Harness 不是某一个框架。LangGraph 可以承担 orchestration，Langfuse 可以承担模型观测，数据库可以承担业务审计，但 Harness 是这些能力组合后的运行边界。

### 2.3 一分钟总回答

> 我把 Agent Harness 分成执行、观测和保证三层。执行层用 TaskSpec、Episode、Graph、Tool Gateway 和 Checkpoint 控制任务如何运行；观测层用 trace/span、PromptExecution、ToolCall 和结构化 Event 回答发生了什么；保证层用 EvidenceRef、VerificationReport 和 Simulation 回答这次结果是否可信、为什么做出这个决定，以及改动后行为有没有回归。
>
> 我不会把“可解释”理解为展示模型 Chain of Thought。真正可靠的解释应该来自可验证输入：使用了哪些学习证据、触发了什么规则、采用哪个 prompt / model / tool 版本、哪些 alternatives 被策略拒绝、最终哪些 verification checks 通过。模型生成的自然语言解释只能作为展示层，不能作为唯一审计依据。
>
> BinnAgent 里，AgentEpisode 是一次业务任务主键；LearningEvent 表达领域状态变化；ToolCallRecord 和 PromptExecutionRecord 记录工具与 Prompt 决策；Langfuse 保存模型原始观测；EvidenceRef 把评分、Mastery、Memory 和推荐串起来；VerificationReport 决定 episode completed、warning 还是 verification_failed。Dev Console 再把这些投影成可排查视图。

## 3. 五个容易混淆的概念

### Q1：可观测、可追踪、可解释、可审计、可复现有什么区别？

#### 高质量回答

| 能力 | 核心问题 | 典型数据 |
|---|---|---|
| 可观测 Observability | 系统现在发生了什么、健康吗 | metrics、logs、traces |
| 可追踪 Traceability | 这次任务经过了哪些步骤和依赖 | episode、span、event lineage |
| 可解释 Explainability | 为什么产生这个业务决定 | evidence、rules、policy、decision |
| 可审计 Auditability | 谁在何时基于什么权限改变了什么 | immutable audit event、actor、before/after |
| 可复现 Reproducibility | 能否在受控条件下重建相同行为 | prompt/model/tool/data/config versions |

> 它们互相支持但不能替代。一个完整 trace 可以说明调用路径，却不一定说明推荐为什么合理；一个自然语言理由可以让用户看懂，却不一定满足审计或复现。

#### 追问：系统有 Langfuse trace，就已经可解释了吗？

> 没有。Trace 主要描述执行轨迹。若没有证据来源、规则版本、业务状态和 verification，看到 Prompt 与 Output 仍无法判断这次推荐是否有根据。

### Q2：Logs、Metrics、Traces、Events 分别用来做什么？

#### 高质量回答

- Logs：离散诊断文本或结构化记录，适合具体错误上下文。
- Metrics：可聚合数值时间序列，适合 SLO、趋势和告警。
- Traces：一次请求 / episode 跨组件的调用树和耗时。
- Business Events：领域事实，例如 `exercise_graded`、`memory_written`。

> “tool latency 2.3 秒”是 trace / metric；“本次评分证据写入了 Memory”是业务 event；“provider timeout stack”是 log。不要把所有内容都塞进一个 JSON log 后假装四种能力都有了。

### Q3：业务事件和 Event Sourcing 是一回事吗？

> 不是。记录 LearningEvent 只能说明系统保留了领域事件；只有当系统状态以事件日志为权威来源、能从事件重放并处理版本演进时，才能称为 event sourcing。BinnAgent 当前事件主要用于审计、验证和 trace，权威业务状态仍在领域表中。

### Q4：Tracing 与 Audit 为什么要分开？

> Trace 可以采样、过期、脱敏，也可能因观测平台故障而丢失；审计记录通常要求完整、不可抵赖、受事务保护和更长保留。模型 token 级 span 可以采样，但“谁批准发送消息”不能采样掉。

### Q5：解释和模型推理过程有什么区别？

> 解释是面向用户或审计者的、基于可验证证据的理由；内部推理文本不保证忠实，也可能包含敏感信息。系统应输出决策摘要、引用证据、规则和不确定性，而不是展示或依赖隐藏 Chain of Thought。

## 4. Harness 数据模型

### Q6：为什么需要 Episode？

> HTTP request 太短，conversation thread 太长。Episode 表示一次有目标、开始、结束、状态和成功标准的业务任务，能跨多个请求、模型调用、工具调用和 checkpoint。它是追踪与验证的主聚合键。

#### 追问：Episode 和 Trace ID 是否可以共用？

> 不建议混为一谈。Episode 是稳定业务实体；一个 episode 可能因恢复、重试或后台处理产生多个技术 trace。应建立一对多映射，而不是让观测平台 ID 成为业务主键。

### Q7：应该有哪些关联 ID？

#### 推荐模型

| ID | 语义 |
|---|---|
| request_id | 一次 HTTP / RPC 请求 |
| trace_id | 一次技术调用链 |
| span / observation_id | 调用链中的一个操作 |
| learner / user_id | 数据所有者或执行主体 |
| session_id | 产品学习会话 |
| thread_id | conversation / checkpoint lineage |
| episode_id | 一次业务任务 |
| task_id | TaskSpec 中的任务定义 |
| graph_run_id | 一次图执行尝试 |
| prompt_execution_id | 一次 prompt governance 决策 |
| tool_call_id | 一次工具执行 |
| checkpoint_id | 暂停恢复点 |
| evidence_id | 一个可解析证据对象 |

> 这些 ID 不能随意互换，也不能全部使用 learner_id。关联字段要贯穿 HTTP、graph config、tool metadata、worker job 和 Langfuse attributes。

### Q8：一次 Episode Trace 应包含什么？

> TaskSpec、当前状态、事件序列、模型执行、工具调用、checkpoint、evidence refs、verification report、失败类型和版本信息。原始敏感内容是否包含，应由权限和数据策略决定。

### Q9：Event schema 怎么设计？

#### 高质量回答

```text
event_id
episode_id / learner_id
event_type / schema_version
source_module
actor / causation_id / correlation_id
target_type / target_id
occurred_at / sequence
payload / evidence_refs
```

> `event_type` 必须是稳定枚举或受治理命名；payload 要版本化；并行和跨机器场景不能只靠 wall-clock timestamp 排序，最好增加 episode-scoped 单调 sequence 或 causation DAG。

### Q10：为什么需要 causation_id？

> correlation_id 表示“属于同一任务”，causation_id 表示“谁直接导致了我”。例如 `exercise_graded` 导致 `mastery_updated`，后者又导致 `review_scheduled`。没有因果边，只按时间相邻推断容易在并行流程中出错。

### Q11：ToolCall 应记录 raw input / output 吗？

> 取决于风险。调试价值高，但可能包含个人数据、secret 和大文档。常见做法是本地记录 schema、hash、大小、摘要、status、latency、version 和 trace reference；原始内容只在受控观测系统按策略保存。高风险审计可保存加密、脱敏的规范化参数，但不能无差别全量记录。

### Q12：Hash 有什么价值和局限？

> Stable hash 能判断输入是否相同、关联重试和检测 schema drift，不暴露原文。但 hash 不能解释内容，也无法证明记录者没有伪造；低熵输入还可能被字典枚举。敏感场景可使用带 secret 的 HMAC，并明确 canonical serialization。

### Q13：PromptExecution 为什么不能只记录 prompt 文本？

> 还需要 prompt_id / version / hash、input hash、schema、model policy、repair、fallback、confidence、decision 和 trace reference。否则只能看到模型说了什么，无法知道这个输出为什么被业务接受或拒绝。

## 5. Trace 设计与上下文传播

### Q14：Agent Trace 的 span 树怎么设计？

#### 推荐结构

```text
episode / agent span
├─ graph_run
│  ├─ load_profile
│  ├─ select_goal
│  ├─ prepare_task
│  │  ├─ rag.retrieve
│  │  └─ prompt.execute
│  ├─ checkpoint.waiting_user
│  └─ resume_run
│     ├─ exercise.grade
│     ├─ mastery.update
│     ├─ memory.write
│     ├─ review.schedule
│     └─ verification
└─ response / outcome
```

> Span 名称保持低基数，tool / prompt ID 放 attribute。不能把 learner 输入直接拼到 span name，否则指标基数和隐私都会失控。

### Q15：Trace context 如何跨边界传播？

> HTTP 用标准 trace headers 或内部 correlation metadata；LangGraph config 携带 thread、run 和 callback；Tool Gateway 把 trace context 传给 adapter；MCP / HTTP 下游使用标准 header；background job 在 job payload 中保存 trace link 和 episode ID；resume 新建 trace 时用 link 关联旧 trace，而不是伪装成一个永不结束的 span。

### Q16：Checkpoint 暂停数小时，原 Trace 要一直开着吗？

> 不应。长时间开放 span 会破坏时延统计并增加资源占用。等待节点结束当前 run，记录 `waiting_user` 和 checkpoint；resume 创建新 trace / graph run，通过 episode_id、thread_id、checkpoint_id 和 trace link 关联。

### Q17：并行 Tool Calls 如何追踪？

> 每个 call 有独立 span / call ID，共享 parent 或 span link；结果按 call ID 关联，不能依赖完成顺序。fan-in span 记录 partial failures、等待时间和聚合策略。

### Q18：重试应该复用 span 还是建子 span？

> 逻辑 ToolCall 可以有一个父 span，每次 attempt 建子 span，记录 attempt index、error、backoff 和 provider request ID。这样既能看整体调用，也能区分重试成本。业务审计仍只记录一个幂等操作及最终结果，除非每次尝试本身有审计意义。

### Q19：Streaming 如何正确结束 Trace？

> 不能在返回 StreamingResponse 对象时就结束业务 span。应在 generator 完成、错误或 cancellation 时记录 outcome；区分 time-to-first-token、token duration、persist duration 和 post-processing。客户端断线要标记 cancelled / disconnected，而不是 success。

### Q20：Background Job 如何关联原请求？

> Job payload 保存 episode_id、origin trace ID、job ID 和 causation event ID。Worker 创建新 trace，并用 link 指向原 trace；业务结果写回同一 episode 或明确 child episode。不能把 request-scoped span context 对象直接序列化进队列。

### Q21：时间戳足以恢复执行顺序吗？

> 不足。跨进程时钟会漂移，并行事件可能同一时间。应使用每 episode / stream sequence、parent event ID 或逻辑时钟；timestamp 用于展示和耗时，sequence / causation 用于确定顺序。

## 6. 可观测性工程

### Q22：Agent 应关注哪些 Metrics？

#### 系统指标

- request / episode throughput。
- P50 / P95 / P99 end-to-end latency。
- model、tool、DB、checkpoint latency。
- timeout、retry、fallback 和 cancellation。
- token、cost、context length。
- queue depth、worker lease timeout。

#### Agent 质量指标

- task success / verification pass rate。
- tool selection / argument validity。
- schema pass、repair、fallback、review-required rate。
- average steps、loop / no-progress rate。
- evidence coverage / resolution rate。
- Memory write precision、recommendation acceptance。

> 基础设施健康和业务质量必须同时看。模型 200 OK 不代表学习任务成功。

### Q23：什么是高基数问题？

> learner_id、episode_id、prompt text、tool arguments 等取值巨大，不应作为 Prometheus label。它们适合 trace / log attributes。Metrics label 使用 provider、model、prompt_id、status 等受控枚举，并控制版本数量。

### Q24：如何做 Trace Sampling？

> 正常低风险流量可 head sample；错误、长延迟、高费用、verification_failed、高风险工具和用户投诉可 tail retain。业务审计和关键 LearningEvent 不能按 trace sampling 一起丢失。

### Q25：观测平台故障能否让业务失败？

> 一般 telemetry 应 fail-open：Langfuse 不可用不能阻断本地学习。但合规审计可能 fail-closed，例如无法记录高风险审批时禁止外部副作用。必须区分“可选 telemetry”和“业务必需 audit”。

### Q26：如何避免观测系统反过来拖慢 Agent？

> 批量异步上报、有限队列、timeout、熔断、采样和 payload 大小限制；shutdown 时有界 flush。不要在每个 token 同步写数据库，也不要因为 Langfuse 慢让用户请求无限等待。

### Q27：如何设计告警？

> 告警应基于用户影响和 SLO，例如 verification failure 突增、schema repair rate 突增、provider timeout、Memory 写入无证据、checkpoint resume failure、跨 tenant 拒绝。单次模型异常进日志，持续超阈值才告警，避免噪声。

### Q28：如何判断是模型问题还是 Tool 问题？

> 拆 span 与错误 taxonomy：模型是否选择了正确工具、arguments 是否通过 schema、Gateway 是否允许、provider 是否成功、output 是否有效、后续 verifier 是否通过。没有分层，只看到最终 500 无法归因。

## 7. 可追踪性与业务审计

### Q29：什么叫“端到端可追踪”？

> 从用户输入开始，能沿 episode 找到 TaskSpec、Context、Graph Run、Prompt、Tool、Evidence、Domain Write、Verification 和最终响应；从任何一个 Memory 或 Mastery 结果也能反向找到产生它的 attempt 和 episode。

### Q30：为什么只记录成功路径不够？

> 真正难排查的是未发生的动作。Trace 要能区分：节点没被路由、被 policy 拒绝、输入缺失、执行失败、结果无效或被 verifier 否决。否则“没有 Memory record”无法判断是正常跳过还是丢写。

### Q31：状态变化如何审计？

> 记录 actor、operation、target、before / after 或 delta、reason、evidence、policy、idempotency key 和 timestamp。对于大对象可保存版本与 hash。审计记录与业务写最好同事务或通过 outbox 保证，不应依赖异步 trace 恰好成功。

### Q32：删除 Memory 后审计怎么办？

> 用户数据删除权与审计保留要分层。业务内容按策略删除或匿名化；审计可能只保留不可逆 hash、操作类型和法律允许的最小元数据。不能为了审计永久保留原始敏感内容。

### Q33：为什么要记录 Policy Decision？

> 相同输入在不同风险策略、用户 scope 或 feature flag 下可能不同。只记录 ToolCall 不知道为什么允许。Policy Decision 应包含 policy version、rules matched、allow / deny / approval_required 和可信上下文摘要。

### Q34：如何追踪 Fallback？

> 记录 primary provider、失败类型、fallback policy、目标 provider、语义差异和最终结果。不能只把 fallback 后的 success 当正常 success，否则质量下降和主 provider 故障会被隐藏。

### Q35：Audit Log 可以修改吗？

> 理想上 append-only，通过数据库权限、WORM 存储或签名链提高完整性。纠正错误时追加 correction event，不覆盖原记录。普通 trace 可以按保留策略删除，但关键审计需满足组织要求。

## 8. 可解释性与 Evidence

### Q36：Agent 的解释应该包含什么？

#### 推荐解释对象

```json
{
  "decision": "retry_with_hint",
  "reason_code": "low_mastery_after_spelling_error",
  "summary": "本题拼写错误且当前掌握度偏低，建议带提示重试。",
  "evidence_refs": [
    {"type": "exercise_attempt", "id": "..."},
    {"type": "mastery_state", "id": "..."}
  ],
  "policy": {"id": "recommendation_policy", "version": "v3"},
  "confidence": 0.82,
  "limitations": ["仅有最近两次作答证据"]
}
```

> 对用户展示 summary，对开发者展示 codes、evidence、policy 和 trace links。不同受众看到不同层级。

### Q37：EvidenceRef 应至少包含什么？

> type、stable ID、confidence、reason、used_by 和必要 metadata。它应能通过 Resolver 找回证据或明确显示已过期 / 已删除，不能只保存一段不可解析字符串。

### Q38：Evidence 与 Context 有什么区别？

> Context 是模型或节点可见的信息集合；Evidence 是被某个决策明确引用、可追溯的依据。放进 prompt 的十段 RAG chunk 不代表十段都成为最终推荐证据。

### Q39：为什么“模型说因为 X”不等于真实解释？

> 模型可能事后合理化，生成理由不一定对应实际 feature、policy 或调用路径。可靠解释要由 Harness 从实际输入、规则、版本和证据生成，再允许模型润色表述，但不得改变 reason code 和引用。

### Q40：如何解释 LLM 参与的非确定决定？

> 记录 prompt / model version、结构化输出、confidence、候选项、validation 和 policy gate；将模型建议与最终业务决策分开。例如模型建议 `grammar_issue`，schema 通过，但 policy 因置信度低转 `review_required`。解释应同时展示两层。

### Q41：是否应该保存 rejected alternatives？

> 对高价值推荐有帮助，但要控制大小。保存 top alternatives、score、主要拒绝 reason，而不是完整隐藏推理。这样可以回答“为什么推荐 A 而不是 B”，也便于离线评估。

### Q42：什么是 Counterfactual Explanation？

> 告诉用户什么条件变化会导致不同结果，例如“再连续答对两次后会从提示重试切换为延后复习”。它应基于真实 policy threshold，不能由模型随意编造。

### Q43：Confidence 应如何解释？

> 先说明它代表什么：模型分类置信、证据完整度还是业务估计。不同来源不能混成一个数字。要做校准，观察 0.8 的预测是否约有 80% 正确；否则 UI 上展示小数只是假精确。

### Q44：用户可解释和工程可解释有什么区别？

> 用户需要简洁、可行动和隐私友好的理由；工程人员需要版本、输入摘要、状态 diff、tool / prompt / policy 和 failure taxonomy；审计人员需要 actor、授权与不可变记录。一个万能 explanation payload 往往过度暴露或信息不足。

## 9. Verification：从“执行完成”到“任务完成”

### Q45：为什么 Agent 需要 VerificationReport？

> 模型或图跑到 END 只说明执行停止，不说明目标完成。VerificationReport 根据 TaskSpec success criteria 和 required checks 检查必需动作、证据和业务结果，并决定 completed、warning 或 failed。

### Q46：Process Check 与 Outcome Check 有什么区别？

> Process check 验证是否调用评分、写 Memory、安排 Review；Outcome check 验证分数范围、推荐是否合理、用户目标是否满足。只检查流程容易“步骤全跑但结果错”，只检查结果又无法保证合规路径。

### Q47：Critical、Warning、Info 怎么设计？

> Critical 失败不能宣告成功，例如没有答案却更新 Mastery；Warning 表示可降级完成，例如总结文案缺失；Info 只记录覆盖度。Severity 应由受版本控制的 policy 定义，不应由模型临时决定。

### Q48：LLM-as-a-Judge 可以作为最终 verifier 吗？

> 可以评估开放文本质量，但不应单独验证权限、工具执行、金额、状态写入等确定性事实。使用时要固定 rubric、保存 judge model / prompt version、做人工校准、防 self-preference，并与 deterministic checks 组合。

### Q49：Verification 失败后怎么办？

> 根据错误进入 retry、compensation、waiting_user、manual_review 或 verification_failed。不能只记录红灯然后仍返回 completed。Verifier 本身也要可观测，并区分“检查失败”和“检查系统故障”。

### Q50：Verification 是否会和业务代码重复？

> 它不应重新实现所有业务逻辑，而应检查可观测事实与不变量。数据库约束保证写入正确，Verifier 检查 episode 是否产生了需要的记录、值域和证据。二者是 defense in depth。

## 10. 隐私、安全与数据治理

### Q51：Trace 中最容易泄露什么？

> system prompt、用户消息、RAG 文档、tool arguments / results、API token、数据库 URI、learner PII、模型原始输出和异常 stack。观测系统经常比业务数据库权限更宽，因此必须单独威胁建模。

### Q52：如何做 Redaction？

> 在进入观测 SDK 前做结构化字段级过滤；secret 永不记录；PII 按用途 hash / mask；大文本保存 hash 和受控 reference；错误 stack 过滤 header / URL query。不能只在展示 UI 打码，因为原始数据已经离开进程。

### Q53：数据保留如何设计？

> 按数据类别设置 TTL：高体量 token trace 短期；聚合 metrics 长期；业务审计按法规；用户内容支持删除；错误样本经过脱敏后进入 eval set。环境区分 dev / staging / prod，禁止生产数据无授权复制到本地。

### Q54：Debug Console 有哪些风险？

> 它能跨 episode 查询内部状态、prompt hash、tool error 和 evidence，属于高权限入口。应默认关闭、强认证、网络隔离、learner scope、审计查询行为，并避免 raw prompt / output。仅靠前端隐藏菜单不是安全边界。

### Q55：Trace ID 可以暴露给用户吗？

> 可以提供不可枚举的 support reference，但内部查询仍需授权。不能让知道 trace ID 的人直接读取 trace；也不要把 PII 编进 ID。

### Q56：Prompt Injection 会污染可解释输出吗？

> 会。恶意文档可能诱导模型生成“可信理由”。因此 explanation reason code、evidence refs 和 policy 必须由 Harness 生成或验证；外部内容来源清晰标记，不允许文档文本决定授权和审计字段。

## 11. 测试、评估与回归

### Q57：如何测试 Observability？

> 使用 fake exporter / in-memory collector，断言 span 名称、parent / link、status、关键 attributes 和 redaction；观测关闭时业务仍成功；collector timeout 不拖垮请求；shutdown 有界 flush。不能只人工打开 UI 看一次。

### Q58：如何测试 Trace 完整性？

> 为关键 scenario 定义 expected milestones，而不是固定所有 span 顺序。比如 Daily Lesson 必须包含 task_prepared、answer_received、graded、mastery_updated、verification；并行子 span 顺序允许变化，但 call IDs 和 parent links 必须正确。

### Q59：如何测试解释忠实度？

> 改变输入证据并断言 reason code / recommendation 按 policy 变化；删除 evidence 时解释必须降级并显示 limitation；随机抽样让人工核对引用是否真实支持结论；禁止 explanation 引用未使用的 context。

### Q60：如何测试审计不可丢？

> 在业务写入与 audit 写入之间注入故障；若 audit 是强制要求，事务必须整体 rollback 或 outbox 可靠补发；重复消费不产生重复审计；数据删除后符合保留策略。

### Q61：Simulation 与 Trace 怎么结合？

> Scenario 不只断言 API 输出，还检查 episode events、tool calls、evidence 和 verification。失败报告链接到 trace；baseline 比较关键行为指标，如 repair rate、步骤数和 Memory 写入，而不是只对最终字符串做 snapshot。

### Q62：如何避免 Baseline 掩盖回归？

> Baseline 更新必须经过行为评审；区分 intentional change 与 regression；保留变更理由和受影响 scenario；不能因为 prompt 改动导致失败就自动重录。

### Q63：Explainability 有哪些指标？

- explanation coverage。
- evidence resolution rate。
- unsupported citation rate。
- reason code consistency。
- human agreement / correction rate。
- confidence calibration。
- user action / appeal rate。

> “生成了 reason 字段”不代表解释质量高。

## 12. 生产排障题

### Q64：用户说“系统为什么突然推荐语法课”，怎么查？

#### 推荐路径

1. 用 learner / episode 找到 recommendation event。
2. 查看 reason code、policy version 和 evidence refs。
3. 解析对应 ExerciseAttempt、错误类型和 Mastery state。
4. 查看 PromptExecution 是否 repair / fallback / low confidence。
5. 查看 ToolCall 是否失败后降级。
6. 查看最近部署、prompt、policy 或 catalog revision。
7. 对照 VerificationReport 和相同 persona simulation。

> 如果只能翻日志关键词，说明 Harness 还没有形成决策 provenance。

### Q65：Token Cost 突然翻倍，如何定位？

> 按 prompt_id / version、model、route、tool result size 和 continuation count 分组；查看 context / completion token 分布；找新加入的大 Resource、循环或 fallback；对比部署前后的 trace。不要先猜是模型涨价。

### Q66：Memory 写入数量突然下降，怎么判断是否故障？

> 同时看 Memory candidate rate、schema failure、review_required、evidence missing、policy reject 和真正无可写事件。数量下降可能是精度提升，不能只对写入 count 告警。

### Q67：Trace 显示 Tool 成功，但业务表没有记录，可能是什么？

> Tool provider 返回成功后事务 commit 失败；Tool span 结束过早；tool result 只是 dry-run；幂等命中旧结果；写入在后台尚未完成；trace 与 episode 关联错。需要把 tool execution、domain write 和 transaction outcome 分开记录。

### Q68：Verification 通过但用户结果明显错误，说明什么？

> Checks 可能只覆盖流程没有覆盖 outcome，evidence 本身错误，policy threshold 不合理，或 verifier fail-open。应把这个案例加入 eval / simulation，补 outcome check，而不是只改用户文案。

### Q69：观测平台完全不可用时系统应该怎样？

> 普通学习继续，本地业务 event 和必要 audit 仍写；telemetry exporter 限时失败并计数；高风险动作若依赖强审计则暂停；恢复后可从 outbox 补发允许补发的数据。不能无限缓存 raw prompt 导致内存爆炸。

## 13. BinnAgent 当前实现怎么讲

### Q70：BinnAgent Harness 的主数据链是什么？

```text
TaskSpec
→ AgentEpisode
→ LearningEvent[]
→ PromptExecutionRecord[]
→ ToolCallRecord[]
→ EvidenceRef[]
→ VerificationReport
→ Episode status
→ EpisodeTraceView / Dev Console
```

> TaskSpec 定义 objective、allowed tools、success criteria 和 verification policy；Episode 聚合一次任务；Event 记录领域里程碑；Prompt / Tool 记录决策与执行；Evidence 支撑 Mastery、Memory 和 Recommendation；Verification 决定完成状态。

### Q71：Langfuse 与本地表如何分工？

> Langfuse 是模型调用观测来源，保存 raw prompt / output、token、latency、cost 和 trace UI；本地 PromptExecutionRecord 只保存业务索引、schema / repair / fallback / decision、hash 和 Langfuse references。这样减少原始敏感内容重复存储，同时本地仍能回答输出是否被接受。

### Q72：为什么 Langfuse 关闭时业务仍能运行？

> `observe()` 在未配置或不可用时 yield None，业务调用不依赖 observation 对象。这是 telemetry fail-open。PromptExecution 本地记录仍可写，但 Langfuse trace / observation ID 为空。

#### 追问：这是否意味着完全无观测？

> 不是。仍有 Episode、Event、ToolCall、PromptExecution 和 Verification；只是缺少 raw model span、token、latency 等外部观测。Readiness / dashboard 应显示 tracing disabled，避免误以为数据完整。

### Q73：EpisodeTraceView 当前如何聚合？

> 按 episode 查询 LearningEvent、ToolCallRecord、PromptExecutionRecord 和最新 Checkpoint，附上 VerificationReport；从 Event payload 收集 EvidenceRef，并按 source_module / tool_name 聚合 node summaries，再生成 graph_run 调试投影。

### Q74：当前 node summary 真的是 LangGraph 节点 trace 吗？

> 不完全是。`node_summaries_from_trace()` 用 event.source_module、tool_name 和 prompt.source_module 做 Counter 聚合，名称可能是模块或工具，不一定等于真实 LangGraph node，也没有 parent、duration 和顺序。面试时应称为“业务聚合 summary”，不能夸大为完整 span tree。

### Q75：当前 graph_run 的 Langfuse trace ID 有什么局限？

> 它从 prompt executions 中取第一个非空 trace ID，未必就是整个 graph run 的 root trace。更严谨的模型应在 Episode / GraphRun 直接保存 root trace ID，每个 PromptExecution 保存 observation ID 和 parent trace 关系。

### Q76：当前 LearningEvent 排序有什么风险？

> 查询按 occurred_at、created_at 排序，没有 episode-scoped sequence。并行或相同时钟精度下顺序可能不稳定，也没有直接 causation edge。可以增加 sequence、causation_event_id 和 schema_version，并用数据库约束保证递增或使用有序事件写入器。

### Q77：`tool_call_ids` JSON 列表和 ToolCallRecord 外键同时存在有什么风险？

> 它是冗余索引：ToolCallRecord 已按 episode_id 关联，Episode 又维护 ID list。并发 append 或事务失败可能不一致。可以以关联表为真相，按需查询；若保留快照列表，应明确由数据库 trigger / transaction 维护和校验。

### Q78：当前 Verification 状态映射有什么 fail-open 风险？

> `status_for_verification_report()` 只把 `failed` 映射为 verification_failed、`warning` 映射 warning，其他未知或 malformed status 默认 completed。生产应对未知 status fail closed 或至少 completed_with_warnings，并先用 VerificationReport schema validation。

### Q79：当前 Observability metadata 有什么准确性风险？

> `observe_langgraph_run()` metadata 和 tags 固定写 provider=ollama、local_model=True，但当前 ModelRouter 可能选择 LongCat、DeepSeek 或其他 provider。错误标签会污染成本和质量分析。应从实际 model policy / resolved provider 注入 attributes，而不是硬编码。

### Q80：旧 AgentRun / AgentEvent / ToolCall / ModelCallLog 与新 Episode Runtime 并存怎么解释？

> 代码中存在早期 run-centric models 和后来的 episode-centric AgentEpisode / LearningEvent / ToolCallRecord；Prompt governance 又明确不再维护完整本地 ModelCallLog。应标记 legacy 与 active schema，完成读写路径审计和迁移，避免同一个概念两套真相。面试中主动说清演进历史比假装架构一次成型更可信。

### Q81：当前 Evidence 聚合有什么改进空间？

> `collect_evidence_refs_from_events()` 会收集所有 event payload 中的 refs，但没有全局去重、解析实体是否存在、权限和过期状态。下一步应按 `(type,id)` 去重，使用 EvidenceResolver 返回 found / source / title，并在解释和 Verification 中区分引用存在与证据有效。

### Q82：Debug API 当前安全边界是什么？

> Debug API 默认关闭并要求 token / allowed origin，Prompt Debug 不返回 raw prompt 和 raw output。这减少了暴露面。但 origin 不是认证，生产仍需网络隔离、强身份和审计；runtime episode 查询也必须做 learner ownership，不能只知道 UUID 就访问。

### Q83：如果用两周升级 Harness 可观测性，你怎么排优先级？

第一阶段统一语义和关联：

1. 明确 active runtime schema，标记或迁移 legacy AgentRun / ModelCallLog。
2. 增加 GraphRun 实体或字段，直接保存 root trace ID、attempt、status。
3. LearningEvent 增加 sequence、schema_version、causation_id、actor。
4. 统一 request / episode / thread / graph run / prompt / tool 的 context propagation。

第二阶段提高解释忠实度：

5. EvidenceRef 去重并接 EvidenceResolver。
6. Recommendation / Memory / Mastery 输出统一 reason_code、policy version、evidence 和 limitation。
7. VerificationReport schema 强校验，未知 status fail closed。
8. Tool / policy / catalog / prompt / model versions 纳入 trace。

第三阶段生产治理：

9. 接 OpenTelemetry 或标准 trace bridge，Langfuse 专注 LLM observations。
10. 修复硬编码 provider tags，增加 token / cost / first-token metrics。
11. 实施 redaction、sampling、TTL 和 debug audit。
12. 用 restart、stream cancel、parallel tool、fallback、observability outage simulations 验证。

## 14. 系统设计题：设计一个可解释的客服 Agent Harness

可以按以下顺序回答：

1. 定义 TaskSpec：目标、允许工具、风险、成功标准。
2. 创建 Episode，生成 request / trace / run correlation。
3. 用户意图、RAG、Tool、审批和回复分别建 span。
4. CRM 查询和订单操作经过 Tool Gateway，记录 spec / policy / approval。
5. 每个知识引用生成 EvidenceRef，最终答案只引用实际使用证据。
6. 退款建议生成 reason code、policy version、金额阈值和 alternatives。
7. 高风险退款由 human approval，审计与业务写同事务或 outbox。
8. Verification 检查身份、订单 ownership、金额、审批和回复引用。
9. Episode 结束后输出用户解释与内部解释两个视图。
10. Metrics 监控任务成功、转人工、错误退款、工具失败、证据覆盖和成本。
11. Trace 短期保留，审计长期最小化保留，PII 预先脱敏。
12. Simulation 覆盖 prompt injection、越权订单、重复退款和 provider timeout。

## 15. “深入做过”才容易回答的快问快答

### 1. Trace ID 能否作为 Episode ID？

不建议。Episode 是业务实体，可能关联多个恢复和重试 trace。

### 2. 有完整 Trace 是否等于可解释？

不等于，还需要 evidence、policy 和 decision provenance。

### 3. 有 LearningEvent 是否等于 Event Sourcing？

不等于，除非事件是状态权威来源并支持完整重放。

### 4. Audit 是否可以采样？

关键安全和业务审计通常不能；telemetry trace 可以采样。

### 5. Prompt 原文是否必须保存到业务库？

不必须，可以保存版本、hash 和受控观测引用，降低隐私风险。

### 6. Hash 是否等于脱敏？

不完全是，低熵数据可被枚举，且 hash 仍可能属于可关联数据。

### 7. 等待用户数小时是否保持 span 打开？

不应；结束 run，resume 建新 trace，用 episode / checkpoint 和 span link 关联。

### 8. 并行 span 可以按结束时间推导因果吗？

不能，使用 parent / link / causation ID。

### 9. `completed` 是否代表任务成功？

只有 Verification 通过后才应代表业务成功；图到 END 不够。

### 10. LLM 生成的理由是否可信解释？

不能单独信任，必须由真实 evidence 和 policy 校验。

### 11. LLM Judge 可以验证授权吗？

不可以，授权必须是确定性检查。

### 12. Observability 故障是否总是 fail-open？

Telemetry 一般是；强制 audit 不可用时高风险动作可能需要 fail-closed。

### 13. learner_id 适合做 metric label 吗？

不适合，高基数且有隐私风险。

### 14. Tool span success 是否代表数据库 commit success？

不一定，必须单独记录 domain write / transaction outcome。

### 15. Fallback success 是否应该计为普通 success？

不应完全合并，要保留 degraded / fallback 维度。

### 16. Debug Console 隐藏在前端是否足够？

不够，后端必须强认证、授权和网络隔离。

### 17. EvidenceRef 存在是否代表证据有效？

不代表，还要 resolve、校验 ownership、内容和过期状态。

### 18. 时间戳能否保证并行事件顺序？

不能，使用 sequence 和 causation。

### 19. Trace 可以当业务数据库吗？

不能，采样、过期和可用性语义都不同。

### 20. 可复现是否要求模型逐字输出相同？

通常不要求，应复现配置和行为分布，确定性业务结果与不变量必须一致。

## 16. 容易让面试官扣分的回答

### “可观测就是把所有 Prompt 和 Output 打日志。”

这会制造隐私、成本和检索问题，也缺少 metrics、span hierarchy 和业务语义。

### “接了 Langfuse，所以 Agent 可解释。”

Langfuse 提供模型调用观测，不自动生成忠实的业务解释。

### “模型会告诉我们为什么这样做。”

模型可能事后合理化。解释必须绑定真实 evidence 和 policy。

### “Graph 跑完就是任务完成。”

执行停止不代表 success，需要 Verification。

### “为了可追踪，所有原始内容永久保存。”

违反数据最小化，扩大敏感面和成本。

### “Trace 丢了没关系，数据库里有结果。”

普通 telemetry 可以丢，但没有业务 events / audit 就无法解释高风险状态变化。

### “所有 ID 都用 user_id 关联就行。”

会混淆用户、会话、任务、执行尝试和调用，无法处理并发和恢复。

### “按 timestamp 排序就是真实轨迹。”

并行、时钟漂移和重试会让时间顺序不等于因果顺序。

### “BinnAgent node summaries 就是完整 LangGraph trace。”

当前只是按 source / tool / prompt 聚合的业务视图，没有完整 parent 和 span timing。

### “BinnAgent 只有一套 Runtime 数据模型。”

当前有历史 run-centric 和 active episode-centric 模型，需要明确治理和迁移。

## 17. 五分钟项目讲稿

> BinnAgent 的 Agent Harness 目标是把一次学习任务从黑盒回答变成可追踪、可验证的 Episode。TaskSpec 先定义目标、允许工具、成功标准和 VerificationPolicy；运行时创建 AgentEpisode，所有 LearningEvent、ToolCall、PromptExecution、Checkpoint、Evidence 和 Verification 都关联到 episode。
>
> 我把可观测、可追踪和可解释分开。Langfuse 负责模型层观测，包括 raw prompt / output、token、latency 和 trace；本地 PromptExecutionRecord 不重复存 raw 内容，只存 prompt version / hash、schema、repair、fallback、decision 和 Langfuse reference。这样即使 Langfuse 关闭，业务仍能运行并保留结构化决策索引。
>
> 可追踪性由 EpisodeTrace 聚合：它串起 LearningEvent、ToolCall、PromptExecution、Checkpoint 和 Verification。比如用户提交答案后，会看到 answer_received、exercise_graded、mastery_updated、memory_written、review_scheduled 和 recommendation。没有答案时，相关副作用事件不能出现，这既是 trace 事实，也是 simulation 的业务不变量。
>
> 可解释性不是让模型展示思维过程，而是 EvidenceRef 加 Policy Decision。推荐下一步练语法时，系统应引用具体 ExerciseAttempt、错误类型和 Mastery state，记录 reason code、policy version、confidence 和 limitation。VerificationReport 再检查必需步骤和证据，critical 失败就进入 verification_failed，而不是因为图跑到 END 就 completed。
>
> 当前实现也有边界。node summaries 只是按 source module 聚合，不是完整 LangGraph span tree；graph run 的 Langfuse ID从 prompt record 推断，不一定是 root trace；LearningEvent 没有单调 sequence 和 causation ID；旧 AgentRun / ModelCallLog 与新 Episode Runtime 仍并存；provider metadata 还有硬编码 Ollama 的准确性问题。这些我会按统一 schema、关联 ID、EvidenceResolver、严格 Verification 和标准 trace propagation 的顺序改进。
>
> 最终我判断 Harness 做得好不好，不看埋点数量，而看能不能回答五个问题：这次任务目标是什么；实际经过了什么；为什么做这个决定；结果是否满足成功标准；如果失败，能否稳定复现并防止同类回归。

## 18. 面试前最终自检

你应该能不看文档回答：

- Agent Harness 与 LangGraph / Langfuse 的关系。
- Observability、Traceability、Explainability、Audit、Reproducibility 的区别。
- Episode、Thread、Trace、Run、Prompt、Tool、Evidence ID 如何关联。
- logs、metrics、traces、events 的不同用途。
- checkpoint / resume、parallel、streaming、background job 如何传播 trace。
- 为什么不保持等待数小时的 span。
- telemetry fail-open 与 mandatory audit fail-closed 的区别。
- 为什么 explanation 不能依赖模型自述或 Chain of Thought。
- EvidenceRef、Policy Decision、VerificationReport 如何组合。
- process check、outcome check、critical / warning 的区别。
- 如何做 redaction、sampling、retention 和 debug access。
- BinnAgent 当前 Harness 已实现什么、哪些投影可能不准确、如何升级。

## 19. 相关文档

- [Agent Runtime / Harness Interview Brief](agent-runtime-harness.md)
- [AI Agent、Tools 与 Function Calling 面试指南](AI-Agent-Tools-Function-Calling面试指南.md)
- [LangGraph 深度面试题、参考回答与压力追问](LangGraph深度面试题与追问.md)
- [Prompt 工程经验](Prompt工程经验.md)
- [Prompt Execution Governance](../architecture/prompt-execution-governance.md)
- [Evaluation 与 Observability](../architecture/07-evaluation-observability.md)
- [Verification Runtime Audit](../architecture/verification-runtime-audit.md)
- [Simulation / Evaluation Audit](../architecture/simulation-evaluation-audit.md)

