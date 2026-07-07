# 群聊学习线索捕捉：直接读取微信群消息版产品文档

> 版本：2026-07-07  
> 场景：个人项目 / 小范围自用  
> 路线：直接读取指定微信群消息，不做公众号、小程序、企业微信等替代 MVP。  
> 入口约定：用户端入口放在 **学习中心的辅助入口区**，不新增一级导航，不放进「AI 对话」主入口。

---

## 0. 产品结论

本功能不是 MCP，也不是新的聊天页，而是一个从微信群消息中提取学习信号的后台学习能力。

最终路线：

```text
指定微信群消息读取
→ 成员映射到 learner
→ 只分析绑定用户的消息
→ 提取语法、表达缺口、想学内容、词汇、好句和笔记线索
→ 写入学习画像、学习记录、推荐、词汇候选、语法推荐、好句收藏和笔记
```

用户心智：

```text
我平时就在微信群里和学习搭子交流。
BinnAgent 自动帮我把里面值得学的内容整理出来。
```

---

## 1. 命名约定

### 用户可见名称

推荐使用：

```text
群聊学习线索
```

完整功能名：

```text
群聊学习线索捕捉
```

### 不要使用

| 名称 | 原因 |
|---|---|
| 微信对话 | 容易和现有 AI 对话混淆 |
| 群聊对话 | 和 ChatPage 边界不清 |
| AI 群聊 | 容易让人以为机器人在群里聊天 |
| 微信机器人 | 容易误解为群内自动回复机器人 |
| 群聊监控 / 微信监听 | 负面感强，不适合作为产品名 |
| MCP 微信 | 本功能不是 MCP |

### 内部模块名

```text
GroupLearningSignals
WechatGroupIngestion
ConversationLearningIngestion
```

建议后端目录：

```text
backend/app/services/group_learning/
backend/app/services/wechat_ingestion/
```

---

## 2. 入口位置约定

### 2.1 不新增一级导航

用户端当前一级入口应保持清晰，不为这个功能新增 tab。

不要新增：

```text
AI 对话 / 探索 / 学习中心 / 群聊
```

也不要把它放进 `AI 对话`，因为它不是实时聊天功能。

### 2.2 主入口放在学习中心的辅助入口区

入口放在学习中心首页的辅助区域，弱于「教材学习 / 词汇练习 / 学习画像 / 学习记录」这些主入口。

建议布局：

```text
学习中心

主入口：
[教材学习] [词汇练习] [学习画像] [学习记录]

辅助入口：
[群聊学习线索]
来自微信群的表达缺口、好句、想学单词和语法点
3 条待确认
[查看线索]
```

### 2.3 学习中心卡片文案

```text
群聊学习线索
从指定微信群捕捉你想学的表达、语法、单词和好句。

待确认 3 条
今日新增 5 条
[查看线索]
```

空状态：

```text
群聊学习线索
连接指定微信群后，这里会显示从群聊里捕捉到的学习内容。
[去设置]
```

### 2.4 设置入口

设置入口可以同时放两个位置：

1. 学习中心辅助入口卡片里的「去设置」。
2. 顶部用户名下拉菜单 → 群聊学习线索设置。

但真正的日常使用入口只放在学习中心辅助入口。

### 2.5 不放的位置

| 位置 | 原因 |
|---|---|
| AI 对话页 | 容易和实时 Agent 对话混淆 |
| Explore 主能力卡 | 它是数据入口和学习信号，不是专项学习能力 |
| Header 一级导航 | 使用频率不应高于教材学习、词汇练习 |
| 教材学习页主内容 | 它不只服务教材，项目不限制教材学习 |

---

## 3. 功能定位

### 一句话定义

用户在指定微信群里自然交流，BinnAgent 自动读取该群文本消息，把英文使用、中文表达缺口、学习兴趣和好句子转成学习资产。

### 它不是 AI 对话

```text
AI 对话：用户主动问 Agent，Agent 即时回答。
群聊学习线索：用户在微信群自然表达，系统后台整理学习信号。
```

### 它不是教材学习附属功能

它可以服务教材学习，但不限制于教材。

来源可能是：

```text
学习搭子闲聊
用户想学的生活话题
考试作文表达
口语表达
看到的好句
想问的语法
想记的单词
```

输出可以进入：

```text
语法学习
词汇详解
好句收藏馆
词根词缀
精读与泛读
学习画像
学习记录
个人笔记
知识库候选
```

---

## 4. 核心用户故事

### 4.1 英文语法检测

用户在微信群发：

```text
I am agree with you.
```

系统生成线索：

```text
类型：语法错误
问题：agree 是动词，不需要 be
正确表达：I agree with you.
推荐学习：agree with / be in agreement with
```

### 4.2 语法熟练度证据

用户多次正确使用：

```text
I have been learning English for two months.
```

系统更新：

```text
present perfect continuous 正确使用证据 +1
for + 时间段 正确使用证据 +1
```

微信群自然聊天证据权重低于正式练习，但可作为画像参考。

### 4.3 中文表达缺口

用户在群里说：

```text
这个观点太绝对了
```

系统判断这可能是用户不会表达的英文意图，生成：

```text
表达缺口：委婉反驳 / hedging
可学表达：
- That sounds a bit too absolute.
- That claim may be too strong.
- I think this view needs more nuance.
推荐学习：hedging language, modal verbs, nuance, absolute
```

### 4.4 主动学习意图

用户发送：

```text
#语法 倒装句
#单词 nuance
#收藏 What matters most is not A, but B.
#怎么说 这个观点太绝对了
#纠错 I am agree with you.
```

系统直接识别为用户学习意图，并放入线索收件箱。

### 4.5 好句沉淀

用户发：

```text
What matters most is not how fast you learn, but how consistently you practice.
```

或：

```text
#收藏 What matters most is not A, but B.
```

系统生成好句候选：

```text
句式：What matters most is not A, but B.
功能：强调重点 / 对比结构
适用：作文主体段、观点强调
```

---

## 5. 第一版范围

### 必做

```text
指定微信群来源配置
成员映射 learner
文本消息导入和去重
中英文识别
语法正确/错误识别
中文表达缺口识别
#单词 / #语法 / #收藏 / #怎么说 / #纠错 标签识别
群聊学习线索收件箱
接受 / 忽略 / 删除线索
接受后写入学习推荐、词汇候选、好句候选、语法推荐、学习画像、学习记录
```

### 暂不做

```text
公众号 / 小程序 / 企业微信替代 MVP
语音识别
图片 OCR
文件解析
链接内容抓取
群里自动公开纠错
读取所有群
分析未绑定 learner 的群成员
```

---

## 6. 微信消息读取边界

这是个人项目、小范围使用，因此产品路线直接做微信群读取。但业务层仍要有边界，避免误读全部消息。

必须支持：

```text
白名单群组
成员映射
暂停读取
删除线索
删除原始消息缓存
查看线索来源
```

不要默认：

```text
读取所有微信群
读取所有私聊
分析所有群成员
在群里主动公开纠错
长期保存全部 raw message
```

---

## 7. 消息处理 Pipeline

```text
WechatGroupReader
  ↓
MessageNormalizer
  ↓
ParticipantMapper
  ↓
LanguageDetector
  ↓
LearningSignalExtractor
  ↓
SignalRouter
  ↓
BinnAgent 学习资产
```

### 7.1 WechatGroupReader

职责：从指定微信群读取新消息。

业务层只依赖抽象接口，不把具体微信读取实现写死：

```ts
interface GroupMessageReader {
  listSources(): Promise<GroupSource[]>
  fetchNewMessages(sourceId: string, cursor?: string): Promise<GroupMessageBatch>
}
```

第一版可以先用本地 reader 导出 JSON，再通过 import endpoint 进入系统。

### 7.2 MessageNormalizer

处理：

```text
清理空白
合并多行文本
识别 #标签
识别 @BinnAgent
识别中文 / 英文 / 中英混合
生成 content_hash
```

### 7.3 ParticipantMapper

只分析绑定 learner 的成员消息。

```text
绑定成员 → 进入分析
未绑定成员 → 默认忽略或仅作上下文，不写入个人画像
```

### 7.4 LearningSignalExtractor

输出学习线索。

```ts
ConversationLearningSignal {
  id: string
  message_id: string
  learner_id: string
  signal_type: SignalType
  target_type: TargetType
  target_label: string
  confidence: number
  evidence_text: string
  normalized_note?: string
  recommendation_reason: string
  status: 'candidate' | 'accepted' | 'dismissed' | 'applied'
}
```

Signal 类型：

```ts
type SignalType =
  | 'grammar_correct_usage'
  | 'grammar_error'
  | 'expression_gap'
  | 'desired_topic'
  | 'desired_grammar'
  | 'desired_vocabulary'
  | 'good_sentence'
  | 'phrase_candidate'
  | 'vocabulary_candidate'
  | 'learning_question'
  | 'note_candidate'
```

---

## 8. 语法熟练度计算

微信群自然聊天不是考试，证据权重要低于正式练习。

建议权重：

| 证据来源 | 权重 |
|---|---:|
| 正式教材题 / 语法题 | 1.0 |
| 词汇练习 / 拼写练习 | 0.8 |
| 用户主动 #纠错 后改对 | 0.7 |
| 微信群自然英文正确使用 | 0.3 |
| 微信群自然英文错误使用 | 0.4 |

更新规则：

```text
正确自然使用：增加该语法点熟练度
连续多次正确：增加稳定性
同类错误重复出现：增加复习优先级
纠错后下一次改对：提高学习转化信号
近期证据权重大于很久以前的证据
```

---

## 9. 中文表达缺口识别

中文表达缺口不是“说中文就扣分”，而是识别用户在英语学习上下文中可能想表达但不会表达的内容。

典型消息：

```text
这个怎么说？
我想表达“这件事没有想象中那么简单”
有没有更委婉的说法？
这个观点太绝对了
```

输出：

```ts
ExpressionGapSignal {
  chinese_text: string
  intent_label: string
  suggested_expressions: string[]
  required_grammar: string[]
  required_vocabulary: string[]
  recommended_targets: Array<'GrammarPage' | 'VocabularyDetailPage' | 'WritingPhrasebookPage'>
}
```

---

## 10. 用户端页面设计

### 10.1 学习中心辅助入口卡

在学习中心首页主入口下方增加一张轻量卡。

```text
群聊学习线索
从指定微信群捕捉你想学的表达、语法、单词和好句。

待确认 3 条 · 今日新增 5 条
[查看线索]
```

状态：

| 状态 | 展示 |
|---|---|
| 未连接 | 显示「去设置」 |
| 已连接无新线索 | 显示最近同步时间 |
| 有待确认线索 | 显示 badge 和「查看线索」 |
| 同步失败 | 显示轻量 warning 和重试 |

### 10.2 群聊学习线索收件箱

这是该功能的主页面，作为学习中心二级页。

分组：

```text
全部
表达缺口
语法线索
想学内容
词汇候选
好句候选
笔记候选
已忽略
```

每条线索显示：

```text
类型
来源消息片段
系统解释
推荐动作
来源时间
接受 / 忽略 / 删除
```

示例：

```text
表达缺口
“这个观点太绝对了”
可学表达：That claim may be too strong.
推荐：观点表达与委婉反驳
[加入学习计划] [加入好句] [忽略]
```

### 10.3 群聊学习线索设置页

设置入口：

```text
学习中心辅助入口卡 → 设置
或
用户名下拉菜单 → 群聊学习线索设置
```

「群聊学习线索设置」必须是和「学习设置」同级的独立设置入口，不要藏在学习设置弹窗里的普通 section。原因：

```text
学习设置：练习偏好、发音偏好、任务进入方式。
群聊学习线索设置：外部数据来源、成员映射、读取边界、缓存保留策略。
```

这不是状态展示页，必须是可配置页面。白名单群组、成员映射、原始消息保留天数不能只显示当前值，必须提供明确的编辑控件和保存反馈。

#### 10.3.1 页面结构

建议分区：

```text
读取开关
群组白名单
成员映射
保留与清理
写入策略
同步状态
```

每个分区都要有：

```text
当前状态
可编辑控件
保存 / 取消
保存成功或失败反馈
必要的风险提示
```

#### 10.3.2 读取开关

控件：

```text
[开关] 启用群聊学习线索捕捉
[按钮] 暂停读取 / 恢复读取
```

行为：

| 操作 | 结果 |
|---|---|
| 关闭启用开关 | 停止读取新消息，不删除已有线索 |
| 点击暂停读取 | source status 变为 paused |
| 点击恢复读取 | source status 变为 active |
| 读取失败 | 显示失败原因和「重试同步」 |

暂停 / 恢复后要立即更新同步状态，并保留用户可以继续处理已有线索的能力。

#### 10.3.3 群组白名单配置

白名单群组必须可增删改，不能只是展示“2 个群”。

控件：

```text
[添加群组]
群名称输入框
external_group_key 输入框 / 选择器
状态切换：active / paused
[保存]
[移除]
```

列表每一行展示：

```text
群名称
群标识 external_group_key
状态 active / paused / revoked
最后同步时间
待确认线索数
操作：暂停 / 恢复 / 编辑 / 移除 / 删除该群原始消息缓存
```

约束：

```text
默认不读取任何群，用户必须手动添加到白名单。
移除白名单群组后，不再读取新消息。
移除时必须让用户选择是否删除该群 raw message 缓存。
同一个 external_group_key 不能重复添加。
```

空状态：

```text
还没有白名单群组。
添加一个指定微信群后，BinnAgent 才会读取该群文本消息。
[添加群组]
```

#### 10.3.4 成员映射配置

成员映射必须可编辑，不能只是展示“1 位 learner”。

控件：

```text
群成员列表
成员搜索
learner 选择器
角色选择：learner / partner / unknown
[开关] 是否分析该成员消息
[保存映射]
[取消映射]
```

列表每一行展示：

```text
微信群成员显示名
external_member_key
当前映射 learner
角色
analysis_enabled
最近消息时间
操作：映射到当前 learner / 更换 learner / 取消映射 / 开启分析 / 关闭分析
```

规则：

```text
只有 role=learner 且 analysis_enabled=true 的成员消息会写入个人学习资产。
partner / unknown 成员默认只可作上下文，不写入个人画像。
未映射成员默认忽略，不进入学习线索收件箱。
取消映射后，后续消息不再分析；历史已生成线索保留可追溯来源。
```

风险提示：

```text
把群成员映射到 learner 会让该成员之后的文本消息进入学习信号抽取。
请确认这个群成员就是当前学习者本人，或该项目明确允许这样分析。
```

#### 10.3.5 原始消息保留与清理

缓存天数必须可配置。

控件：

```text
原始消息保留天数：数字输入 / stepper / select
可选值：1 / 3 / 7 / 14 / 30 天
[按钮] 立即清理过期缓存
[按钮] 删除全部原始消息缓存
```

默认值：

```text
7 天
```

校验：

```text
最小 1 天
最大 30 天
空值不允许保存
```

行为：

| 操作 | 结果 |
|---|---|
| 修改保留天数 | 更新 source.raw_retention_days |
| 立即清理过期缓存 | 删除 occurred_at 早于保留窗口的 raw message |
| 删除全部原始消息缓存 | 删除 raw content_text，但保留已接受线索的必要 evidence 摘要 |

删除全部原始消息缓存必须二次确认：

```text
删除后无法从原始群消息重新生成线索；已接受的学习资产不会删除。
```

#### 10.3.6 写入策略

控件：

```text
[开关] 自动生成学习推荐
[开关] 接受后自动写入候选资产
[开关] 高可信标签线索自动进入候选
可信度阈值 slider / select：0.70 / 0.80 / 0.90
```

默认策略：

```text
自动生成学习推荐：开启
接受后自动写入候选资产：开启
高可信标签线索自动进入候选：关闭
可信度阈值：0.80
```

要求：

```text
自动写入不能绕过用户确认，除非用户明确打开对应开关。
任何自动写入都必须保留来源消息追溯。
```

#### 10.3.7 同步状态与调试信息

设置页底部展示同步状态，但它只是辅助信息，不替代配置控件。

展示：

```text
最后同步时间
最后读取 cursor
本次导入消息数
去重消息数
生成线索数
失败原因
```

操作：

```text
[手动同步一次]
[导入本地 JSON]
[查看最近导入记录]
```

`导入本地 JSON` 是第一版接本地 reader 的关键入口，上传后显示：

```text
导入成功 N 条
重复跳过 N 条
生成候选线索 N 条
被成员映射规则忽略 N 条
```

#### 10.3.8 保存与反馈

所有设置修改必须有明确保存反馈：

```text
保存中
已保存
保存失败，请重试
字段校验错误
```

建议交互：

```text
小改动如开关：可立即保存，并显示 toast。
复杂编辑如白名单群组、成员映射：进入编辑态，点击保存后提交。
危险操作如移除群组、删除缓存：必须二次确认。
```

#### 10.3.9 不允许的设置页实现

不要做成：

```text
白名单群组：2 个
成员映射：1 位 learner
原始缓存：7 天
```

这种只是状态摘要，不是设置页。状态摘要可以存在，但旁边必须有编辑、添加、删除、保存等操作入口。

---

## 11. 数据库表建议

### 11.1 `group_learning_sources`

```sql
id
learner_id
platform              -- wechat
source_type           -- group
display_name
external_group_key
status                -- active / paused / revoked
last_cursor
last_seen_at
raw_retention_days
auto_generate_recommendations
auto_write_candidates
auto_apply_high_confidence_tagged_signals
confidence_threshold
created_at
updated_at
```

### 11.2 `group_learning_participants`

```sql
id
source_id
external_member_key
display_name
learner_id
role                  -- learner / partner / unknown
analysis_enabled
last_message_at
created_at
updated_at
```

### 11.3 `group_learning_messages`

```sql
id
source_id
external_message_id
external_member_key
learner_id
message_type
content_text
content_hash
language_mix
occurred_at
ingestion_status
created_at
processed_at
```

### 11.4 `group_learning_signals`

```sql
id
message_id
learner_id
signal_type
target_type
target_label
confidence
evidence_text
normalized_note
recommendation_reason
status
applied_target_id
created_at
updated_at
```

---

## 12. API 建议

### 12.1 来源管理

```http
GET /api/learners/{learner_id}/group-learning/sources
POST /api/learners/{learner_id}/group-learning/sources
PATCH /api/learners/{learner_id}/group-learning/sources/{source_id}
DELETE /api/learners/{learner_id}/group-learning/sources/{source_id}
```

来源管理必须覆盖白名单群组的可配置行为：

```json
{
  "display_name": "七年级英语学习搭子群",
  "external_group_key": "wechat-group-local-key",
  "status": "active",
  "raw_retention_days": 7,
  "auto_generate_recommendations": true,
  "auto_write_candidates": true,
  "auto_apply_high_confidence_tagged_signals": false,
  "confidence_threshold": 0.8
}
```

`PATCH` 至少支持：

```json
{
  "display_name": "新的群名称",
  "status": "paused",
  "raw_retention_days": 14,
  "auto_generate_recommendations": false,
  "auto_write_candidates": true,
  "confidence_threshold": 0.9
}
```

删除来源时需要支持 query 参数或 body 选项：

```text
delete_raw_messages=true | false
```

### 12.2 成员映射管理

```http
GET /api/learners/{learner_id}/group-learning/sources/{source_id}/participants
POST /api/learners/{learner_id}/group-learning/sources/{source_id}/participants
PATCH /api/learners/{learner_id}/group-learning/participants/{participant_id}
DELETE /api/learners/{learner_id}/group-learning/participants/{participant_id}
```

新增 / 更新成员映射：

```json
{
  "external_member_key": "wechat-member-local-key",
  "display_name": "小林",
  "learner_id": "current-learner-id",
  "role": "learner",
  "analysis_enabled": true
}
```

取消映射：

```json
{
  "learner_id": null,
  "role": "unknown",
  "analysis_enabled": false
}
```

### 12.3 缓存清理

```http
POST /api/learners/{learner_id}/group-learning/sources/{source_id}/cleanup
DELETE /api/learners/{learner_id}/group-learning/sources/{source_id}/messages
```

清理过期缓存：

```json
{
  "mode": "expired"
}
```

删除全部原始消息缓存：

```json
{
  "mode": "all_raw_messages",
  "keep_signal_evidence": true
}
```

### 12.4 消息导入

```http
POST /api/group-learning/wechat/messages/import
```

Body：

```json
{
  "source_id": "...",
  "messages": [
    {
      "external_message_id": "...",
      "external_member_key": "...",
      "content_text": "I am agree with you.",
      "occurred_at": "2026-07-07T20:31:00Z"
    }
  ]
}
```

### 12.5 线索收件箱

```http
GET /api/learners/{learner_id}/group-learning/signals?status=candidate
PATCH /api/learners/{learner_id}/group-learning/signals/{signal_id}
```

操作：

```json
{
  "action": "accept" | "dismiss" | "delete" | "apply_to_vocabulary" | "apply_to_phrasebook" | "apply_to_grammar"
}
```

---

## 13. 和现有 BinnAgent 模块的关系

| 群聊线索 | 写入位置 |
|---|---|
| grammar_error | GrammarPage 推荐、学习画像弱点、练习推荐 |
| grammar_correct_usage | mastery / profile 熟练度证据 |
| expression_gap | WritingPhrasebook、GrammarPage、VocabularyDetail 推荐 |
| desired_vocabulary | VocabularyDetail / 词汇本候选 |
| desired_grammar | GrammarPage topic |
| good_sentence | WritingPhrasebook candidate |
| phrase_candidate | WritingPhrasebook candidate |
| desired_topic | Explore 推荐 / 学习计划 |
| note_candidate | 用户笔记 / 知识库候选 |

---

## 14. 验收标准

1. 学习中心首页有辅助入口「群聊学习线索」。
2. 不新增一级导航，不放进 AI 对话页。
3. 顶部用户名下拉菜单有和「学习设置」同级的「群聊学习线索设置」。
4. 可以新增、编辑、暂停、恢复、移除指定微信群白名单来源。
5. 可以查看、搜索、编辑成员映射，并把指定群成员映射到当前 learner。
6. 可以开启 / 关闭成员分析，未映射成员默认不进入线索收件箱。
7. 可以配置原始消息保留天数，范围 1-30 天，默认 7 天。
8. 可以手动清理过期缓存，也可以二次确认后删除全部原始消息缓存。
9. 可以配置自动生成推荐、接受后自动写入候选、可信度阈值等写入策略。
10. 所有设置变更必须有保存成功、保存失败或字段校验反馈。
11. 可以导入该群文本消息并去重。
12. 可以识别英文语法正确使用和错误使用。
13. 可以识别中文表达缺口。
14. 可以识别 `#单词`、`#语法`、`#收藏`、`#怎么说`、`#纠错` 等标签。
15. 用户端有群聊学习线索收件箱。
16. 用户可以接受、忽略、删除线索。
17. 接受后的线索可以进入词汇候选、好句候选、语法推荐、学习画像或学习记录。
18. 每条推荐能追溯到来源消息，但不暴露无关群成员数据。

---

## 15. Codex 提示词

```text
你在 paras0l/BinnAgent 仓库中工作。请实现“群聊学习线索捕捉”的第一版，产品路线直接读取指定微信群消息，不做公众号/小程序/企业微信 MVP。

重要命名：
- 用户可见功能名：群聊学习线索
- 完整功能名：群聊学习线索捕捉
- 不要叫“AI 对话”或“微信对话”，避免和现有 ChatPage 混淆。
- 内部模块可叫 GroupLearningSignals / WechatGroupIngestion。

入口约定：
- 不新增一级导航。
- 不放进 AI 对话页。
- 主入口放在学习中心首页的辅助入口区，弱于教材学习、词汇练习、学习画像、学习记录这些主入口。
- 卡片文案：群聊学习线索 / 从指定微信群捕捉你想学的表达、语法、单词和好句。
- 设置入口可以在该卡片里，也可以在用户名下拉菜单里。
- 用户名下拉菜单里的「群聊学习线索设置」必须和「学习设置」同级，不要放进学习设置弹窗内部。

产品目标：
用户在指定微信群里自然交流，系统读取该群文本消息，抽取学习信号：
1. 英文语法是否用对。
2. 哪些语法点用户已熟练使用。
3. 哪些中文句子可能代表用户不会表达，生成表达缺口。
4. 用户想学的话题、语法、单词、好句。
5. 把这些线索写入学习画像、学习记录、Explore 推荐、词汇候选、语法推荐、好句收藏候选和笔记候选。

实现范围第一版：
- 指定微信群来源配置。
- 成员映射 learner。
- 文本消息导入和去重。
- 学习信号抽取。
- 群聊学习线索收件箱。
- 接受 / 忽略 / 删除线索。
- 接受后写入现有学习资产或推荐系统。

不要做：
- 不做公众号、小程序、企业微信替代 MVP。
- 不做群内自动公开纠错。
- 不做语音、图片、文件、链接解析。
- 不读取所有群，只读取白名单群。
- 不分析未映射 learner 的群成员。

后端建议新增表：
- group_learning_sources
- group_learning_participants
- group_learning_messages
- group_learning_signals

后端建议新增 API：
- GET /api/learners/{learner_id}/group-learning/sources
- POST /api/learners/{learner_id}/group-learning/sources
- PATCH /api/learners/{learner_id}/group-learning/sources/{source_id}
- POST /api/group-learning/wechat/messages/import
- GET /api/learners/{learner_id}/group-learning/signals?status=candidate
- PATCH /api/learners/{learner_id}/group-learning/signals/{signal_id}

消息读取层：
先实现抽象接口，不要把具体微信读取方式写死在业务层：

interface GroupMessageReader {
  listSources(): Promise<GroupSource[]>
  fetchNewMessages(sourceId: string, cursor?: string): Promise<GroupMessageBatch>
}

第一版可以先用 import endpoint 接收本地 reader 导出的消息 JSON，业务层按标准消息结构处理。后续再接真实本地微信 reader。

信号类型：
- grammar_correct_usage
- grammar_error
- expression_gap
- desired_topic
- desired_grammar
- desired_vocabulary
- good_sentence
- phrase_candidate
- vocabulary_candidate
- learning_question
- note_candidate

前端建议：
1. 学习中心首页新增辅助入口卡：群聊学习线索。
2. 新增二级页面：群聊学习线索收件箱。
3. 新增独立设置弹窗 / 页面：群聊学习线索设置。
4. 群聊学习线索设置必须可编辑、可保存，不要只展示当前值。
5. 群组白名单支持添加、编辑、暂停、恢复、移除、删除该群缓存。
6. 成员映射支持搜索成员、映射 learner、更换 learner、取消映射、开启 / 关闭分析。
7. 原始消息保留时间支持 1 / 3 / 7 / 14 / 30 天配置，并支持立即清理过期缓存、二次确认后删除全部 raw message。
8. 写入策略支持自动生成推荐、接受后自动写入候选、可信度阈值配置。
9. 同步状态、最后同步时间、导入统计只能作为辅助信息，不能替代配置控件。

收件箱分组：
- 全部
- 表达缺口
- 语法线索
- 想学内容
- 词汇候选
- 好句候选
- 笔记候选
- 已忽略

每条线索显示：
- 类型
- 来源消息片段
- 系统解释
- 推荐学习动作
- 接受 / 忽略 / 删除

接受后：
- grammar_error → 学习画像弱点 + GrammarPage 推荐
- grammar_correct_usage → 语法熟练度证据
- expression_gap → 好句候选 / 语法推荐 / 词汇详解推荐
- desired_vocabulary → VocabularyDetail / 词汇本候选
- desired_grammar → GrammarPage topic
- good_sentence / phrase_candidate → WritingPhrasebook candidate
- note_candidate → 用户笔记候选

熟练度计算：
微信群自然聊天证据权重低于正式练习：
- 正式教材题 / 语法题：1.0
- 词汇练习 / 拼写练习：0.8
- 用户主动 #纠错 后改对：0.7
- 微信群自然英文正确使用：0.3
- 微信群自然英文错误使用：0.4

请确保：
- 只处理绑定 learner 的消息。
- 原始消息支持删除或短期保留。
- 每条推荐可追溯来源消息。
- 不暴露无关群成员数据。

完成后运行：
cd binnagent-frontend && npm run lint && npm run build
以及后端测试命令，如项目已有 pytest 或 npm test。

输出：
1. 修改摘要
2. 新增表和 API
3. 新增前端页面/组件
4. 信号抽取逻辑
5. 如何导入微信群消息
6. 测试结果
```
