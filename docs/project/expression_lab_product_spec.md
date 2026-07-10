# BinnAgent 英语表达实验室（Expression Lab）产品与技术规格

> 文档状态：Draft v1.0  
> 适用项目：BinnAgent  
> 能力 ID：`expression-lab`  
> 内部模块名：`ExpressionLab`  
> 文档目的：定义“按需生成式界面”在 BinnAgent 中的首个用户侧试点能力，并明确产品边界、交互闭环、技术协议、数据结构与验收标准。

---

## 1. 产品概述

### 1.1 产品名称

**中文名称：英语表达实验室**  
**英文名称：Expression Lab**

不使用“表达对话”“AI 表达聊天”“群聊助手”等名称，避免与现有 `AI 对话` 功能混淆。

### 1.2 一句话定义

英语表达实验室把用户的中文表达意图、英文草稿、群聊学习线索或收藏好句，转换成一个按需生成的、可比较、可练习、可保存、可追踪的英语学习界面。

### 1.3 产品定位

它不是另一个聊天页，也不是单纯的 HTML 内容生成器，而是：

```text
稳定的产品外壳
+ LLM 生成的局部学习界面
+ 系统受控的保存和练习动作
```

它重点解决：

- 用户知道中文意思，但不知道英语怎么说；
- 用户写出英文，但不确定语法、语气或自然度；
- 用户看到一个好句，希望理解结构并迁移使用；
- 用户从飞书群聊中产生表达缺口、语法错误、词汇兴趣或好句候选；
- 用户希望把一次临时问题沉淀成长期可复习的学习资产。

---

## 2. 产品目标与非目标

### 2.1 产品目标

1. 将“不会表达”转化为一次完整学习闭环，而不是只给一段文本答案。
2. 通过生成式 UI 呈现不同表达方案、语气差异、结构、易错点和练习。
3. 连接现有 BinnAgent 资产：好句收藏馆、词汇本、语法进度、练习系统、学习画像、群聊学习线索。
4. 记录用户是否完成、是否收藏、是否在后续真实场景中再次使用。
5. 验证“固定产品骨架 + 按需生成局部界面”的 Generative UI 模式。

### 2.2 非目标

- 不替代现有 AI 对话。
- 不生成或改变全局导航、账户、设置、权限和登录页面。
- 不允许 LLM 直接调用任意后端 API。
- 不允许未经隔离的模型 JS 运行在主页面上下文。
- 不自动把所有生成内容写入长期资产。
- 不做完整作文批改、实时语音评分或自由多轮角色扮演。
- 不把它设计成第二个 Explore 页面。

---

## 3. 目标用户与核心场景

### 3.1 目标用户

- 经常在中文和英文之间切换的英语学习者；
- 需要提高写作、口语和群聊表达自然度的用户；
- 使用飞书群作为学习搭子交流场景的用户；
- 已经在 BinnAgent 中积累词汇、语法和好句资产的用户。

### 3.2 核心输入场景

#### 场景 A：中文表达缺口

```text
这个观点太绝对了，英语怎么说？
```

系统生成：

- 不同语气强度的表达；
- 日常、正式、写作场景对比；
- 句型结构；
- 关键词解释；
- 小练习；
- 收藏和沉淀动作。

#### 场景 B：英文草稿修复

```text
I am agree with you.
```

系统生成：

- 原句与修正 diff；
- 错误定位；
- 语法解释；
- 口语/正式表达扩展；
- 改写练习；
- 记录语法点。

#### 场景 C：好句迁移

```text
What matters most is not how fast you learn, but how consistently you practice.
```

系统生成：

- 原句结构高亮；
- 抽象模板；
- A/B 替换器；
- 使用场景；
- 造句练习；
- 加入好句收藏馆。

#### 场景 D：群聊学习线索

来源可以是：

- `expression_gap`
- `grammar_error`
- `good_sentence`
- `desired_vocabulary`
- `desired_grammar`

用户从“群聊学习线索”页面点击后进入表达实验室。

---

## 4. 入口设计

### 4.1 Explore 主入口

在 Explore 中新增一个正式能力：

```text
英语表达实验室
把中文意图、英文草稿或群聊表达变成可比较、可练习、可收藏的英语表达。
```

建议分类：

- 主分类：写作
- 次分类：口语

### 4.2 群聊学习线索入口

对以下线索类型，主操作改为“打开表达实验室”：

- 表达缺口；
- 语法错误；
- 好句候选；
- 需要展开的词汇或语法意图。

不再直接将“接受线索”作为唯一主动作。推荐流程：

```text
查看线索
→ 打开表达实验室
→ 完成理解或练习
→ 用户确认保存哪些资产
```

### 4.3 手动输入入口

表达实验室必须允许用户不依赖飞书或群聊线索，直接输入：

- 中文表达；
- 英文草稿；
- 好句；
- 想学习的词或语法点。

### 4.4 学习中心入口

学习中心不新增一级主卡，可在辅助入口或“最近学习线索”中显示：

```text
英语表达实验室
继续处理 2 条待学习表达
```

---

## 5. 用户流程

### 5.1 标准流程

```text
选择来源或手动输入
→ 选择场景与目标
→ 生成 Expression UI Spec
→ 校验与渲染
→ 用户比较表达 / 查看结构 / 完成练习
→ 用户选择保存动作
→ 写入好句、词汇、语法或练习记录
→ 生成学习事件与后续推荐
```

### 5.2 首次生成前的输入字段

必填：

- 输入文本；
- 输入类型：中文意图 / 英文草稿 / 好句 / 词汇或语法点。

可选：

- 使用场景：日常聊天 / 群聊讨论 / 考试写作 / 正式沟通；
- 目标风格：自然 / 委婉 / 正式 / 简洁 / 有说服力；
- 当前水平；
- 是否需要小练习；
- 来源线索 ID。

### 5.3 生成后操作

用户可以：

- 收藏某个表达；
- 加入词汇本；
- 记录语法点；
- 生成 1–3 道练习；
- 再生成一种语气；
- 复制表达；
- 标记“不适合我”；
- 退出但保留本次临时状态。

---

## 6. 页面布局

### 6.1 稳定页面外壳

固定区域：

```text
PageShell
  Header / Back
  Input Summary
  Generated UI Area
  System Action Bar
  Evidence / Source Drawer
```

固定 UI 由项目代码实现，LLM 不控制：

- 页面标题；
- 返回按钮；
- 生成状态；
- 保存和删除按钮；
- Loading / Error / Empty State；
- API 调用；
- 用户确认；
- 审计和权限。

### 6.2 动态生成区域

LLM 可以决定：

- 模块类型；
- 模块顺序；
- 表达数量；
- 语气对比方式；
- 是否展示结构图；
- 是否展示错误 diff；
- 使用哪种练习；
- 是否展示 SVG 可视化。

### 6.3 桌面布局

```text
┌──────────────────────────────────────────────────────┐
│ Header / Input Summary                               │
├───────────────────────────────┬──────────────────────┤
│ Generated Learning UI         │ Context / Source     │
│                               │ Drawer               │
├───────────────────────────────┴──────────────────────┤
│ System Action Bar                                   │
└──────────────────────────────────────────────────────┘
```

### 6.4 移动端布局

- Generated UI 单列；
- Context / Source 变 bottom sheet；
- System Action Bar 固定在底部；
- 不允许动态 UI 把关键动作推到视口外。

---

## 7. 动态 UI 模块类型

第一版允许以下 block：

### 7.1 `expression_variants`

展示 2–5 个候选表达：

- 文本；
- 中文解释；
- 使用场景；
- 语气标签；
- 自然度；
- 难度；
- 收藏动作。

### 7.2 `tone_spectrum`

展示表达强度或正式度轴：

```text
委婉 ───────── 中性 ───────── 直接
```

### 7.3 `sentence_diff`

用于英文草稿修复：

- 原句；
- 修正句；
- 删除、添加和替换高亮；
- 错误解释。

### 7.4 `pattern_diagram`

句型结构：

```text
I think + [观点] + needs more + [抽象名词]
```

支持 SVG 节点和连线。

### 7.5 `usage_comparison`

对比近义表达：

- meaning；
- register；
- context；
- common collocations；
- avoid_when。

### 7.6 `vocabulary_focus`

展示值得展开的词：

- 词义；
- 搭配；
- 例句；
- 近义词；
- 加入词汇本动作。

### 7.7 `grammar_focus`

展示语法点：

- 规则；
- 错误；
- 修正；
- 最小对比；
- 记录语法点动作。

### 7.8 `micro_practice`

支持：

- 翻译；
- 改写；
- 选择最自然表达；
- 填空；
- 情景选择；
- 造句。

### 7.9 `transfer_builder`

用于好句迁移：

- 模板；
- 可替换槽位；
- 用户输入；
- 动态预览。

### 7.10 `sandbox_widget`

实验性 block，仅用于复杂交互：

- HTML；
- scoped CSS；
- SVG；
- 受限 JS。

必须运行于 iframe sandbox，不能直接进入主 DOM。

---

## 8. Expression UI DSL

### 8.1 顶层结构

```json
{
  "version": "expression_ui.v1",
  "session_id": "uuid",
  "source": {
    "type": "manual | group_learning_signal",
    "source_id": "optional-id"
  },
  "intent": {
    "input_type": "zh_intent | en_draft | good_sentence | learning_target",
    "text": "这个观点太绝对了",
    "context": "group_chat",
    "goal": "polite_disagreement"
  },
  "layout": "tone_spectrum",
  "blocks": [],
  "suggested_assets": [],
  "learning_actions": []
}
```

### 8.2 Block 通用结构

```json
{
  "id": "block-1",
  "type": "expression_variants",
  "title": "更自然的表达",
  "description": "按语气强度比较",
  "data": {},
  "ui": {
    "collapsible": false,
    "emphasis": "primary"
  }
}
```

### 8.3 系统动作结构

LLM 只能提出动作，不直接执行：

```json
{
  "id": "save-expression-1",
  "type": "save_writing_phrase",
  "label": "收藏这个表达",
  "payload": {
    "text": "That claim may be too strong.",
    "chinese_meaning": "这个说法可能有些过强"
  },
  "requires_confirmation": true
}
```

允许的第一版动作：

- `save_writing_phrase`
- `save_vocabulary`
- `save_grammar_point`
- `create_practice`
- `copy_expression`
- `dismiss_suggestion`
- `mark_completed`

---

## 9. 生成式 UI 安全边界

### 9.1 优先级

```text
预置组件 props
> JSON UI DSL
> HTML/CSS/SVG
> 受限 JS
```

能用 DSL 表达的，不允许生成任意 JS。

### 9.2 HTML 与 CSS

必须：

- sanitize；
- CSS scope；
- 禁止外部样式；
- 禁止 iframe 嵌套；
- 禁止 `on*` 事件属性；
- 禁止 `javascript:` URL；
- 禁止任意 form action；
- 图片仅允许项目域、data URI 或代理后的白名单资源。

### 9.3 JS 沙箱

`sandbox_widget` 必须：

- 使用独立 iframe；
- 禁止 `allow-same-origin`；
- 禁止访问 cookies、localStorage、sessionStorage；
- 禁止网络请求；
- 禁止父页面 DOM；
- 仅允许通过 `postMessage` 上报白名单事件；
- 超时自动终止；
- 支持销毁与重建。

### 9.4 权限边界

生成式 UI 不得：

- 直接修改数据库；
- 直接调用任意 API；
- 自动接受学习线索；
- 自动标记用户已掌握；
- 自动发送飞书消息；
- 自动删除或覆盖学习资产。

---

## 10. 后端架构

### 10.1 模块建议

```text
src/expression_lab/
  service.py
  schemas.py
  ui_spec_generator.py
  ui_spec_validator.py
  action_handler.py
  renderer_policy.py
```

### 10.2 API 建议

#### 创建会话

```http
POST /api/learners/{learner_id}/expression-lab/sessions
```

请求：

```json
{
  "input_type": "zh_intent",
  "text": "这个观点太绝对了",
  "context": "group_chat",
  "style": "polite",
  "source_signal_id": null
}
```

响应：

```json
{
  "session_id": "uuid",
  "status": "generating"
}
```

#### 获取生成结果

```http
GET /api/learners/{learner_id}/expression-lab/sessions/{session_id}
```

#### 重新生成局部 block

```http
POST /api/learners/{learner_id}/expression-lab/sessions/{session_id}/blocks/{block_id}/regenerate
```

#### 提交练习答案

```http
POST /api/learners/{learner_id}/expression-lab/sessions/{session_id}/attempts
```

#### 执行系统动作

```http
POST /api/learners/{learner_id}/expression-lab/sessions/{session_id}/actions/{action_id}
```

#### 结束会话

```http
POST /api/learners/{learner_id}/expression-lab/sessions/{session_id}/complete
```

---

## 11. 数据模型

### 11.1 `expression_lab_sessions`

```text
id
learner_id
source_type
source_ref
input_type
input_text
context
style_goal
status
ui_spec_json
model_id
prompt_id
prompt_version
prompt_hash
created_at
updated_at
completed_at
```

### 11.2 `expression_lab_actions`

```text
id
session_id
action_type
payload_json
status
confirmed_by_user
applied_target_type
applied_target_id
created_at
applied_at
```

### 11.3 `expression_lab_attempts`

```text
id
session_id
block_id
question_id
answer_json
score
feedback_json
attempt_number
created_at
```

### 11.4 `expression_lab_events`

```text
id
session_id
event_type
payload_json
occurred_at
```

事件示例：

- `session_created`
- `ui_generated`
- `block_viewed`
- `expression_copied`
- `practice_submitted`
- `asset_saved`
- `session_completed`

---

## 12. 与现有能力的集成

### 12.1 群聊学习线索

输入：

- `expression_gap`
- `grammar_error`
- `good_sentence`
- `desired_vocabulary`
- `desired_grammar`

输出：

- 更新线索状态；
- 保留 source signal 证据；
- 学习完成后可标记 `accepted` 或 `completed`。

### 12.2 好句收藏馆

保存：

- 表达文本；
- 中文含义；
- 使用场景；
- 语气；
- 模板；
- 例句；
- 来源 session ID。

### 12.3 词汇本

可保存：

- 单词；
- 短语；
- 搭配；
- 来源表达；
- 推荐原因。

### 12.4 GrammarPage

可保存或跳转：

- 错误对应语法点；
- 推荐微知识点；
- 针对当前错误生成练习。

### 12.5 练习系统

`micro_practice` 结果写入：

- ExerciseAttempt；
- LearningEvent；
- 学习画像证据；
- 后续推荐。

### 12.6 Explore

新增正式 capability：

```text
feature_id: expression-lab
capability_id: expression_lab
category: writing
status: ready
```

---

## 13. Prompt 与生成策略

### 13.1 Prompt ID

```text
expression_lab.ui_spec
```

版本：

```text
v1
```

### 13.2 模型职责

模型负责：

- 理解用户意图；
- 判断场景和语气；
- 生成表达方案；
- 生成解释、结构和练习；
- 选择合适 block；
- 输出严格 UI DSL。

模型不负责：

- 执行保存；
- 权限判断；
- 操作数据库；
- 生成全局页面；
- 直接发消息。

### 13.3 Fallback

当 DSL 校验失败时：

1. 尝试 JSON repair；
2. 删除不支持 block；
3. 降级为固定 `expression_variants + micro_practice`；
4. 最终降级为文本解释卡。

用户不可看到原始异常或模型 JSON。

---

## 14. 前端组件建议

```text
binnagent-frontend/src/pages/ExpressionLabPage.tsx
binnagent-frontend/src/components/expression-lab/ExpressionInputPanel.tsx
binnagent-frontend/src/components/expression-lab/GeneratedUiRenderer.tsx
binnagent-frontend/src/components/expression-lab/ExpressionVariantsBlock.tsx
binnagent-frontend/src/components/expression-lab/ToneSpectrumBlock.tsx
binnagent-frontend/src/components/expression-lab/SentenceDiffBlock.tsx
binnagent-frontend/src/components/expression-lab/PatternDiagramBlock.tsx
binnagent-frontend/src/components/expression-lab/MicroPracticeBlock.tsx
binnagent-frontend/src/components/expression-lab/SandboxWidget.tsx
binnagent-frontend/src/components/expression-lab/ExpressionActionBar.tsx
```

统一使用现有：

- `PageShell`
- `FeatureHero`
- `SurfaceCard`
- `Button`
- `StatusBanner`
- `ConfirmDialog`
- `LoadingState`
- `ErrorState`
- `EmptyState`

---

## 15. 状态设计

### 15.1 页面状态

- `idle`
- `generating`
- `ready`
- `partial`
- `error`
- `completed`

### 15.2 Block 状态

- `loading`
- `ready`
- `answering`
- `submitted`
- `correct`
- `incorrect`
- `regenerating`
- `unsupported`

### 15.3 资产动作状态

- `candidate`
- `confirming`
- `saving`
- `saved`
- `failed`

---

## 16. 体验与动效

- 生成时使用 block skeleton，不让整页闪烁；
- block 逐个淡入；
- 语气轴和结构 SVG 使用 150–300ms 动效；
- 正确答案轻微 scale / glow；
- 错误答案轻微 shake + 差异高亮；
- 保存成功显示局部状态，不强制全页 toast；
- `prefers-reduced-motion` 下关闭非必要动画；
- 所有交互支持 keyboard focus。

---

## 17. 评估指标

### 17.1 技术指标

- UI DSL schema pass rate；
- JSON repair rate；
- fallback rate；
- 生成耗时；
- block render error rate；
- sandbox timeout rate；
- action execution error rate。

### 17.2 产品指标

- 生成后完成率；
- 表达复制率；
- 表达收藏率；
- 词汇保存率；
- 语法点保存率；
- 小练习完成率；
- 首次正确率；
- 重试后正确率；
- 7 天内复习率；
- 后续真实群聊中再次使用推荐表达的比例。

### 17.3 核心成功信号

```text
用户曾经不会表达
→ 在表达实验室中学习
→ 收藏或练习
→ 后续在真实群聊或写作中使用
```

---

## 18. 验收标准

### 18.1 功能验收

- Explore 中有“英语表达实验室”入口；
- 可手动输入中文意图和英文草稿；
- 群聊表达缺口和语法错误可打开实验室；
- 至少支持 5 种动态 block；
- 可完成至少一种小练习；
- 可保存好句、词汇和语法点；
- 所有保存操作需要用户确认；
- 会话和用户动作可追踪。

### 18.2 生成式 UI 验收

- 模型输出必须经过 schema 校验；
- 未知 block 不导致页面崩溃；
- DSL 失败时能降级；
- HTML/CSS 被清洗和隔离；
- JS 仅在 sandbox 内运行；
- 动态 UI 无法直接调用系统 API；
- 动态 UI 无法访问主页面存储和 DOM。

### 18.3 响应式验收

- 桌面、平板、移动端可用；
- 移动端底部操作首屏可见；
- 长内容仅在主内容内部滚动；
- Context / Source 使用 drawer 或 bottom sheet；
- 生成内容不会挤掉关键操作。

### 18.4 质量验收

- 至少覆盖中文表达缺口、语法错误、好句迁移三类测试；
- 前后端 lint、test、build 通过；
- Prompt eval 中包含 accepted、repair、fallback、rejected case；
- 关键系统动作有后端单元测试；
- sandbox 有安全测试。

---

## 19. 推荐实施顺序

### 第一阶段：表达缺口 + 英文草稿

- 手动输入；
- 群聊线索跳转；
- `expression_variants`；
- `tone_spectrum`；
- `sentence_diff`；
- `micro_practice`；
- 保存好句、词汇、语法点。

### 第二阶段：好句迁移

- `pattern_diagram`；
- `transfer_builder`；
- 句型模板保存；
- 造句练习。

### 第三阶段：沙箱组件

- `sandbox_widget`；
- 受限 JS；
- 复杂 SVG；
- postMessage action protocol。

---

## 20. 最终设计原则

```text
表达实验室不是让模型自由写整个页面，
而是在稳定的学习产品骨架内，
为当前表达问题生成最合适的局部学习界面。
```

```text
生成内容，不生成权力；
生成局部，不生成全局；
结构化 DSL 优先；
保存前用户确认；
所有结果可审计、可回放、可删除。
```

