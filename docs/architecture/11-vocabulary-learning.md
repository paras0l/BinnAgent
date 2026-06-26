# 11. 教材词汇与背单词模块

## 1. 模块目标

本模块把教材中的 `Words and Expressions in Each Unit` 词表编译为可追溯的单元词汇，并在用户开启某个单元时，由 Vocabulary Agent 将该单元词汇幂等加入个人背单词列表。

核心闭环：

```text
教材导入 -> 定位单元词表 -> 按 Unit 抽取并审核 -> 随知识版本发布
        -> 用户开启 Unit -> 注入个人词表与来源标签 -> 沉浸式学习
        -> 多形式练习 -> 更新掌握度与 SRS -> 到期复习
```

本期必须支持：

- 从教材后部识别并解析 `Words and Expressions in Each Unit`，不依赖固定页码。
- 词汇按教材、版本和单元归属，保留 PDF 页码、印刷页码与版面证据。
- 开启单元时只注入该单元词汇，重复开启不重复创建。
- 同一词可同时拥有教材单元、对话提取、阅读生词和手动添加等多个来源标签。
- 提供专注、低干扰的沉浸式背词体验。
- 单词可播放发音，支持英音/美音、失败降级和缓存。
- 为后续拼写训练预留稳定的任务与事件接口。

本模块不把“加入词表”等同于“已经学会”，也不因用户切换教材或教材升级而清空既有掌握度。

## 2. 已验证的教材基线

仓库中的人教版七年级上册 PDF 可作为首个 golden textbook：

- PDF 共 138 页。
- `Words and Expressions in Each Unit` 从 **PDF 第 117 页**开始，该页印刷页码为 **94**。
- 词表采用双栏排版，正确阅读顺序是左栏从上到下，再读右栏，而不是按页面横向逐行读取。
- 单元会在同一页中换栏，也会跨页延续。例如 PDF 第 117 页左栏为 `Starter Unit 1`，右栏进入 `Starter Unit 2`；PDF 第 118 页左栏延续 Starter Unit，再在右栏进入 `Unit 1`。
- 黑体表示重点词汇，不表示“只有黑体才是词条”；人名、缩写和短语也可能是有效词条。

因此，“七上从 117 页开始”只能作为特定版本的定位提示和回归测试，不得写成通用业务规则。

## 3. 领域边界

### 3.0 当前实现状态

截至 2026-06-26，代码已落地以下能力：

- `VocabularyItem.entry_kind` 支持 `word`、`phrase`、`collocation`、`sentence_pattern`、`abbreviation`、`proper_noun`。
- `VocabularyUserOverride` 保存用户覆盖层：展示名、用户释义、隐藏系统释义、我的理解、我的例句、搭配、笔记、发音偏好和复习偏好。
- `VocabularyMasteryVector` 保存 `recognition`、`recall`、`spelling`、`listening`、`context_use`、`production` 六维掌握度；attempt 会按练习类型更新相关维度。
- `VocabularyMistake` 保存可编辑/可删除错因；删除采用 inactive，后续专项复习不再读取该错因。
- API 已提供 `GET /api/learners/{learner_id}/vocabulary/{item_id}`、`PATCH /override`、`PATCH/DELETE /mistakes/{mistake_id}`。
- 新词学习与旧词复习入口已分离：`/vocabulary-learning/new-session` 和 `/review-session` 作为推荐入口，旧 `/vocabulary/sessions` 保持兼容。
- 前端词汇练习页提供“认识新词 / 今日复习 / 听音拼写”，旧词复习默认隐藏答案；词汇详情页提供个人词卡轻量编辑。

### 3.1 三类对象

| 对象 | 回答的问题 | 生命周期 |
|---|---|---|
| 教材词条 `TextbookVocabularyEntry` | 这本书这个单元列了什么词 | 随知识版本发布，不因用户变化 |
| 个人词汇 `VocabularyItem` | 这个用户对该词掌握得怎样 | 跨教材、跨会话长期存在 |
| 词汇来源 `VocabularyItemSource` | 用户为什么会学到这个词 | 一个词可有多条，独立增删 |

公共教材事实与个人掌握状态必须分离。教材词条不可直接保存用户的熟练度；个人词汇也不能只靠一个字符串 `source_ref` 表达所有来源。

### 3.2 词与表达

词表内容不全是单个单词，需支持：

- 单词：`morning`
- 短语：`Good morning!`、`first name`
- 缩写：`BBC`、`P.E.`
- 专有名词：`Dale`、`China`
- 变体或组合写法：`telephone/phone number`

建议使用 `entry_kind = word | phrase | abbreviation | proper_noun`，不要为了复用现有 `word` 字段而丢弃短语。

## 4. PDF 词表解析

### 4.1 定位策略

按以下顺序定位词表区：

1. 在 PDF 文本层和 OCR 块中搜索规范化标题：`Words and Expressions in Each Unit`。
2. 使用大小写、空白和常见 OCR 误差的模糊匹配，但必须同时满足“位于教材后段”或“后续出现 Unit 标题”等结构证据。
3. 若全文无可靠标题，只把教材后 25% 页面作为候选区，交给版面模型识别，不直接发布。
4. 页码提示可来自教材配置，例如七上 `expected_start_pdf_page = 117`，仅用于缩小搜索和产生偏差告警。

定位结果保存：

```json
{
  "section_type": "unit_vocabulary_index",
  "start_pdf_page": 117,
  "start_printed_page": "94",
  "end_pdf_page": 125,
  "heading_bbox": [102, 42, 420, 82],
  "confidence": 0.99,
  "locator_version": "v1"
}
```

### 4.2 版面读取顺序

每页先基于字符坐标或视觉块识别栏边界，再按栏读取：

```text
page -> header/footer removal -> column detection
     -> left column top-to-bottom -> right column top-to-bottom
     -> unit state propagation -> entry segmentation
```

禁止先把双栏页面压成纯文本再按行解析，否则左右栏内容会交错并把词条分配到错误单元。

### 4.3 单元边界

识别以下标题并映射到教材结构树中的稳定 `curriculum_node_id`：

```text
Starter Unit 1
Starter Unit 2
Starter Unit 3
Unit 1 ... Unit N
```

解析器维护 `current_unit` 状态；跨栏或跨页没有新标题时，后续词条继续归属上一单元。单元标题不能只保存文本，必须与该知识版本中的 Unit 节点匹配。无法唯一匹配时进入人工审核。

### 4.4 词条切分与字段抽取

优先使用版面规则抽取，LLM 只修复低置信结果：

- 词条通常从栏左边界附近的英文 token 开始，以 `p.1`、`p.S7` 等教材页引用结束。
- 缩进续行合并到上一词条，例如长音标、词性或中文释义换行。
- 字体粗细仅生成 `is_key_vocabulary`，不能作为词条存在与否的判断。
- 音标可能同时包含英音和美音，按教材说明保持先后顺序，并保存原始文本。
- `adj.`、`n.`、`pron.` 等词性归一化为数组，同时保留原文。
- 教材页引用解析为 `lesson_printed_page`，不得与词表自身所在页混淆。
- 无词性的短语、人名和缩写仍应保留，并标注对应 `entry_kind`。

标准输出：

```json
{
  "lemma": "morning",
  "display_form": "morning",
  "entry_kind": "word",
  "phonetics": [{"accent": "book", "text": "/ˈmɔː(r)nɪŋ/"}],
  "parts_of_speech": ["noun"],
  "definitions_zh": ["早晨；上午"],
  "is_key_vocabulary": true,
  "curriculum_node_id": "unit_starter_1",
  "lesson_printed_page": "S1",
  "evidence": {
    "pdf_page": 117,
    "printed_page": "94",
    "column": 1,
    "bbox": [51, 140, 245, 164],
    "source_segment_id": "seg_..."
  },
  "confidence": 0.98
}
```

音标示例中的 Unicode 只用于归一化展示；教材原始音标另存于 evidence，避免旧字体映射造成信息丢失。

### 4.5 解析流水线

在 [10-knowledge-base.md](./10-knowledge-base.md) 的 ingestion pipeline 中增加专用阶段：

```text
structured
  -> vocabulary_section_located
  -> vocabulary_layout_parsed
  -> vocabulary_entries_extracted
  -> vocabulary_units_linked
  -> vocabulary_validated
  -> normalized -> published
```

幂等键：

```text
source_version_id + vocabulary_parser_version + extraction_schema_version
```

### 4.6 发布门禁

词表进入 `published` 前至少满足：

- 每个词条都关联一个有效 Unit 和一个页面证据。
- Unit 顺序与教材结构树一致，不出现无解释的回退或跳号。
- 同页双栏顺序正确；跨页词条和续行没有串栏。
- 词条的教材页引用落在该教材允许的页码格式内。
- 同 Unit 下规范键重复率低于阈值，重复项已合并或明确保留不同词性/义项。
- 低 OCR 置信、无法识别音标或无法确定词条边界的项目进入 review queue。

golden set 应覆盖 PDF 第 117-125 页的所有 Starter Unit 与 Unit 1-9，并重点标注跨栏、跨页、非黑体词条、短语、人名和双音标案例。

## 5. 单元开启与词汇注入

### 5.1 触发时机

当用户第一次开启某个教材单元时，由 lesson/session service 产生：

```json
{
  "event_type": "textbook_unit_started",
  "learner_id": "...",
  "source_release_id": "...",
  "curriculum_node_id": "unit_1",
  "session_id": "...",
  "occurred_at": "..."
}
```

Vocabulary Agent 消费事件并执行 `ensure_unit_vocabulary_enrolled`。该操作应在开课事务内同步完成或使用 transactional outbox；用户进入课程后必须立即能看到本单元词汇。

现有实现只在用户完成某个 vocabulary knowledge attempt 后创建 `VocabularyItem`，晚于本需求。目标实现应改为“开单元即批量登记，练习后再更新掌握度”。

### 5.2 注入规则

1. 只读取当前 release 中与该 Unit 直接映射、状态为 `published` 的教材词条。
2. 按 `learner_id + canonical_key` upsert 个人词汇，避免大小写导致重复。
3. 为每个词 upsert 一条教材来源关系，幂等键为：

   ```text
   learner_id + vocabulary_item_id + source_type + source_version_id + curriculum_node_id
   ```

4. 已从对话加入的单词不新建个人词汇，只增加“教材 · 七年级上册 · Unit 1”标签。
5. 已掌握词不重置 `mastery/confidence`，默认进入低频抽查；未学词进入本单元新词池。
6. 注入不等于把全单元一次塞进今日任务。Lesson Planner 根据时间预算、重点词标记和每日新词上限分批安排。
7. 教材版本升级时增加新版本来源，不覆盖历史来源和学习事件；被教材移除的词只将对应来源标为 inactive。

### 5.3 来源标签

用户界面显示短标签，详情页显示完整溯源：

| 来源类型 | 短标签示例 | 详情 |
|---|---|---|
| `textbook_unit` | `七上 · U1` | 书名、出版社、版本、Unit、PDF/印刷页 |
| `conversation` | `对话` | 会话时间和消息引用 |
| `reading` | `阅读` | 材料标题和句子上下文 |
| `manual` | `手动` | 用户添加时间 |

多个标签并列展示，不能覆盖。用户删除某个标签时，只删除来源关系；仅当没有任何来源且用户确认后，才删除个人词汇及其复习历史。

## 6. 数据模型

### 6.1 教材词条

教材词条仍使用 `knowledge_points(type = vocabulary)`，其版本化 `content` 增加：

```text
lemma
display_form
entry_kind
phonetics[]
parts_of_speech[]
definitions_zh[]
is_key_vocabulary
lesson_printed_page
parser_confidence
```

`curriculum_knowledge_map` 记录 Unit、教材顺序和 `role = unit_wordlist`；`knowledge_evidence` 记录词表页 bbox 和来源 segment。

### 6.2 个人词汇扩展

现有 `vocabulary_items` 保留为学习状态聚合，但建议增加：

```text
canonical_key             -- 归一化 lemma/phrase，后续替代 lower(word) 去重
entry_kind
preferred_meaning_id
preferred_accent          -- uk/us/auto
audio_status              -- available/fallback/unavailable
```

新增多来源表：

```text
vocabulary_item_sources
  id
  learner_id
  vocabulary_item_id
  source_type             -- textbook_unit/conversation/reading/manual
  source_id               -- knowledge point/message/material 等稳定 ID
  source_version_id
  curriculum_node_id
  display_label
  context_snapshot jsonb
  first_seen_at
  active
```

当前单值 `source_ref` 在迁移后只作兼容读取；新写入必须使用来源表。

新增练习证据表或扩展学习事件：

```text
vocabulary_attempts
  id, learner_id, vocabulary_item_id, session_id
  drill_type              -- recognition/recall/listening/context/spelling
  prompt_variant
  answer, is_correct, score
  response_time_ms, hint_count, replay_count
  occurred_at
```

掌握度必须综合不同 `drill_type`，只会“看英文选中文”不能判定全面掌握。

### 6.3 发音资产

```text
vocabulary_pronunciations
  id, canonical_key, accent, phonetic
  provider, provider_entry_id, audio_url
  media_type, license, attribution
  fetched_at, expires_at, health_status
```

个人词汇只引用规范发音资产，不为每个用户重复存音频。

## 7. Vocabulary Agent 职责

Vocabulary Agent 负责：

- 响应 `textbook_unit_started`，登记单元词汇和来源。
- 根据今日配额选择新词、到期词和薄弱词。
- 为每个词选择合适训练形式，不连续机械重复同一题型。
- 调用 Dictionary Tool 补充发音、音标、义项、搭配和例句，但不覆盖教材释义。
- 记录练习事件，更新个人掌握度并调用 SRS。
- 把拼写薄弱、听音不识词、词义混淆等错误分类写入 memory。

它不负责重新解析 PDF，也不能在运行时绕过已发布知识版本直接相信原始 OCR 文本。

建议输出：

```json
{
  "unit_enrollment": {"added": 18, "linked": 7, "already_known": 3},
  "session_plan": [
    {"vocabulary_item_id": "...", "drill_type": "listening", "reason": "new_word"}
  ],
  "spelling_candidates": [],
  "memory_updates": [],
  "next_review_schedule": []
}
```

## 8. 沉浸式背词体验

### 8.1 体验原则

- 一屏一词或一个短任务，隐藏全局导航与无关统计。
- 先要求主动回忆，再揭示答案；默认不直接展示中英文对照。
- 键盘、触屏和读屏均可完成，重要操作有明确焦点和可访问标签。
- 每组建议 5-10 个词，结束后给简短反馈，可退出并恢复。
- 错误使用中性反馈，不用红色惩罚或连续打击动画。

### 8.2 训练形式

单次学习按“感知 -> 理解 -> 提取 -> 迁移”组合：

1. **听音辨词**：播放一次发音，从近形或近音词中选择。
2. **意义回忆**：只显示词或语境，用户口头/心中回忆后揭示。
3. **语境选择**：在单元主题例句中选择正确义项。
4. **搭配补全**：补全高频搭配，不只背孤立中文。
5. **主动输出**：口头造句或短句填空。
6. **拼写入口**：显示“听写此词”或“拼写练习”，本期可置灰并标记 TODO，但 API 合同先稳定。

学习页保留：发音按钮、进度、提示、退出、稍后再学。翻译、音标、例句和来源在揭示后分层出现，避免首屏信息过载。

### 8.3 掌握判定

掌握证据至少覆盖两种不同提取形式，并包含一次跨日成功。建议：

```text
recognition 仅小幅加分
recall/context/listening 正确正常加分
spelling 正确提供独立能力证据
使用提示、重复播放和超长响应降低本次证据权重
跨日保持比同一 session 连续答对权重更高
```

SRS 首期可继续使用现有间隔表，但调度输入应从布尔 `correct` 扩展到 0-4 评分与 drill evidence；算法升级时保留事件重放能力。

## 9. 拼写功能预留

本期不实现完整拼写教学，但预留以下入口：

拼写训练的完整入口、用户流程、练习状态、字母级反馈、响应式布局和无障碍规范见 [拼写训练模块 UI/UX 设计规范](../superpowers/specs/2026-06-19-spelling-training-uiux.md)。

```text
POST /api/learners/{id}/vocabulary/sessions/{session_id}/spelling-attempts
```

请求模型：

```json
{
  "vocabulary_item_id": "...",
  "prompt_mode": "audio",
  "answer": "morning",
  "response_time_ms": 4200,
  "replay_count": 1,
  "hint_count": 0
}
```

响应至少返回 `is_correct`、编辑距离、错误位置、正确拼写和下一练习建议。后续可增加字母级错误模式、音素到字素训练和易混词对比，但不能把拼写成绩混进普通识义题而失去能力维度。

## 10. 发音与词典 Provider

### 10.1 MVP 选择

MVP 建议把 [Free Dictionary API](https://dictionaryapi.dev/) 作为默认在线词典/单词音频 provider。其 v2 接口无需 API key：

```text
GET https://api.dictionaryapi.dev/api/v2/entries/en/{word}
```

响应包含 `phonetic`、`phonetics[].text`、`phonetics[].audio`、词性、释义和例句，适合补充教材词条。公开说明称服务免费，但没有生产 SLA，因此不能成为唯一依赖。

Provider 链：

```text
local pronunciation cache
  -> Free Dictionary API
  -> browser SpeechSynthesis en-GB/en-US
  -> unavailable（仍允许继续学习）
```

浏览器 [SpeechSynthesis](https://developer.mozilla.org/en-US/docs/Web/API/SpeechSynthesis) 作为设备侧降级，可选择本机可用英语 voice；不同操作系统音色不一致，因此必须标为 `tts_fallback`，不能冒充词典真人录音。

### 10.2 归一化接口

```python
class PronunciationProvider(Protocol):
    async def lookup(
        self, canonical_key: str, accent: str | None
    ) -> list[PronunciationAsset]: ...
```

标准响应：

```json
{
  "canonical_key": "morning",
  "assets": [
    {
      "accent": "uk",
      "phonetic": "/ˈmɔːnɪŋ/",
      "audio_url": "https://...",
      "provider": "free_dictionary_api",
      "kind": "recording"
    }
  ],
  "fallback": null
}
```

### 10.3 稳定性与安全

- 后端调用外部 API，前端不直接拼 provider URL；统一超时、限流、重试和熔断。
- `word` 必须 URL encode，并限制为已归一化的英文词/短语，防止 SSRF 和任意 URL 请求。
- 音频 URL 只允许 HTTPS 和 provider allowlist 域名，播放前校验媒体类型。
- 对成功响应做缓存和 negative cache；批量预热当前 Unit，但限制并发，禁止导入整本书时轰炸免费服务。
- Provider 无结果不阻塞教材发布或开课。
- 缓存音频文件前核对上游许可；许可不明确时只缓存元数据和短期 URL，不把第三方音频永久收入对象存储。
- 保存 provider、获取时间、许可与 attribution，便于切换或下架。
- 中文教材释义以教材发布版本为事实源；外部词典用于补充，不静默覆盖。

长期可增加本地、可再分发的开源词典/发音数据，Free Dictionary API 保留为补充或开发环境 provider。

## 11. API 设计

```text
POST /api/learners/{id}/textbooks/{source_id}/units/{unit_id}/start
     开启单元，并幂等登记该单元词汇

GET  /api/learners/{id}/vocabulary
     支持 source_type/source_id/unit_id/status 查询，返回多来源标签

GET  /api/learners/{id}/vocabulary/units/{unit_id}/summary
     单元词汇总数、新词、学习中、已掌握、到期数

POST /api/learners/{id}/vocabulary/sessions
     创建沉浸式学习 session，指定 unit、时长和模式

GET  /api/learners/{id}/vocabulary/sessions/{session_id}/next
     获取下一任务，不提前泄露答案

POST /api/learners/{id}/vocabulary/sessions/{session_id}/attempts
     提交多形式练习结果

GET  /api/vocabulary/{item_id}/pronunciations?accent=uk
     获取归一化发音资产与 fallback 信息
```

`start` 响应应让前端解释发生了什么：

```json
{
  "unit_id": "unit_1",
  "vocabulary": {
    "total": 34,
    "newly_added": 20,
    "source_linked": 11,
    "already_known": 3
  }
}
```

## 12. 前端信息架构

### 12.1 单元页

- “开始学习 Unit”触发词汇登记。
- 展示“本单元 34 词 · 新词 20 · 已掌握 3”。
- 可进入“学本单元词汇”，也可继续综合课程。

### 12.2 词汇列表

- 支持按教材、单元、来源、状态筛选。
- 每词展示多个来源 chip，例如 `七上 · U1`、`对话`。
- 发音按钮直接可用；失败时切换 TTS 并给轻量提示。
- 详情展开教材释义、补充释义、例句、搭配和完整溯源。

### 12.3 沉浸模式

- 独立全屏路由，刷新后可恢复 session。
- 音频不自动连续播放；首次播放由用户手势触发以兼容浏览器策略。
- 快捷键：空格播放、Enter 揭示/提交、1-4 自评、Esc 退出确认。
- 完成页只展示本组结果、最需要加强的 1-2 点和下次复习时间。

## 13. 可观测性与质量指标

### 13.1 解析指标

| 指标 | MVP 目标 |
|---|---|
| 词表区定位准确率 | golden textbook 100% |
| Unit 归属准确率 | >= 99% |
| 词条边界 precision/recall | >= 98% |
| 页面证据覆盖率 | 100% |
| 低置信项目审核覆盖率 | 100% |

### 13.2 产品与学习指标

- 单元开启到词汇可见的延迟。
- 重复注入率，应为 0。
- 多来源合并成功率。
- 发音可用率、首播延迟、provider fallback 率。
- 新词学习完成率、跨日保持率和 7/30 天 recall。
- 各 drill type 的正确率，尤其区分 recognition 与 spelling。
- 用户退出沉浸模式的位置和单组合理长度。

## 14. 测试策略

### 14.1 解析测试

- 对七上 PDF 第 117-125 页建立人工标注 fixture。
- 验证 PDF 117 / 印刷 94 的双页码映射。
- 验证左栏先于右栏、Unit 标题位于栏中间、跨页延续。
- 验证黑体重点词与非黑体人名都被提取。
- 验证音标/释义续行、短语、缩写、双音标和 `p.S1` 页引用。
- 对 OCR 降质页面做回归，低置信结果必须进入审核而非静默发布。

### 14.2 业务测试

- 首次开启 Unit 批量加入，第二次开启新增数为 0。
- 对话已有词只增加教材来源，不重置掌握度。
- 同一词来自两个 Unit 时显示两个来源标签。
- 教材 release 升级不会删除旧学习事件。
- 免费词典超时、404、无音频和非法音频域名均能安全降级。
- session 中断后恢复到同一进度，重复提交 attempt 幂等。
- 拼写入口在功能未启用时返回明确 capability 状态，而不是 500。

## 15. 实施顺序

### Phase 1：教材词表可靠入库

- 建立七上第 117-125 PDF 页 golden fixture。
- 实现词表定位、双栏解析、Unit 映射和发布 lint。
- 扩展 vocabulary knowledge schema 与 evidence。

### Phase 2：单元注入与来源模型

- 新增 `vocabulary_item_sources` 和兼容迁移。
- 把注入时机从“完成词汇题后”前移到“开启单元时”。
- 增加来源筛选、单元摘要与注入幂等测试。

### Phase 3：沉浸式学习与发音

- 实现 vocabulary session、任务流和 attempt evidence。
- 接入 Free Dictionary API、发音缓存与 SpeechSynthesis fallback。
- 实现一屏一词、键盘操作和断点恢复。

### Phase 4：拼写与调度升级

- 实现听写、编辑距离和字母级错误模式。
- 使用多维练习证据升级 mastery 与 SRS。
- 根据跨日保持率校准新词量和复习间隔。

## 16. 关键决策

1. **页码提示不是解析规则。** 七上 PDF 117 是 golden baseline，标题、版面和 Unit 结构才是通用依据。
2. **教材词条、个人词汇、来源关系分层。** 同一词只保留一份个人掌握状态，但可有多个来源标签。
3. **开单元即登记，计划器再分批教学。** 保证词汇可见，同时避免一次学习过载。
4. **教材释义与外部词典补充并存。** 外部 provider 不能覆盖教材事实。
5. **发音 provider 可替换且允许失败。** 免费 API 适合 MVP，不应成为开课单点故障。
6. **拼写是独立能力维度。** 先稳定事件和 API 合同，再实现完整训练。
