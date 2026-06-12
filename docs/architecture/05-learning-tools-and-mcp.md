# 05. Learning Tools 与 MCP 方案

## 1. 模块目标

Learning Tool Gateway 为 Agent 提供稳定、结构化、可审计的学习工具。

第一阶段可以用内部 Python service 实现，后续逐步 MCP 化，方便接入外部题库、词典、语音服务和学习平台。

## 2. 工具总览

| 工具 | 用途 | 优先级 |
|---|---|---|
| CET Question Bank | 四六级题目、真题、模拟题 | P0 |
| Dictionary Tool | 释义、音标、例句、搭配、词频；预留有道词典 provider | P0 |
| Spaced Repetition Scheduler | 生成复习队列 | P0 |
| Essay Scoring Tool | 作文评分和错误分析 | P0 |
| Material Ranker | 推荐合适难度材料 | P1 |
| ASR Tool | 口语转写和发音分析 | P1 |
| TTS Tool | 听力材料和发音示范 | P1 |
| Progress Analytics | 学习趋势和周报 | P1 |

## 3. CET Question Bank

### 3.1 数据字段

```text
question_id
exam_type: CET4 / CET6
section: listening / reading / writing / translation
question_type
difficulty
source
stem
options
answer
explanation
tags
estimated_time_seconds
```

### 3.2 标签体系

阅读标签：

- main_idea
- detail
- inference
- vocabulary_in_context
- paragraph_matching
- transition_logic

听力标签：

- news
- long_conversation
- passage
- speaker_attitude
- detail_location
- transition_signal

写作标签：

- argumentation
- chart_description
- campus_life
- social_issue
- technology

## 4. Dictionary Tool

Dictionary Tool 是统一词典抽象，不直接绑定具体供应商。第一阶段可以使用本地词典数据或 mock provider；后续预留接入有道词典，并建议通过 MCP server 暴露给 Agent。

### 4.1 输入

```json
{
  "word": "sustain",
  "learner_level": "CET6",
  "context_sentence": "The policy is hard to sustain."
}
```

### 4.2 输出

```json
{
  "word": "sustain",
  "phonetic": "/səˈsteɪn/",
  "meanings": [],
  "contextual_meaning": "维持",
  "collocations": [],
  "examples": [],
  "confusing_words": [],
  "cet_relevance": "high"
}
```

### 4.3 Provider 抽象

建议定义统一 provider：

```python
class DictionaryProvider(Protocol):
    async def lookup(self, request: DictionaryLookupRequest) -> DictionaryLookupResponse:
        ...

    async def examples(self, request: DictionaryExampleRequest) -> DictionaryExampleResponse:
        ...
```

Provider 选择：

```yaml
dictionary:
  default_provider: local
  providers:
    local:
      enabled: true
    youdao:
      enabled: false
      app_key_env: YOUDAO_APP_KEY
      app_secret_env: YOUDAO_APP_SECRET
      endpoint: configurable
```

### 4.4 有道词典预留接口

后续接入有道词典时，系统内部仍保持统一输出 schema，不让 Vocabulary Agent 感知有道字段差异。

有道 provider 建议输出归一化字段：

```json
{
  "provider": "youdao",
  "query": "sustain",
  "basic": {
    "phonetic_us": "",
    "phonetic_uk": "",
    "explains": []
  },
  "web_phrases": [],
  "examples": [],
  "raw_ref": "object_storage_or_log_ref"
}
```

归一化到 Dictionary Tool 标准响应：

```json
{
  "word": "sustain",
  "phonetic": "/səˈsteɪn/",
  "meanings": [],
  "contextual_meaning": "维持",
  "collocations": [],
  "examples": [],
  "confusing_words": [],
  "cet_relevance": "high",
  "provider": "youdao"
}
```

实现注意：

- 有道 API key 不进入代码库，统一从环境变量读取。
- API 返回原文只保存引用或摘要，避免日志过大。
- 调用失败时 fallback 到 local dictionary 或让 LLM 基于上下文生成临时解释，并标记 `source=llm_generated`。
- 对考试核心词，优先使用本地可控词库，避免外部 API 波动影响复习。

## 5. Spaced Repetition Scheduler

### 5.1 输入

```json
{
  "item_id": "word_sustain",
  "item_type": "vocabulary",
  "last_result": "wrong",
  "response_time_ms": 8200,
  "current_confidence": 0.58
}
```

### 5.2 输出

```json
{
  "next_review_at": "2026-06-13T20:30:00+08:00",
  "interval_days": 2,
  "new_confidence": 0.46,
  "recommended_drill": "context_fill_blank"
}
```

## 6. Essay Scoring Tool

### 6.1 评分维度

四六级作文建议维度：

- 内容完整性。
- 结构清晰度。
- 语言准确性。
- 词汇丰富度。
- 连贯衔接。
- 任务匹配度。

### 6.2 输出

```json
{
  "score": 12,
  "max_score": 15,
  "strengths": [],
  "key_issues": [],
  "sentence_feedback": [],
  "rewrite_suggestions": [],
  "error_patterns": []
}
```

注意：工具不直接替用户完成最终作文。Writing Agent 要先让用户二次修改。

## 7. ASR / TTS Tool

### 7.1 ASR

用途：

- 口语转写。
- 跟读对比。
- 听力转写评估。

输出：

```json
{
  "transcript": "...",
  "confidence": 0.87,
  "segments": [],
  "possible_pronunciation_issues": []
}
```

### 7.2 TTS

用途：

- 单词发音。
- 句子跟读。
- 听力材料生成。

要求：

- 支持英音/美音。
- 支持语速调节。
- 可生成短句而不是长音频。

## 8. Material Ranker

根据以下因素排序材料：

- 用户目标。
- 当前水平。
- 生词密度。
- 兴趣主题。
- 历史完成率。
- 考试相关性。

输出：

```json
{
  "material_id": "reading_001",
  "reason": "难度适中，含 3 个目标词，适合训练转折定位。",
  "estimated_minutes": 12
}
```

## 9. MCP 化策略

### 9.1 为什么 MCP

MCP 适合将学习工具标准化：

- 题库可作为 resource。
- 词典、评分、复习调度可作为 tool。
- 常用教学 prompt 可作为 prompt。
- 后续可接入外部学习平台。

### 9.2 分阶段

第一阶段：

- 内部工具函数。
- 结构化输入输出。
- 工具调用审计。

第二阶段：

- 将 Dictionary、Question Bank、SRS 封装为 MCP server。
- Dictionary MCP server 内部支持 provider 插拔，预留 `youdao` provider。

第三阶段：

- 接入外部 MCP server，如文件、网页、知识库、日历。
- 如有道词典以独立 MCP server 形态接入，则通过 Tool Gateway 做 allowlist、参数校验和输出归一化。

### 9.3 Dictionary MCP Tool 草案

Tool name：

```text
dictionary.lookup
```

输入：

```json
{
  "word": "sustain",
  "context_sentence": "The policy is hard to sustain.",
  "learner_level": "CET6",
  "provider": "youdao"
}
```

输出：

```json
{
  "word": "sustain",
  "phonetic": "/səˈsteɪn/",
  "meanings": [],
  "examples": [],
  "collocations": [],
  "source": {
    "provider": "youdao",
    "confidence": 0.9
  }
}
```

## 10. 工具安全

英语学习工具风险较低，但仍需注意：

- 上传作文和音频属于用户数据，需要隐私保护。
- 外部网页材料可能包含 prompt injection。
- 题库版权需要明确。
- 学习记录不能跨用户泄漏。

工具调用必须记录：

- user_id。
- session_id。
- tool_name。
- input summary。
- output summary。
- latency。
- error。
