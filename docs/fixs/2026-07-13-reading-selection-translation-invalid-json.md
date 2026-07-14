# 精读划词翻译收到模型回复但前端仍提示失败

## 状态

待修复。

## 背景

精读“全文选读”支持拖选单词或短语并查看语境翻译。查询顺序为：优先读取共享基础词库；词库未命中或缺少中文义项时，通过 `reading.selection_translation` PromptExecutor 调用默认模型生成语境翻译。

默认模型切换为 LongCat 后，Langfuse 能看到模型已经返回了语义合理的翻译，但前端仍显示：

> 翻译暂时失败，请重新选择后再试。

## 问题表现

本次划选内容为 `ordinary`。Langfuse 记录的 LongCat 原始回复为：

```text
{"translation":"普通的","context_note":"在此句中，ordinary 修饰 things，表示"平常的、不特别的"，强调作者开始关注身边那些容易被忽略的日常事物。","confidence":0.95}
```

从自然语言内容看，翻译、语境解释和置信度都合理；但前端没有展示这些内容，而是进入统一错误状态。

后端访问日志确认对应请求最终返回：

```text
POST /api/learners/{learner_id}/reading-workshop/selection-translation 502 Bad Gateway
```

## 根因分析

LongCat 回复看起来接近 JSON，但不是合法 JSON。`context_note` 字符串内部直接使用了未转义的 ASCII 双引号：

```text
表示"平常的、不特别的"
```

这些引号在实际 JSON 字符串中需要写成 `\"`，或者改用中文引号 `“”`。未转义引号会提前结束 `context_note` 字符串，导致后续内容无法解析。

实际失败链路：

1. LongCat 返回语义正确但 JSON 语法错误的文本。
2. Langfuse 记录模型原始回复。Langfuse 有记录只表示模型调用完成，不表示业务 schema 已通过。
3. OpenAI-compatible client 无法将内容解析为 structured payload。
4. ModelRouter 发起一次 JSON repair 请求；如果修复回复仍不合法，则返回原始失败结果。
5. PromptExecutor 的本地 repair 只能提取 fenced JSON、截取首尾对象并重新执行 `json.loads()`，不能修复字符串内部未转义的引号。
6. `reading.selection_translation` 输出未通过 `ReadingSelectionTranslationOutput` schema，结果被标记为 `rejected`。
7. 阅读接口返回 `502 Selection translation failed schema validation`。
8. 前端只判断 `response.ok`，将所有非 2xx 响应统一映射为“翻译暂时失败，请重新选择后再试”。

## 为什么数据库中可能看不到失败记录

PromptExecutor 会在当前业务数据库会话中写入 `PromptExecutionRecord`。但是阅读接口在结果被拒绝后抛出 HTTP 502，`get_db_session()` 会回滚整个请求事务，因此刚写入的失败执行记录也被回滚。

这会造成观测差异：

- Langfuse 保留模型调用及原始输出。
- API access log 保留 502。
- `prompt_execution_records` 可能没有这次失败，只保留其他已成功提交的记录。

因此，不能用数据库中“最近一条记录为 accepted”推断这次前端请求成功。

## 影响范围

- 共享基础词库命中且已有中文义项时不受影响，因为不会调用模型。
- 基础词库未命中或中文义项尚未生成时，需要调用模型，可能触发此问题。
- 任何 LongCat 结构化输出只要在字符串中生成未转义双引号，都可能遇到同类失败。
- 前端当前无法区分模型超时、网络错误、schema 校验失败和后端异常，用户只能看到统一提示。

## 建议修复

### 1. 升级划词翻译 Prompt

新增 `reading.selection_translation` v2，明确要求：

- JSON 字符串内部禁止使用未转义的 ASCII 双引号。
- 引用词义时使用中文引号 `“”`，或正确输出 `\"`。
- 只返回 `translation`、`context_note` 和 `confidence` 三个字段。

同时更新 `evals/prompts/` 下对应 eval set，加入字符串内部裸引号的回归样例。

### 2. 增加针对固定 schema 的确定性兜底

为划词翻译提供受控 fallback parser。只有明确识别出三个目标字段时才恢复结果，并在恢复后重新执行完整 JSON Schema 校验。不要把任意模型文本直接绕过 schema 写入响应。

### 3. 保留失败执行记录

PromptExecutionRecord 的失败审计不应跟随业务 502 一起回滚。可选方案：

- 使用独立审计会话提交执行记录；或
- 在业务层返回受控错误结果并先提交审计记录；或
- 通过独立事件/队列异步写入失败记录。

需要避免为了保存审计记录而提前提交其他尚未完成的业务写入。

### 4. 改善前端错误反馈

前端应读取后端错误类型，并至少区分：

- 基础词库暂无中文释义且模型生成失败；
- 模型输出格式错误；
- 请求超时或网络错误；
- 选择内容已经变化或不在原句中。

同时保留“重新翻译”按钮，不要求用户重新拖选同一内容。

## 建议回归测试

后端：

- LongCat 返回严格合法 JSON 时，接口返回 200。
- `context_note` 包含中文引号时，接口返回 200。
- 原始回复包含未转义 ASCII 双引号时，受控 fallback 能恢复或返回可识别错误。
- 无法恢复时返回稳定错误码，并保存 rejected PromptExecutionRecord。
- 基础词库已有中文释义时不调用模型。

前端：

- 200 响应展示翻译与语境说明。
- schema 错误显示明确提示并允许原地重试。
- 网络错误仍显示通用重试提示。
- 重试期间不丢失当前划词选择。

## 涉及模块

- `src/api/reading.py`
- `src/prompts/versions/reading.selection_translation.v1.md`
- `src/prompts/registry.py`
- `src/prompts/repair.py`
- `src/prompts/executor.py`
- `src/api/deps.py`
- `binnagent-frontend/src/pages/ReadingWorkshopPage.tsx`
- `evals/prompts/reading_selection_translation_v1.jsonl`

## 验收标准

1. 同一段 `ordinary` 测试材料连续执行多次，不再因解释中的引号返回 502。
2. Langfuse、PromptExecutionRecord、API 状态和前端展示能够对应同一次请求。
3. 模型输出确实无法恢复时，前端展示可理解、可重试的具体错误。
4. 修复不绕过 PromptExecutor、输出 schema 或现有基础词库优先策略。
