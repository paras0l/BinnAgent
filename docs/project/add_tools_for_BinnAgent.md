围绕 can-do statement 建立一组可组合的学习工具。核心链路是：

```text
题目/用户疑问
   ↓
识别语言现象
   ↓
匹配 can-do statement + 原子知识点
   ↓
分析作答证据
   ↓
更新学习者状态
   ↓
选题、生成练习、安排复习
```

## 一、两个 can-do 检索工具

虽然底层可以共享同一个检索服务，但对 LLM 应暴露成两个工具，因为输入语义不同。

### 1. `find_can_do_for_item`

根据题目、正确答案和可选解析，识别考查的 can-do statements。

```json
{
  "question": "They wondered whether will the train arrive on time.",
  "task_type": "error_correction",
  "correct_answer": "They wondered whether the train would arrive on time.",
  "knowledge_type": "grammar",
  "top_k": 3
}
```

返回结果不能只有一句话，必须包含证据和置信度：

```json
{
  "primary": {
    "id": "egp:<actual-id>",
    "statement": "Can report thought using 'wonder' + 'wh-' word + clause, with a tense shift where relevant.",
    "confidence": 0.93,
    "role": "primary"
  },
  "atomic_kcs": [
    {
      "id": "grammar.reported_question.word_order",
      "label": "间接疑问句使用陈述语序",
      "confidence": 0.98,
      "evidence": {
        "incorrect": "will the train arrive",
        "correct": "the train would arrive"
      }
    },
    {
      "id": "grammar.reported_speech.backshift",
      "label": "间接引语中的时态后移",
      "confidence": 0.91,
      "evidence": {
        "incorrect": "will",
        "correct": "would"
      }
    }
  ],
  "alternatives": [],
  "needs_review": false
}
```

这里要采用“一个主要 can-do + 多个原子 KC”的结构。否则一个 EGP can-do 同时包含 `wonder`、间接疑问语序和时态后移，DKT 无法知道学生具体不会哪一个。

还要注意：示例使用的是 `whether`，而给出的 statement 写的是 `wh-word`。工具应保留这个术语差异并检查候选项，不能因为语义接近就强行返回唯一答案。

### 2. `find_can_do_for_query`

根据学习者的自然语言疑问查找 can-do statements。

```json
{
  "query": "为什么 wondered 后面不能说 whether will the train arrive？",
  "user_level": "B1",
  "conversation_context": [
    "They wondered whether will the train arrive on time."
  ],
  "top_k": 3
}
```

这个工具应返回：

* 最相关 can-do；
* 用户疑问涉及的原子知识点；
* 判断依据；
* 推荐解释深度；
* 是否需要追问。

例如：

```json
{
  "intent": "grammar_question",
  "matches": [
    {
      "can_do_id": "egp:<actual-id>",
      "confidence": 0.91,
      "reason": "疑问包含 wondered、whether、疑问句语序和时态变化"
    }
  ],
  "atomic_kcs": [
    "grammar.reported_question.word_order",
    "grammar.reported_speech.backshift"
  ],
  "recommended_response_level": "B1",
  "clarification_required": false
}
```

## 二、建议增加的其他 tools

### 3. `analyze_learner_response`

比较题目、参考答案和学生答案，产生学习证据。

输入：

```json
{
  "question_id": "q_123",
  "question": "...",
  "expected_answer": "...",
  "learner_answer": "...",
  "linked_can_do_ids": ["..."]
}
```

输出应区分：

* `SUCCESS`：成功使用目标结构；
* `UNSUCCESSFUL`：尝试了但使用错误；
* `NO_ATTEMPT`：完全绕开目标结构；
* `UNRELATED_ERROR`：目标结构正确，错在其他地方。

它是 Dialogue-based KT 与 DKT 之间最关键的桥梁。

### 4. `get_learner_knowledge_state`

读取用户在某些 can-do/KC 上的当前状态：

```json
{
  "user_id": "u_1",
  "knowledge_ids": [
    "grammar.reported_question.word_order",
    "grammar.reported_speech.backshift"
  ]
}
```

返回建议包括：

* DKT 掌握概率；
* IRT 能力估计；
* 最近证据；
* 置信度；
* 是否到期复习；
* 常见错误。

不要只返回一个“掌握/未掌握”布尔值。

### 5. `record_learning_evidence`

将一次作答或对话证据写入学习者模型。

```json
{
  "user_id": "u_1",
  "source": "dialogue",
  "question_id": "q_123",
  "observations": [
    {
      "knowledge_id": "grammar.reported_question.word_order",
      "outcome": "UNSUCCESSFUL",
      "confidence": 0.97
    }
  ],
  "event_id": "unique-event-id"
}
```

这是有副作用的写工具，必须：

* 使用 `event_id` 保证幂等；
* 保存匹配模型版本；
* 保存原始证据；
* 支持撤销错误标注；
* 不允许 LLM 直接覆盖掌握概率。

### 6. `recommend_next_learning_action`

根据学习者状态选择下一步，而不只是推荐下一道题。

可能动作：

* 解释概念；
* 对比正误例句；
* 做一道辨析题；
* 做纠错题；
* 做开放式产出；
* 复习前置知识点；
* 暂停该知识点。

输出要说明为什么：

```json
{
  "action": "contrastive_explanation",
  "target_knowledge_ids": [
    "grammar.reported_question.word_order"
  ],
  "reason_codes": [
    "REPEATED_WORD_ORDER_ERROR",
    "BACKSHIFT_PARTIALLY_MASTERED"
  ],
  "constraints": {
    "difficulty": "B1",
    "avoid_new_grammar": true
  }
}
```

### 7. `generate_constrained_activity`

让 LLM 按学习状态生成题目，但必须接受明确约束。

```json
{
  "target_can_do_ids": ["..."],
  "activity_type": "error_correction",
  "difficulty": "B1",
  "required_forms": ["wonder + whether + clause"],
  "forbidden_knowledge_ids": ["grammar.inversion.advanced"],
  "item_count": 3
}
```

生成后还应经过内部校验器检查：

* 题目是否真的触发目标 can-do；
* 是否存在多个正确答案；
* 是否无意考查了更难知识；
* 答案与解析是否一致。

### 8. `schedule_knowledge_review`

连接 FSRS，为 can-do/KC 安排复习：

```json
{
  "user_id": "u_1",
  "knowledge_id": "grammar.reported_question.word_order",
  "rating": "again",
  "evidence_id": "ev_123"
}
```

FSRS 应调度“知识点对应的复习活动”，而不是反复展示同一道题。

### 9. `explain_learning_decision`

面向学习者或教师解释系统为什么做出某个判断：

```json
{
  "user_id": "u_1",
  "decision_type": "next_activity",
  "decision_id": "decision_123",
  "audience": "learner"
}
```

例如：

> 你已经能正确把 will 改成 would，但最近两次仍在 whether 后使用疑问语序，因此下一题只练习间接疑问句语序。

这个工具读取已保存的决策依据，不能让 LLM事后编造理由。

## 三、词汇也使用同一模型

不用另建一套完全不同的系统。统一定义：

```text
KnowledgeItem
├── GrammarCanDo
├── VocabularyCanDo
├── PronunciationCanDo
└── DiscourseCanDo
```

词汇可以有对应工具能力，例如：

* 根据题目识别目标词义、搭配或语域；
* 区分“认识词义”和“能在语境中产出”；
* 识别搭配错误；
* 根据用户疑问匹配 vocabulary can-do；
* 调度词义、拼写、搭配、产出等不同复习活动。

例如 `make a decision` 用错为 `do a decision`，主要 KC 应是词汇搭配，而不是笼统标记为 `decision` 这个单词不会。

## 四、can-do 匹配不能只靠向量搜索

建议采用四阶段匹配：

1. 结构提取：从题目和答案中提取原句、改动位置、语法形式、功能和题型。
2. 混合召回：关键词/BM25、向量语义检索、形式规则同时召回候选项。
3. 语义重排：LLM 比较候选项与题目证据，但只能从已有候选中选择。
4. 证据校验：返回具体文本跨度；找不到证据时限制最高置信度。

建议阈值：

* `≥ 0.85`：自动采用；
* `0.65–0.85`：保留前三项，必要时人工确认；
* `< 0.65`：不写入学习者模型，允许追问或标记待标注。

## 五、第一阶段最值得实现的 5 个工具

按优先级：

1. `find_can_do_for_item`
2. `find_can_do_for_query`
3. `analyze_learner_response`
4. `get_learner_knowledge_state`
5. `record_learning_evidence`

完成这五个以后，就已经形成：

```text
题目 → can-do → 作答证据 → 学习者状态
```

之后再增加推荐、生成和 FSRS 调度，风险更低。

快速验收可以准备 40–60 个固定样例，至少要求：

* can-do Top-1 命中率 ≥ 85%；
* Top-3 命中率 ≥ 95%；
* 必须返回可定位的题目证据；
* 无关题目误匹配率 ≤ 5%；
* 多知识点题目能区分 primary can-do 和 atomic KCs；
* 相同写入事件不会重复更新学习状态。

