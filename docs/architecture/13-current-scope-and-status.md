# 13. Current Scope and Status

> 更新时间：2026-06-27
> 目的：把当前实现、部分实现和仍处于设计中的内容显性化，避免把架构目标误读成已落地功能。

## 状态图例

| 标记 | 含义 |
|---|---|
| 已实现 | 有后端/API、前端入口或测试支撑，可运行验证 |
| 部分实现 | 已有骨架或单点能力，但学习闭环、可靠性或界面仍缺口 |
| 设计中 | 文档已有目标，代码尚未形成完整能力 |

## 当前产品线

| 产品线 | 状态 | 说明 |
|---|---|---|
| 七年级教材线 | 部分实现 | 教材知识库、单元词汇、RAG chunk、场景化多题型练习和前端入口已存在，RAG 可解释性和恢复能力正在增强 |
| CET 备考线 | 设计中 | 7 天计划、阅读训练、写作二改和周报仍主要在架构文档中 |
| 通用英语陪伴 | 部分实现 | Chat、Memory 摘要、Dashboard 和词汇沉淀已有基础闭环 |

## 共享底座状态

| 模块 | 状态 | 当前能力 | 下一步 |
|---|---|---|---|
| FastAPI API | 已实现 | learners、chat、memory、dashboard、knowledge、vocabulary、grammar 等 routers | 统一 current learner 认证授权 |
| React 前端 | 部分实现 | 多页面学习入口、SSE chat、知识库和词汇练习 | 今日学习路径、恢复提示、RAG 调试模式 |
| LangGraph daily lesson | 部分实现 | 线性 daily lesson graph 和主要节点 | checkpoint、interrupt、answer_required、resume |
| Memory | 部分实现 | 4 层学习记忆架构 + HindSight-inspired Retain/Recall/Reflect 口径已落地；统一 memory event/operation、LearningEpisode、LearnerModelMemory、TeachingStrategyMemory、MemoryWriter/Retriever/Curator、显式 L1-L4 layer metadata、ErrorPattern governance、WritingPhraseMastery、Memory Center、导出/删除/禁用/我已改善、重置计划、情绪/节奏 opt-in、低置信上下文开关、memory_context log、hit-rate 指标、作文批改历史弱点对比 | 更完整 debug dashboard 图表、更多 regression eval、更多 session 类型反思规则 |
| Vocabulary Learning | 部分实现 | 单元 enroll、用户可编辑个人词卡、new/review/spelling session、attempt、错因记录、mastery vector、发音 URL | 薄弱原因总结、题型推荐、更多表达迁移题 |
| Knowledge Base / RAG | 部分实现 | PDF 解析、chunk、embedding、文本 fallback、8 题混合练习流、hint/retry/rubric 反馈 | hybrid retrieval、golden query set、前端证据面板、练习 session 总结 |
| Prompt & Parsing Governance | 部分实现 | Prompt Registry MVP、prompt render API、核心 prompt 模板、写作导入 JSON-first extraction、教材 manifest/profile/parser report | 更多 prompt eval、词汇/语法 schema-first 回填、人工校对工作台 |
| Model Provider | 部分实现 | Ollama chat/stream/embed/health，结构化 JSON repair retry | task policy、local_only 强约束、持久化 model_call_logs |
| Observability | 部分实现 | Langfuse observation 和运行时表 | run_id 贯通 graph/model/tool/memory，Dashboard 可视化 |
| Evaluation / Simulation | 部分实现 | `src/simulation` 提供 deterministic learner persona、behavior policy、scenario runner、assertion engine 和结构化 simulation report；已覆盖 smoke、vocabulary agent deposit、vocabulary practice adaptation、daily graph 基线 | 扩展教材知识练习、写作好句闭环、Memory regression、LLM-assisted learner 和 dashboard |
| CI | 已实现 | GitHub Actions 覆盖 backend lint/test、frontend lint/build、migration 文本检查 | Alembic 在线迁移检查和端到端 smoke |
| Writing Phrasebook | 基础版已实现 | 探索页写作入口、句式 CRUD、外部模型结果提取、候选收藏、识别/填空/替换练习和 attempt 记录 | 模型辅助编辑、精细 mastery、作文批改与翻译练习深度联动 |

## Issue 对应落地

| GitHub issue | 本次落地 | 仍需后续 |
|---|---|---|
| #2 代码检视与优化 | 私有教材重复上传不跨 learner 复用；RAG embedding 失败记录索引质量；chat 序号约束模型对齐；CI | 统一认证授权、上传后台任务、流式 run 状态恢复 |
| #3 文档一致性 | 更新 `AGENTS.md`、`docs/web-frontend.md`、README 状态摘要和本文档 | 持续给主要架构文档补状态标签 |
| #4 MVP 缺口 | 新增当前 scope/status 表，明确 CET 与七年级教材线边界 | daily lesson answer_required/resume、reading/writing/weekly report |
| #5 下一阶段增强 | RAG search 返回 mode/embedding/chunk/source 信息；model structured output repair retry；CI | vocabulary 多维掌握度、observability dashboard、eval dataset |
| #7 教材练习题升级 | `ExerciseBlueprint` 生成 8 道场景化混合题；支持 `choice_context`、`fill_blank`、`dialogue_complete`、`error_fix`；新增 linter、rubric grader、hint/retry 反馈；前端改为一屏一题练习流；答题事件写入 score、error_type、next_review_signal | 独立 exercise session 表、结束复盘卡、根据 learner mastery 动态选题、micro writing/roleplay |
| #11 词汇模块升级 | 新增 `VocabularyUserOverride`、`VocabularyMistake`、`VocabularyMasteryVector`；词汇详情和练习流读取用户覆盖层；新词学习/今日复习入口分离；用户例句优先参与填空上下文；隐藏释义不进入返回 payload；错因可修正/删除 | 更丰富的题型生成、Dashboard 弱项聚合、roleplay/micro writing 生产题 |
| #12 好句收藏馆 | 新增 `writing_phrases`、练习和 attempt 数据表；提供 CRUD/import/exercises/attempts API；探索页接入好句收藏馆前端工作台 | P2 模型辅助编辑、P3 到期复习/mastery、P4 作文批改和翻译练习自动推荐 |
| #14 Memory Core | 新增 `learning_memory_events`、`memory_operations`、`writing_phrase_masteries`、`memory_context_logs`、`learner_memory_settings`；实现 writer/retriever/curator/explainer/manager；词汇、知识、写作句式、chat/session、作文批改、LangGraph 写入或读取统一 memory；前端新增“我的学习记忆”页面；支持查看 evidence、编辑、删除、禁用、我已改善、导出、手动整理、重置计划、情绪/节奏开关、低置信上下文开关；summary 增加 recent events 和 active weaknesses；metrics 增加 retrieval、hit-rate、used-in-prompt、stale | 更完整 memory debug dashboard 图表、长期 regression eval 扩展 |
| #19 HindSight-inspired Memory | 明确 Memory v2 采用 Retain / Recall / Reflect / Explain / Control；新增 `learning_episodes`、`learner_model_memories`、`teaching_strategy_memories`；`record_event()` 自动补 `evidence_ref`；`MemoryCurator.reflect()` 可从事件生成 episode、learner model、teaching strategy；`MemoryRetriever.for_chat/for_daily_plan/for_vocabulary_practice/for_knowledge_exercise/for_essay_review/for_writing_phrasebook/for_memory_explanation` 已实现；Chat、词汇、教材、作文、写作句式入口使用场景化 recall；用户删除/禁用 learner model 或 strategy 后后续 recall 排除；Memory Center 展示新卡片和指标 | 扩展更多 episode 模板、resolved 状态自动化、teaching strategy 效果评估和 dashboard 可视化 |
| #15 Learner Simulation Agent | 新增 `src/simulation/`、`tests/simulation/` 和 `scripts/run_learner_simulation.py`；至少 5 个内置 persona；3 个 deterministic scenario 覆盖 smoke journey、Vocabulary Agent 沉淀、词汇练习 adaptation；runner 通过 API 调用系统并直接调用 daily lesson graph；每次运行生成结构化 report | 教材知识练习、写作好句、Memory 可控性 regression、LLM-assisted 模式和 simulation dashboard |
| #16 教材解析质量止血 | 新增 `books/manifest.yaml`、parser profile、parser quality report；词汇条目增加 `raw_line`、`confidence`、`warnings` 和 `requires_review`；ingest metadata 写入 manifest/profile/report | layout-aware extractor、低置信人工校对队列和前端工作台 |
| #17 Schema-first 回填 | 新增 `src/extraction`，写作好句导入优先 JSON schema，保留 regex fallback 且返回 `parse_mode`、`warnings`、`confidence`；新增 golden-style tests | 词汇字段回传和语法微课 machine_data 的完整保存链路 |
| #18 Prompt Registry | 新增 `src/prompts`、版本化 markdown 模板、schema/model policy 绑定、`/api/prompts/{prompt_id}/render`；迁移 chat、vocabulary agent、grammar prompt、writing phrase prompt；新增 prompt eval fixtures | 更完整 observability 持久化、prompt evaluator、更多 P2 prompt 迁移 |

## 可运行能力

```bash
./scripts/dev.sh
python -m pytest tests/ -v
cd binnagent-frontend && npm run lint && npm run build
```

## 最近风险

- 多用户远程部署前必须把 learner 身份从请求参数迁移到统一认证依赖。
- 教材 ingest 仍在请求链路内执行，较大 PDF 或 embedding 慢时需要后台任务。
- Daily lesson 仍偏线性流程，尚未真正等待用户输出并恢复到具体 task。
