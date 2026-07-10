# 14. Expression Lab

> 状态：完整功能已实现，等待用户体验验收  
> 产品规格：[Expression Lab 产品与技术规格](../project/expression_lab_product_spec.md)

## 1. 定位

英语表达实验室（Expression Lab）用于把中文表达意图、英文草稿、群聊学习线索、好句或词汇/语法学习目标，转换成可比较、可练习、可确认保存、可追踪的英语学习界面。

它遵循三层边界：

```text
稳定产品外壳
+ 经过校验的 Expression UI DSL
+ 由系统执行且需要确认的学习动作
```

Expression Lab 不替代 AI 对话，不生成全局导航，不允许模型直接访问 API 或数据库，也不自动把候选内容写入长期学习资产。

## 2. 完整用户闭环

```text
Explore / 群聊学习线索 / 手动输入
→ 选择输入类型、场景、风格、水平和是否练习
→ 创建 generating 会话
→ PromptExecutor 生成并校验 expression_ui.v1
→ 比较表达、查看结构、完成练习
→ 用户逐项确认保存好句、词汇或语法点
→ 写入 Attempt、LearningEvent、Memory 与后续推荐
→ 完成会话，并在适用时更新来源线索状态
```

退出页面不会丢失会话。重新打开时，前端通过会话详情恢复 UI、动作和练习状态。删除会话会清除会话本身及其动作、尝试和事件，但不会隐式删除用户已经确认保存的长期资产。

## 3. 产品入口

- Explore 提供正式、`ready` 的“英语表达实验室”能力，主分类为写作，兼顾口语表达场景。
- 群聊线索中的 `expression_gap`、`grammar_error`、`good_sentence`、`desired_vocabulary` 和 `desired_grammar` 以“打开表达实验室”为主操作。
- 学习中心只提供辅助入口或待处理数量，不增加一级主卡。
- 页面支持完全脱离群聊线索的手动输入。

全局主导航保持不变；Expression Lab 是 Explore 下的学习工作区，不是新的一级导航。

## 4. 后端边界

后端模块负责：

- 会话、动作、尝试和事件持久化；
- learner 与 source signal 所有权校验；
- PromptExecutor 调用、PromptExecutionRecord 和模型元数据记录；
- DSL schema 校验、JSON repair、未知 block 隔离和 fallback；
- 系统动作白名单、确认、幂等和业务写入；
- 练习结果到 ExerciseAttempt、LearningEvent、Memory 和推荐的桥接；
- 完成与删除状态转换。

模型只负责提出学习内容、block 和候选动作。客户端只能提交该 action 定义在 `editable_fields` 中的字段；后端完成字段白名单、类型和长度校验后再合并到服务端持久化的候选 payload。客户端不可修改 `action_type` 或任何非可编辑字段，服务端始终根据会话中的 `action_id` 解析并执行动作。

### 4.1 API

| 方法 | 路径 | 作用 |
|---|---|---|
| `POST` | `/api/learners/{learner_id}/expression-lab/sessions` | 创建 `generating` 会话 |
| `GET` | `/api/learners/{learner_id}/expression-lab/sessions` | 恢复最近会话 |
| `GET` | `/api/learners/{learner_id}/expression-lab/sessions/{session_id}` | 获取当前 UI、动作、尝试和证据 |
| `POST` | `/api/learners/{learner_id}/expression-lab/sessions/{session_id}/regenerate` | 重新生成整份学习界面 |
| `POST` | `/api/learners/{learner_id}/expression-lab/sessions/{session_id}/blocks/{block_id}/regenerate` | 只重新生成指定 block |
| `POST` | `/api/learners/{learner_id}/expression-lab/sessions/{session_id}/attempts` | 提交 micro practice 答案 |
| `POST` | `/api/learners/{learner_id}/expression-lab/sessions/{session_id}/actions/{action_id}` | 确认并执行白名单动作 |
| `POST` | `/api/learners/{learner_id}/expression-lab/sessions/{session_id}/complete` | 完成会话 |
| `POST` | `/api/learners/{learner_id}/expression-lab/sessions/{session_id}/events` | 记录 block 浏览、复制等客户端学习事件 |
| `DELETE` | `/api/learners/{learner_id}/expression-lab/sessions/{session_id}` | 删除会话及会话内记录 |

所有 session、block、action 和 attempt 查询都必须同时限定 `learner_id`。跨 learner 访问统一返回 403 或作用域内 404，且不得泄露资源是否存在。

### 4.2 数据

核心表为：

- `expression_lab_sessions`：输入、来源、状态、UI spec 和 prompt/model 元数据；
- `expression_lab_actions`：候选动作、确认状态和最终资产引用；
- `expression_lab_attempts`：block/question 答案、分数、反馈和尝试序号；
- `expression_lab_events`：会话创建、生成、查看、复制、练习、保存和完成事件。

外键使用具名约束；会话删除级联清理会话内数据。动作键和练习尝试序号具有数据库唯一约束，以抵御重复点击和并发重放。

## 5. Expression UI DSL

顶层版本固定为 `expression_ui.v1`。服务端覆盖模型返回的 session/source/intent 身份字段，避免模型伪造会话或来源。

第一版支持完整的十种 block：

1. `expression_variants`
2. `tone_spectrum`
3. `sentence_diff`
4. `pattern_diagram`
5. `usage_comparison`
6. `vocabulary_focus`
7. `grammar_focus`
8. `micro_practice`
9. `transfer_builder`
10. `sandbox_widget`

允许的系统动作：

- `save_writing_phrase`
- `save_vocabulary`
- `save_grammar_point`
- `create_practice`
- `copy_expression`
- `dismiss_suggestion`
- `mark_completed`

未知 block 不得导致整页崩溃：校验器将其隔离，已知 block 仍可渲染，会话进入 `partial`。未知动作、缺少确认的持久化动作或被篡改的 action id 必须被后端拒绝。

## 6. 生成与降级

Prompt ID 为 `expression_lab.ui_spec`，版本为 `v1`。它必须注册 `PromptMetadata`、版本化 template、`output_schema`、`model_policy` 和 eval set，并且只能通过 `PromptExecutor` 调用。

降级顺序固定为：

1. 直接通过 JSON schema；
2. 去除围栏或前后说明后进行 JSON repair；
3. 删除不支持的 block，保留其余有效内容；
4. 降级为固定 `expression_variants + micro_practice`；
5. 最终显示受控的纯文本解释卡。

原始异常、堆栈和模型 JSON 不返回给学习者。Prompt eval 至少包含 accepted、repair、fallback 和 rejected 四类离线样例。

## 7. 动作、练习与长期资产

所有保存动作均遵循：

```text
candidate → confirming → saving → saved | failed
```

后端要求显式 `confirmed=true`，对允许编辑的字段完成白名单、类型和长度校验，并根据服务端持久化的动作类型和合并后 payload 执行。重复提交同一动作返回原应用结果，不重复创建资产。

保存结果：

- 好句写入 WritingPhrase，并记录使用场景、语气、模板和来源 session；
- 词汇写入 learner-scoped VocabularyItem/来源信息，执行规范化和去重；
- 语法点写入学习进度或对应语法资产，并保留错误、修正和来源；
- 练习提交同时产生 ExpressionLabAttempt、ExerciseAttempt、LearningEvent 和 Memory 证据，并生成后续推荐。
- `create_practice` 可由学习者选择 1–3 题和练习重点；系统基于当前会话追加针对性练习，不要求重新开始整个会话。

保存的好句会记录 Expression Lab 来源与保存时间。后续群聊消息导入时，只在消息属于当前 learner、发生在保存之后且与已确认表达形成有意义的精确匹配时，记录 `expression_reused` 事件、Memory 证据和复用计数；重复同步保持幂等，本地事件不复制原始群消息正文。

打开来源线索不会自动接受线索。只有用户完成会话并明确触发完成语义后，来源线索才可变为 `accepted` 或 `completed`；不得借此自动保存未确认的候选资产。

## 8. 前端外壳与状态

固定页面由 `PageShell`、`FeatureHero`、`SurfaceCard`、`Button`、`FormField`、`StatusBanner` 和 `ConfirmDialog` 组成。LLM 只能控制 Generated UI 区域内的 block 数据和顺序。

页面状态：`idle`、`generating`、`ready`、`partial`、`error`、`completed`。生成时按 block 展示 skeleton；局部重新生成不闪烁或清空整页。

桌面使用主学习区和 Context / Source 侧栏；平板与移动端将来源区变为 drawer/bottom sheet。移动端系统操作栏固定在底部并预留安全区和内容下边距，不能遮挡练习或把关键操作推离首屏。

所有交互支持键盘和可见焦点；diff 不只依赖颜色；SVG 提供文本替代；dialog/drawer 支持 Escape、焦点陷阱和关闭后焦点恢复；`prefers-reduced-motion` 下关闭非必要动画。

## 9. Sandbox 安全策略

`sandbox_widget` 必须运行在独立 iframe 中：

- 仅设置 `sandbox="allow-scripts"`，禁止 `allow-same-origin`；
- srcdoc 注入 CSP，至少限制 `default-src`、`connect-src`、`form-action`、`frame-src` 和 `base-uri`；
- 清除 `script` 以外非策略允许内容中的 `on*`、`javascript:`、form、nested iframe、object/embed 和外链资源；
- CSS 在 iframe 内隔离，并拒绝 `@import` 和外部 URL；
- 仅接收来源为当前 iframe、结构合法且事件名在白名单内的 `postMessage`；
- sandbox 事件只能更新局部交互或请求系统确认，不能直接调用系统 API；
- 超时后销毁 iframe，支持用户显式重建。

普通 block 不渲染任意模型 HTML/JS。SVG 也必须经过 URL、事件属性和嵌套可执行内容清洗。

## 10. 可观测性

至少记录：

- `session_created`
- `ui_generated`
- `block_viewed`
- `expression_copied`
- `practice_submitted`
- `asset_saved`
- `session_completed`

这些事件用于计算 DSL pass/repair/fallback、生成耗时、render/sandbox/action 错误、复制/收藏/练习/完成率，以及后续真实使用信号。Langfuse 保存原始 prompt/output、token、cost 和 latency；本地 PromptExecutionRecord 只保存 schema/repair/fallback 决策、hash 和 Langfuse 引用。

## 11. 验收矩阵

| 范围 | 必须通过的证据 |
|---|---|
| 中文表达缺口 | 生成语气/场景对比、可复制表达、至少一道练习，确认后可保存资产 |
| 英文草稿修复 | sentence diff、错误解释、语法点与改写练习可用 |
| 好句迁移 | pattern diagram、transfer builder、用户替换预览与造句练习可用 |
| 完整 DSL | 十种 block 均有 schema 与 renderer；未知 block 显示受控 fallback |
| Fallback | accepted、repair、unsupported strip、fixed fallback、rejected/text fallback 均有回归测试 |
| 动作安全 | 后端确认、动作类型白名单、仅 `editable_fields` 可编辑且通过类型/长度校验、重复提交幂等 |
| 所有权 | source/session/action/attempt 全部 learner-scoped，跨 learner 无读写能力 |
| 学习闭环 | attempt 同时写 ExpressionLabAttempt、ExerciseAttempt、LearningEvent、Memory 与推荐证据 |
| 来源线索 | 打开不自动接受；complete 后才按显式语义更新 |
| Sandbox | script/event URL/form/iframe/外链/CSP/postMessage/超时策略均有安全测试 |
| 响应式 | 320px、平板和桌面可用；底部动作不遮挡；来源区按断点切换 |
| 可访问性 | 键盘、焦点、dialog、reduced motion、非颜色提示均可验证 |
| 工程质量 | backend pytest/ruff 与 frontend test/lint/build 全部通过 |

## 12. 交付与验证

完整实现已交付到本地工作区；最终产品体验验收按用户要求由用户执行。出现问题后基于具体场景继续修正，不以缩减规格或回退为最小 MVP 作为处理方式。

需要工程侧复验时可使用：

```bash
.venv/bin/python -m pytest tests/expression_lab tests/api/test_expression_lab.py tests/prompts tests/db/test_migrations.py -q
.venv/bin/ruff check src tests scripts
./scripts/run_learner_simulation.sh --test

cd binnagent-frontend
npm run test
npm run lint
npm run build
```

不得为了隐藏行为回归而更新 simulation baseline。
