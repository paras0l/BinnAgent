可以获得的工程经验非常多，而且这部分比“会写 prompt”高级得多。你在面试里不要把它讲成“我做了 prompt 模板管理”，而要讲成：

> 我在做 Agent 工程化时发现，Prompt 本身不是最难的，难的是让 LLM 调用可复现、可验证、可降级、可回归，并且让结构化输出能安全进入业务系统。

结合你项目现状，Prompt Registry + Schema-first 可以沉淀出 9 类工程经验。

---

# 1. Prompt 不是字符串，而是版本化工程资产

你项目里的 `PromptMetadata` 已经把 prompt 拆成了 `id`、`version`、`owner`、`purpose`、`template_path`、`input_schema`、`output_schema`、`model_policy`、`eval_set` 和 `status`。

这说明一个经验：

> prompt 一旦进入生产链路，就不能只是一段散落在代码里的字符串，而应该像 API、数据库 schema、配置文件一样被版本化管理。

面试里可以说：

```text
早期我也可以把 prompt 写在业务函数里，但随着 Chat、词汇提取、语法微课、写作好句导入等能力增多，prompt 的变更会直接影响结构化输出、Memory 写入、练习生成和前端展示。所以我把 prompt 抽象成 Prompt Registry，每个 prompt 有明确 owner、purpose、version、schema、model policy 和 eval set。
```

这个经验很实用。

---

# 2. 可复现比“这次效果不错”更重要

你的 `PromptRegistry.render()` 会根据模板和变量渲染 prompt，同时生成 `prompt_hash` 和 `input_hash`。

这能形成一个非常重要的工程经验：

> LLM 输出不稳定时，首先要能回答“当时到底喂给模型的是什么”。

没有 `prompt_hash` / `input_hash`，线上出现问题时很难排查：

```text
是 prompt 改了？
是输入变了？
是模型变了？
是 temperature 变了？
是输出 schema 变了？
是 repair 逻辑变了？
```

所以你可以讲：

> 我给每次渲染后的 prompt 和输入变量都生成 hash，这样后续可以把一次 LLM 输出追溯到具体 prompt 版本和输入内容。这个设计对 debug、回归测试和线上问题复现很关键。

---

# 3. Schema-first 的核心不是“让模型输出 JSON”，而是保护业务系统

Schema-first 最大的价值不是格式好看，而是防止 LLM 的不稳定输出污染业务数据。

你项目里已经有 `SCHEMA_REGISTRY`，统一管理 `VocabularyExtractOutput`、`WritingPhraseImportOutput`、`GrammarMicroLessonOutput`。

例如词汇卡 schema 要求输出 `cards`，每个 card 需要 `word`、`phonetic`、`definition_zh`、`definition_en`、`examples`、`confidence` 等字段。

语法微课 schema 要求有 `machine_data` 和 `display_html`，其中 `machine_data` 必须包含 topic、core_rules、examples、mistakes、exercises。

可以提炼成经验：

> LLM 输出不能直接写库，尤其是会影响学习路径、练习、Memory、Mastery 的字段。必须先经过 schema validation，把模型生成内容从“自然语言建议”变成“业务系统可消费的数据结构”。

面试表达：

```text
我把 Schema-first 看作 Agent 系统的安全边界。模型可以生成内容，但只有通过 schema 的字段才能进入数据库、前端组件、Memory 或推荐系统。这样可以避免模型漏字段、乱字段、类型错误或者把解释文字混进机器字段里。
```

---

# 4. 本地模型和外部模型要用不同 model policy

你项目里不同 prompt 已经绑定了不同 `model_policy`。

例如：

* `tutor.chat` 默认用 `ollama_chat`，temperature 0.7；
* `vocabulary.agent.extract` 用 `ollama_utility`，temperature 0.1；
* `grammar.micro_lesson.structured` 和 `writing_phrase.import` 用 `external`，temperature 0.2。

这里可以总结出很好的工程经验：

> 不同 Agent 任务对模型的要求不同，不能所有任务都用同一个模型、同一个 temperature。

你可以这样讲：

```text
聊天类任务允许更自然，所以 temperature 可以高一点；结构化抽取类任务要稳定，所以 temperature 低，并且绑定 output_schema；复杂生成类任务可以走 external model，但本地优先或隐私敏感任务要走 local_only policy。Prompt Registry 让我可以把 prompt、schema 和 model policy 绑定在一起，而不是在业务代码里到处 if-else。
```

这能体现你理解 **model routing / task policy**。

---

# 5. JSON repair 是必要的，但不能无脑信任 repair 后的结果

你项目里的写作好句导入已经有一个实践案例：先尝试提取 JSON，如果失败，会从文本中 slice JSON object；如果仍失败，就用 regex fallback，并返回 `parse_mode`、`repair_used`、`warnings`、`confidence`。

这就是很真实的工程经验：

> LLM 即使被要求输出 JSON，也经常会包 markdown code fence、前后加解释、漏字段、类型错。所以系统必须具备 JSON repair 和 fallback，但 repair 后的结果要降低 confidence，并要求人工确认或进入审核队列。

你的实现里，如果没有合法 JSON，会返回 warning：

```text
未识别到合法 JSON，已使用正则 fallback；请人工确认字段。
```

这个逻辑在代码里已经体现。

面试可以讲：

```text
我不会把 JSON repair 当作万能补丁。repair 只能提高可用性，但 repair_used、parse_mode、warnings、confidence 必须被记录下来。低置信结果不能直接进入关键学习闭环，需要人工确认或者作为候选项展示。
```

这个经验很重要，因为它说明你不是“为了跑通强行修 JSON”。

---

# 6. 机器字段和展示字段必须分离

语法微课 schema 里有一个很好的设计：`machine_data` 和 `display_html` 分开。

这能总结出一个高价值经验：

> 面向用户展示的内容，和面向系统消费的数据，不能混在一起。

比如语法微课：

```text
display_html：前端展示，允许富文本。
machine_data：系统消费，用于生成练习、提取规则、写 Memory、做推荐。
```

面试表达：

```text
LLM 很擅长生成解释性文本，但业务系统需要稳定字段。所以我把展示内容和机器可读内容拆开。展示内容可以更自由，machine_data 必须 schema-first。这样前端可以展示好看的微课，而后端仍能拿 core_rules、examples、mistakes、exercises 做练习生成和后续推荐。
```

这个点非常适合技术面。

---

# 7. Prompt Registry 会倒逼你做 eval set，而不是凭感觉调 prompt

你的 `PromptMetadata` 里有 `eval_set` 字段，词汇提取、语法微课、写作好句导入都已经预留 eval set。

这能沉淀一个工程经验：

> prompt 迭代不能只靠人工肉眼看一次输出，必须有固定样例集和回归评测。

否则你会遇到：

```text
这次改 prompt 让 grammar 输出更好，但 vocabulary extraction 变差了。
新增字段后旧 prompt 漏字段。
为了减少 hallucination，prompt 变保守，导致召回下降。
换模型后 JSON 合法率下降。
```

你可以讲：

```text
Prompt Registry 里每个 prompt 都可以绑定 eval_set。这样 prompt 改动后，不只是看 demo，而是跑固定样例，统计 schema pass rate、字段完整率、repair rate、confidence 分布和人工验收通过率。
```

当前项目还是 MVP，`eval_set` 是登记字段，还需要后续把 runner 打通。你可以主动说：

> 当前 Registry 已经有 eval_set 元数据，下一步是把它和 Simulation / Evaluation 打通，形成 prompt regression。

这样很稳。

---

# 8. Debug API 要受控，Prompt 不应该随便暴露

你的 `/api/prompts/{prompt_id}/render` 被 `require_debug_access` 保护。

这背后也有一个工程经验：

> prompt 是系统行为的一部分，甚至可能包含策略、内部字段、schema、模型路由信息，不应该直接暴露给普通用户。

这个点可以讲成：

```text
Prompt render API 主要给 Dev Console 和调试使用，所以我把它放在 Debug API 保护下。普通学习端不直接看 prompt，只消费学习结果。这样既方便工程调试，又避免把内部策略和 prompt 模板暴露出去。
```

这体现安全意识和工程边界。

---

# 9. Schema-first 会暴露产品设计不清晰的问题

这是非常真实的经验。

当你给写作好句导入设计 schema 时，就必须回答：

```text
一个好句到底需要哪些字段？
text 是必填还是可选？
必须有例句吗？
usage_position 的枚举有哪些？
quality_score 低于多少不能保存？
warnings 是给用户看还是给开发者看？
```

你项目里的 `WRITING_PHRASE_IMPORT_SCHEMA` 规定 candidates 数组，每个候选包含 text、chinese_meaning、usage_scene、usage_position、tags、examples、usage_notes、mistakes、quality_score、warnings，而且至少要求 `text`。

同时 extraction 里如果缺少 examples，会降低 quality_score 并加 warning。

这说明一个经验：

> Schema-first 不只是技术约束，它会逼你把产品对象定义清楚。字段不清楚，prompt 再好也没用。

面试可以这样说：

```text
做 Schema-first 后，我发现很多问题不是模型问题，而是业务 schema 没定义清楚。比如写作好句到底是展示素材、练习素材，还是 Memory 证据？不同用途需要不同字段。Schema-first 逼我把这些边界提前想清楚。
```

---

# 10. 这部分最值得展示的工程经验总结

你可以把经验总结成下面这段：

```text
在实践 Prompt Registry + Schema-first 时，我最大的工程经验是：Agent 应用里 prompt 不是一段文本，而是一个可版本化、可复现、可验证、可回归的工程资产。每个 prompt 都应该绑定 owner、purpose、version、output schema、model policy 和 eval set。每次渲染要记录 prompt_hash 和 input_hash，方便线上问题复现。

同时，Schema-first 不是简单要求模型输出 JSON，而是保护业务系统的边界。LLM 输出只有通过 schema validation、JSON repair、confidence scoring 和 fallback 策略之后，才能进入数据库、Memory、Mastery、推荐或前端展示。对于低置信或 fallback 结果，要记录 parse_mode、repair_used、warnings 和 confidence，必要时进入人工审核。

这个过程也让我认识到，不同任务要有不同 model policy：聊天可以更开放，结构化抽取要低温稳定，隐私敏感任务要本地优先，复杂生成任务可以外部模型但必须受 schema 和 eval 约束。最终目标不是写一个“效果好的 prompt”，而是让 LLM 调用在工程系统里可调试、可追踪、可替换、可持续迭代。
```

---

# 11. 面试官可能会追问什么？

我会重点准备这些问题。

## Q1：为什么不用代码里写死 prompt？

回答：

```text
早期可以，但当 prompt 数量增加后，写死在代码里会导致版本不可追踪、模型策略分散、schema 不统一、debug 不可复现。Prompt Registry 可以把 prompt 作为工程资产管理。
```

## Q2：prompt_hash 有什么用？

回答：

```text
用于复现和审计。同一个 prompt_id 不代表内容没变，prompt_hash 能精确标识实际发送给模型的文本。结合 input_hash、model_policy 和 output_schema，可以定位一次 LLM 输出来自哪个版本、哪个输入和哪个模型策略。
```

## Q3：LLM 输出不符合 schema 怎么办？

回答：

```text
先 schema validation；失败后尝试 JSON repair；repair 后仍要重新校验；如果还失败，走 fallback 或返回候选结果，并记录 parse_mode、repair_used、warnings、confidence。关键业务字段不能直接信任 fallback。
```

## Q4：Schema 会不会限制模型创造力？

回答：

```text
会，所以要区分展示字段和机器字段。比如 display_html 可以更自由，但 machine_data 必须严格 schema。创造力留给用户可见解释，确定性留给业务系统消费。
```

## Q5：如何评估 prompt 改动有没有变好？

回答：

```text
不能只看一次 demo。每个 prompt 绑定 eval_set，统计 schema pass rate、field completeness、repair rate、confidence、人工验收通过率和下游业务指标，比如 memory write success、exercise generation success、recommendation relevance。
```

---

# 12. 这部分在简历里怎么写？

可以写成：

```text
- 设计 Prompt Registry 与 Schema-first 输出治理体系，将核心 Prompt 版本化管理，绑定 owner、purpose、output_schema、model_policy 和 eval_set；每次渲染生成 prompt_hash 与 input_hash，用于 LLM 调用复现、调试和回归评估。
```

再加一条更工程化的：

```text
- 建设结构化输出校验与 JSON repair / fallback 机制，对词汇提取、语法微课、写作好句导入等 LLM 产物进行 schema validation、parse_mode、repair_used、warnings 和 confidence 记录，避免低置信模型输出直接污染 Memory、练习生成和学习推荐链路。
```

---

# 13. 我建议下一步补强

当前项目已经有 Registry MVP，但最好继续补这几个：

```text
1. 新增 ModelCallLog，记录 prompt_id、version、prompt_hash、input_hash、output_schema、model_policy、raw_output、validated_output、repair_used、schema_passed、latency_ms。
2. 所有 LLM 节点统一通过 PromptExecutor 调用，不再各模块直接调用 model_router。
3. 接入 jsonschema validation，而不是只登记 schema。
4. Prompt eval runner 打通 eval_set，输出 schema_pass_rate、repair_rate、field_completeness。
5. Dev Console Prompt Debug 页面展示 prompt render、model call、schema validation、repair diff。
6. Simulation / Evaluation 增加 prompt regression scenario。
```

这里最重要的是第 1 和第 2 个：**从 Prompt Registry 走向 Prompt Execution Governance**。现在你已经能“登记和渲染 prompt”，下一步要能“执行、校验、记录、评估 prompt”。
