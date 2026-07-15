# 精读句子分析 LongCat 重复生成、响应慢且最终 502

## 状态

已修复。

## 现象

精读模式提交“我分析不出来”后，前端等待接近一分钟，最终只显示：

> 句子分析暂时失败。你的作答仍保留在本地，可以直接重试。

后端访问日志对应请求返回 `502 Bad Gateway`，业务数据库中没有留下本次失败的 `PromptExecutionRecord`。

## 现场证据

Langfuse trace `60dbb9bfb50a1344818fdd715cec8580` 记录了同一次业务请求中的两次 LongCat 调用：

| 阶段 | 耗时 | 输入 tokens | 输出 tokens | 结果 |
|---|---:|---:|---:|---|
| 首次生成 | 35.030 秒 | 1544 | 1800 | 输出正好达到任务上限，未形成可接受结构 |
| 自动 JSON repair | 23.884 秒 | 1580 | 1113 | JSON 语法合法，但缺少必填字段 |
| Prompt 总计 | 58.915 秒 | - | 2913 | Schema 校验失败，接口返回 502 |

第二次输出包含 `outcome`、`score`、`teaching`、`selected_can_do_ids`、`error_patterns` 和 `correct_analysis`，但缺少 Schema 要求的 `confidence` 与 `feedback`。校验器首先报告：

```text
$: 'confidence' is a required property
```

因此，这次慢请求不是 90 秒网络 timeout；主要耗时来自过长的首次非流式生成，以及字段不完整后触发的第二次完整生成。

## 根因

1. LongCat 的 OpenAI-compatible client 配置为 `supports_response_format=False`，请求没有原生 JSON response format。
2. `reading.sentence_analysis` Prompt 只要求“符合 JSON Schema”，但模型请求中没有附带实际 Schema。
3. 首次生成允许 1800 tokens，教学内容缺少足够严格的长度约束，现场请求直接打满输出上限。
   LongCat-2.0 默认启用 thinking，推理 tokens 与可见 JSON 共用输出预算；低预算时可能在 JSON 完成前耗尽。
4. Router 过去只检查 JSON 语法；自动 repair 只说“修复成合法 JSON”，没有指出缺少 `confidence` / `feedback`，也没有验证修复结果是否真的通过业务 Schema。
5. “明确不会”与“已有自主分析”共用完整评估输出，NO_ATTEMPT 仍要求生成 score、outcome、错误数组等不必要字段。
6. 前端丢弃后端 `detail`，所有非 2xx 都显示同一个失败提示。

## 修复内容

### 1. 给 LongCat 注入压缩 Schema 契约

`OpenAICompatibleClient` 在 provider 不支持原生 response format、且请求绑定 `response_schema` 时，自动追加压缩 JSON Schema 指令。模型现在能看到完整必填字段、类型、枚举和嵌套结构。

支持原生 response format 的 provider 保持原行为，不重复注入。

### 2. 改为 Schema 错误驱动的定向 repair

`ModelRouter` 在首次响应后执行 Draft 2020-12 Schema 校验，不再把“能 `json.loads()`”等同于业务可接受。

修复请求会携带首个具体错误，例如：

```text
$: 'confidence' is a required property
```

第二次响应再次执行完整 Schema 校验；仍不合格时标记 `repair_failed`，交由 PromptExecutor 生成稳定的 rejected 结果。

### 3. 收紧常规句子分析输出

- `reading.sentence_analysis` 的 `max_tokens` 从 1800 降为 1100。
- feedback、主干、从句、短语、教学步骤和错误模式增加更严格的数量及长度上限。
- Prompt 明确 `confidence`、`feedback` 永远必填，并要求短反馈、最多 4 个教学动作和最多 3 个错误模式。
- 两个句子分析 Prompt 均通过 model policy 向 LongCat 发送 `thinking: {"type":"disabled"}`；该任务是低温结构化抽取与教学编排，不需要默认的深度推理。

仅降低 token 上限会增加截断风险，因此本次同时收紧 Schema 和 Prompt 输出要求。

[LongCat 官方 Chat Completions 文档](https://longcat.chat/platform/docs/api/chat.html)说明 `thinking` 可显式设置为 `enabled` 或 `disabled`；本次不修改其他 Prompt 的推理策略，只对句子分析两条结构化任务关闭 thinking。

### 4. 前端展示可诊断错误

Reading Workshop 保持单次请求和原有 AbortController 隔离，不增加额外网络探测。失败时读取后端状态与 `detail`，区分：

- Schema 输出不完整；
- 请求超时；
- 请求过多；
- 材料保存失败；
- 网络或后端不可达。

所有错误路径继续保留当前句子的本地作答，可直接原地重试。

### 5. NO_ATTEMPT 使用轻量教学 Prompt

新增 `reading.sentence_analysis_no_attempt`：

- 只生成 `confidence`、`feedback`、正确拆解、教学步骤和动态 Can-Do ID；
- `max_tokens=800`；
- 后端确定性补充 `outcome=NO_ATTEMPT`、`score=0` 和 no-attempt 错误模式；
- 不写 production mastery，只进入教学复盘与错误模式沉淀。

这样既减少生成量，也避免让模型在“学习者没有作答”的场景中虚构掌握度判断。

## 回归覆盖

- 不支持 response format 的 provider 会收到压缩 Schema。
- JSON 语法错误会触发定向 repair。
- JSON 语法正确但缺少必填字段也会触发 repair，并携带具体错误。
- repair 后仍缺字段会稳定标记失败。
- 有自主分析时继续更新动态 Can-Do mastery。
- NO_ATTEMPT 返回教学内容、记录教学型错误模式且不更新 mastery。
- 前端 Schema 失败提示明确，且不丢失本地作答。

## 修复后真实 LongCat 验证

验证使用 `PromptExecutor` 直接调用 LongCat，不连接业务数据库，因此不会写入 mastery、Memory 或学习记录。

| 路径 | 调用次数 | LongCat 耗时 | 输入 tokens | 输出 tokens | Schema 结果 |
|---|---:|---:|---:|---:|---|
| NO_ATTEMPT 教学 | 1 | 12.098 秒 | 702 | 467 | passed，无 repair |
| 已自主分析评估 | 1 | 13.276 秒 | 1048 | 460 | passed，无 repair |

NO_ATTEMPT 从现场的 58.915 秒、两次生成、最终 502，降为 12.098 秒、一次生成、直接通过，耗时下降约 79.5%。

## 涉及模块

- `src/providers/openai_compatible.py`
- `src/providers/router.py`
- `src/prompts/schemas.py`
- `src/prompts/registry.py`
- `src/prompts/versions/reading.sentence_analysis.v1.md`
- `src/prompts/versions/reading.sentence_analysis_no_attempt.v1.md`
- `src/api/reading.py`
- `binnagent-frontend/src/pages/ReadingWorkshopPage.tsx`
- `evals/prompts/reading_sentence_analysis_v1.jsonl`
- `evals/prompts/reading_sentence_analysis_no_attempt_v1.jsonl`

## 后续观察项

- 通过 Langfuse 对比修复前后的首次生成时长、输出 tokens、repair rate 和 502 rate。
- 若常规自主分析仍频繁接近 1100-token 上限，再拆分“评估结论”和“教学扩展”，而不是继续盲目降低 token 上限。
- PromptExecutionRecord 当前仍与业务事务共用 session；失败接口回滚时审计记录可能一起丢失，独立审计事务另行治理。
