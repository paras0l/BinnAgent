# 飞书 MCP 群聊学习线索导入方案

> 目标：用飞书群替代微信群，读取指定飞书群消息，把群聊中的英语使用、中文表达缺口、想学内容、单词和好句沉淀到 BinnAgent 的学习系统中。  
> 关键词：飞书 MCP、群聊学习线索、GroupLearningSignals、FeishuGroupSource、FeishuMcpMessageImporter。

---

## 1. 产品决策

当前不再优先做微信 reader，而是先用飞书群替代微信学习搭子群。

原因：

- 项目已经实现了微信 JSON 数据导入，学习分析 pipeline 已经可以复用。
- 飞书官方有 `larksuite/lark-openapi-mcp`，可以通过 MCP 调用飞书 OpenAPI。
- 飞书 IM 能力可以支持获取群列表、搜索群、获取群成员、读取消息列表、发送消息。
- 对当前个人项目而言，飞书群更容易稳定接入，也比个人微信 hook / UI 自动化更可控。

最终方案：

```text
飞书群
  ↓
lark-openapi-mcp
  ↓
FeishuMcpMessageImporter
  ↓
转换成现有微信 JSON 导入兼容格式 / 中性群聊消息格式
  ↓
现有 GroupLearningSignals pipeline
  ↓
语法熟练度、表达缺口、想学内容、单词、好句、笔记、推荐
```

---

## 2. 命名约定

为了避免和项目已有「AI 对话 / ChatPage」混淆，不使用“对话”作为用户侧功能名。

### 用户侧名称

```text
群聊学习线索
```

### 内部模块名

```text
GroupLearningSignals
```

### 数据源名

```text
FeishuGroupSource
```

### 导入器名

```text
FeishuMcpMessageImporter
```

### 避免使用

```text
微信学习捕捉
群聊对话
AI 对话捕捉
微信 reader
```

---

## 3. 功能定位

飞书群不是新的 AI 对话页，也不是教材学习页，而是一个学习信号来源。

用户在飞书群中自然交流，系统读取指定群组消息后，识别以下学习线索：

1. 英文语法使用情况。
2. 中文表达缺口。
3. 用户想学的话题、语法点、单词。
4. 群聊中出现的好句、好表达。
5. 可沉淀到笔记、词库、好句收藏馆、知识库的内容。

---

## 4. 入口位置

入口放在 **学习中心的辅助入口区**。

不新增一级导航，不放进 AI 对话，不作为 Explore 主入口。

建议学习中心结构：

```text
学习中心

主入口：
[教材学习] [词汇练习] [学习画像] [学习记录]

辅助入口：
[群聊学习线索]
从指定飞书群捕捉你想学的表达、语法、单词和好句。
待确认 3 条 · 今日新增 5 条
[查看线索]
```

### 辅助入口卡片文案

```text
群聊学习线索
从指定飞书群捕捉你想学的表达、语法、单词和好句。
待确认 3 条 · 今日新增 5 条
[查看线索]
```

### 设置入口

后续可在顶部用户名下拉菜单的「学习设置」里增加：

```text
群聊学习线索设置
- 飞书群来源
- 同步开关
- 同步频率
- 是否允许群内回复
- 只读模式
```

---

## 5. 飞书 MCP 能力使用

飞书官方 MCP 项目：`larksuite/lark-openapi-mcp`。

关键 IM 工具能力：

| 能力 | 用途 |
|---|---|
| `im.v1.chat.list` | 获取群列表 |
| `im.v1.chat.search` | 搜索指定群 |
| `im.v1.chatMembers.get` | 获取群成员 |
| `im.v1.message.list` | 获取消息列表 |
| `im.v1.message.create` | 发送消息 |

对本功能最重要的是：

```text
im.v1.message.list
im.v1.message.create
```

---

## 6. MCP Polling 实现方式

MCP 更像工具调用，不是天然实时消息监听器。

第一版建议做轮询：

```text
定时调用 im.v1.message.list
拉取指定 chat_id 的新消息
用 message_id / create_time 去重
转成项目已有 JSON 导入格式
写入学习线索 pipeline
```

### 优点

- 实现简单。
- 与 MCP 工具调用方式一致。
- 不需要先搭飞书事件订阅服务。
- 适合个人项目。

### 缺点

- 不是实时监听。
- 实时性取决于轮询间隔。
- 需要维护 cursor / last_message_id / last_message_time。

### 未来可升级

后续如果需要实时性，可以改为：

```text
飞书事件订阅 / callback / websocket
```

但这不属于第一版重点。

---

## 7. FeishuMcpMessageImporter 职责

新增一个导入器：

```text
FeishuMcpMessageImporter
```

职责：

1. 连接飞书 MCP。
2. 找到用户配置的飞书群。
3. 定时拉取新消息。
4. 只处理目标群消息。
5. 只处理支持的消息类型，第一版只处理文本。
6. 做 message_id 去重。
7. 把飞书消息转成现有 JSON 导入兼容格式。
8. 调用已有群聊学习线索导入接口。
9. 保存同步 cursor。
10. 可选：对明确触发词使用飞书 MCP 发群消息。

---

## 8. 配置模型

建议新增配置：

```ts
interface FeishuGroupLearningSourceConfig {
  source_id: string
  platform: 'feishu'
  chat_id: string
  chat_name: string
  enabled: boolean
  sync_interval_seconds: number
  last_message_id?: string
  last_message_time?: string
  import_mode: 'silent' | 'triggered_reply'
  allowed_senders?: string[]
}
```

### 推荐默认值

```json
{
  "platform": "feishu",
  "enabled": true,
  "sync_interval_seconds": 60,
  "import_mode": "silent",
  "allowed_senders": []
}
```

---

## 9. 消息格式转换

### 飞书消息标准化格式

```json
{
  "platform": "feishu",
  "source_type": "group",
  "group_id": "oc_xxx",
  "group_name": "英语学习搭子群",
  "sender_id": "ou_xxx",
  "sender_name": "Alex",
  "message_id": "om_xxx",
  "message_type": "text",
  "content": "I am agree with you.",
  "occurred_at": "2026-07-07T10:30:00+08:00",
  "raw": {
    "provider": "lark-openapi-mcp"
  }
}
```

### 如果短期复用微信 JSON 导入格式

如果现有导入器已经绑定微信字段，可以做兼容层：

```json
{
  "source": "feishu",
  "platform": "feishu",
  "talker": "oc_xxx",
  "talker_name": "英语学习搭子群",
  "sender": "ou_xxx",
  "sender_name": "Alex",
  "msg_id": "om_xxx",
  "type": "text",
  "content": "I am agree with you.",
  "create_time": "2026-07-07T10:30:00+08:00",
  "raw": {
    "provider": "lark-openapi-mcp"
  }
}
```

长期建议改成中性 schema，不再叫 `wechat_compatible`。

---

## 10. 学习线索类型

飞书消息进入 pipeline 后，复用已有学习分析能力。

### 支持线索

| 线索类型 | 示例 | 输出 |
|---|---|---|
| 语法使用 | `I have finished it.` | 增加语法熟练度证据 |
| 语法错误 | `I am agree with you.` | 记录错误点，推荐语法学习 |
| 中文表达缺口 | `这个观点太绝对了怎么说？` | 生成表达候选和学习推荐 |
| 想学语法 | `我想学倒装句` | 推荐 GrammarPage |
| 想学单词 | `nuance 是什么意思？` | 推荐 VocabularyDetail |
| 好句收藏 | `What matters most is not A, but B.` | 推荐加入好句收藏馆 |
| 学习话题 | `我想练面试英语` | 推荐相关学习路径 |

---

## 11. 显式触发词

第一版建议支持这些群聊触发词：

```text
#纠错 I am agree with you.
#怎么说 这个观点太绝对了
#收藏 What matters most is not A, but B.
#单词 nuance
#语法 倒装句
#话题 面试英语
```

### 触发词行为

| 触发词 | 行为 |
|---|---|
| `#纠错` | 分析句子语法，生成纠错结果 |
| `#怎么说` | 识别中文表达缺口，给英文表达建议 |
| `#收藏` | 生成好句候选，写入待确认 |
| `#单词` | 生成词汇详解候选 |
| `#语法` | 生成语法学习推荐 |
| `#话题` | 记录学习兴趣 / 场景 |

---

## 12. 发送消息策略

飞书 MCP 支持发送消息，但默认不应该频繁在群里回复。

### 默认策略

```text
默认只读
显式触发才回复
自然聊天错误不公开纠错
```

### 可以回复的情况

```text
#纠错
#怎么说
#收藏
#单词
#语法
@BinnAgent
```

### 回复示例

用户：

```text
#纠错 I am agree with you.
```

系统：

```text
建议改成：I agree with you.
原因：agree 本身是动词，不需要 be。
已记录到你的群聊学习线索。
```

---

## 13. 用户端呈现

### 学习中心辅助入口

```text
群聊学习线索
来自飞书群：英语学习搭子
今日新增 5 条 · 待确认 3 条
[查看线索]
```

### 线索确认页

```text
待确认线索

1. 表达缺口
中文：这个观点太绝对了
建议表达：That sounds a bit too absolute.
[加入笔记] [加入好句] [忽略]

2. 单词
nuance
[生成词汇详解] [加入词库] [忽略]

3. 语法
I am agree with you.
错误点：agree 不搭配 be
[学习 agree with] [加入错因] [忽略]
```

### 学习画像

展示为用户可理解的信息：

```text
来自群聊的学习信号
- 你最近多次想表达“委婉反驳”
- agree with 结构出现过错误
- nuance 被标记为想学单词
```

### Explore 推荐

```text
推荐：观点表达与委婉反驳
原因：你在飞书群里多次想表达“这个观点太绝对了”
```

---

## 14. 最小实现范围

### V1 只读导入

做：

- 配置一个飞书群 `chat_id`。
- 定时调用 `im.v1.message.list`。
- 只处理 text 消息。
- 按 message_id 去重。
- 转成现有微信 JSON 兼容格式。
- 写入现有学习线索 pipeline。
- 学习中心显示辅助入口卡。
- 线索进入待确认队列。

不做：

- 不处理图片、文件、语音。
- 不读取多个群。
- 不自动回复群消息。
- 不做复杂成员权限管理。
- 不做实时事件订阅。

### V2 显式触发回复

做：

- 支持 `#纠错`、`#怎么说`、`#收藏`、`#单词`、`#语法`。
- 使用 `im.v1.message.create` 回复群消息。
- 保持发送总开关。

### V3 多群同步管理

做：

- 多飞书群配置。
- 群成员映射 learner。
- 同步状态面板。
- 暂停同步。
- 重新导入某时间段。
- 错误重试和同步日志。

---

## 15. 建议后端接口

### 创建/更新来源

```http
POST /api/group-learning/sources
PATCH /api/group-learning/sources/{source_id}
```

### 导入消息

```http
POST /api/group-learning/sources/{source_id}/messages/import
```

### 查询线索

```http
GET /api/learners/{learner_id}/group-learning/signals
```

### 确认线索

```http
POST /api/learners/{learner_id}/group-learning/signals/{signal_id}/confirm
POST /api/learners/{learner_id}/group-learning/signals/{signal_id}/ignore
```

### 同步状态

```http
GET /api/group-learning/sources/{source_id}/sync-status
POST /api/group-learning/sources/{source_id}/sync-now
```

---

## 16. 数据模型建议

### `group_learning_sources`

```ts
{
  id: string
  platform: 'feishu'
  source_type: 'group'
  external_group_id: string
  display_name: string
  enabled: boolean
  sync_interval_seconds: number
  last_message_id?: string
  last_message_time?: string
  import_mode: 'silent' | 'triggered_reply'
  created_at: string
  updated_at: string
}
```

### `group_learning_messages`

```ts
{
  id: string
  source_id: string
  external_message_id: string
  external_sender_id: string
  sender_display_name?: string
  learner_id?: string
  message_type: 'text'
  content_text: string
  occurred_at: string
  raw_payload: object
  ingestion_status: 'pending' | 'processed' | 'ignored' | 'failed'
}
```

### `group_learning_signals`

```ts
{
  id: string
  source_id: string
  message_id: string
  learner_id?: string
  signal_type:
    | 'grammar_usage'
    | 'grammar_error'
    | 'expression_gap'
    | 'desired_topic'
    | 'desired_grammar'
    | 'desired_vocabulary'
    | 'good_sentence'
    | 'phrase_candidate'
  target_type: string
  target_label: string
  evidence_text: string
  recommendation_reason: string
  confidence: number
  status: 'pending' | 'confirmed' | 'ignored'
  created_at: string
}
```

---

## 17. 权限与配置

飞书 MCP 接入需要飞书开放平台应用：

- App ID
- App Secret
- 对应 IM 权限
- 如果使用用户身份访问，需要 OAuth 配置和 user access token

第一版建议使用应用身份或明确授权的应用范围，仅读取指定群。

注意：不能假设应用可以读取所有群；应该只处理应用可见且用户配置的群。

---

## 18. 安全和控制

虽然这是个人项目，也建议保留基础控制：

- 只读模式开关。
- 群回复总开关。
- 指定群白名单。
- 指定 sender 白名单，可选。
- 去重机制。
- 同步日志。
- 原始消息可删除。
- 学习线索需要用户确认后再写入长期记忆 / 笔记 / 词库。

---

## 19. 实现建议

### 推荐目录

```text
binnagent-backend/
  app/group_learning/
    models.py
    schemas.py
    routes.py
    services.py
    feishu_mcp_importer.py
```

或作为独立 sidecar：

```text
tools/feishu-mcp-importer/
  package.json
  src/index.ts
  src/normalize.ts
  src/sync.ts
```

如果飞书 MCP 主要以 Node 包运行，sidecar 用 Node 更自然；如果项目后端更方便统一管理，也可以 Python 后端调用 MCP client。

---

## 20. Codex 提示词

```text
你在 paras0l/BinnAgent 仓库工作。请实现飞书 MCP 群聊学习线索导入的第一版。

产品目标：
用飞书群代替微信群，读取指定飞书群消息，把消息转成项目已有微信 JSON 导入兼容格式，复用现有群聊学习线索分析 pipeline。用户入口放在学习中心辅助入口，名字叫“群聊学习线索”，不要和 AI 对话混淆。

请先检查项目中已有的微信 JSON 导入实现，找到：
- 现有导入接口
- 现有消息 schema
- 学习线索 pipeline
- 学习中心页面入口结构

实现范围：
1. 新增 FeishuMcpMessageImporter 或等价服务。
2. 支持配置一个飞书群 chat_id。
3. 通过飞书 MCP 调用 im.v1.message.list 拉取消息。
4. 第一版只处理 text 消息。
5. 使用 message_id / create_time 做去重。
6. 把飞书消息标准化成现有微信 JSON 导入兼容格式，或新增中性 group message schema 并兼容旧 pipeline。
7. 调用现有导入 pipeline，生成语法使用、语法错误、中文表达缺口、想学语法、想学单词、好句候选等学习线索。
8. 学习中心增加辅助入口卡片：群聊学习线索。
9. 线索进入待确认队列，不要默认直接写入长期记忆。

不要做：
- 不做微信 reader。
- 不做图片、文件、语音消息。
- 不做多个群。
- 不做自动群回复。
- 不新增一级导航。
- 不放进 AI 对话页。

命名：
- 用户侧：群聊学习线索
- 内部模块：GroupLearningSignals
- 数据源：FeishuGroupSource
- 导入器：FeishuMcpMessageImporter

完成后请输出：
- 修改摘要
- 主要文件
- 飞书消息到现有 schema 的映射
- 同步和去重逻辑
- 学习中心入口说明
- 测试方式
```

---

## 21. 总结

现在方案已经从“微信 reader”调整为“飞书 MCP 群聊学习线索导入”。

核心判断：

```text
项目已实现微信 JSON 导入 → 不需要重做学习分析
飞书 MCP 可读群消息 → 新增 source adapter 即可
学习中心放辅助入口 → 不新增一级导航、不混入 AI 对话
```

第一版只需要做：

```text
飞书群消息拉取
消息标准化
复用现有导入 pipeline
学习中心辅助入口
待确认线索队列
```
