# Textbook Parsing Dev Console Audit

> 更新时间：2026-07-04
> 范围：教材解析质量治理在 Dev Console 中的 API、页面和 evidence 查询入口。

## 当前 Dev Console 页面

本次改造前，Dev Console 已有：

- Learners：选择 learner context。
- Recent Episodes / Graph Runs：查看 AgentEpisode、checkpoint、events、tool calls、VerificationReport 和 evidence refs。
- Memory Debug：查看和治理 Memory v2 数据。
- Tool Registry / Tool Call Records：查看工具注册与调用记录。
- Evidence Debug：解析 runtime evidence refs。
- RAG Debug：按 query/source/node 检索 chunk。
- Prompt Debug：渲染 prompt 与查看 prompt execution。
- VerificationReport：按 episode 查看验证报告。
- Simulation Report：查看 simulation scenarios 与 latest report。

本次新增 Textbook Parsing Dev Console：

- `/dev/textbooks`
- `/dev/textbooks/:sourceId`
- `/dev/textbooks/:sourceId/parser-runs/:parserRunId`

## KnowledgeSource 当前可见字段

普通学习端 `GET /api/learners/{learner_id}/knowledge-base` 已返回：

- `source` / `sources[]`：title、filename、grade、volume、status、unit_count、knowledge_count、page_count。
- 质量摘要：`latest_parser_run_id`、`parser_status`、`quality_score`、`quality_status`、`blocking_reasons`、`pending_review_count`、`pending_blocker_count`、`review_warning_count`、`parser_report_summary`。
- `parser_evidence`：parser/profile/manifest/vocab parser、RAG chunk count、text char count、warnings 和完整 parser report。
- `review.items`：旧兼容的 low-confidence knowledge point review 列表。

普通学习端不会展示整本 PDF 原文；只展示知识点、页码、raw line 摘要和必要解析 warning。

## Review API 与前端入口

已有 Review Queue API：

- `GET /api/knowledge/sources/{source_id}/review-items`
- `GET /api/knowledge/sources/{source_id}/review-items/{review_item_id}`
- `POST /api/knowledge/sources/{source_id}/review-items/{review_item_id}/confirm`
- `POST /api/knowledge/sources/{source_id}/review-items/{review_item_id}/update`
- `POST /api/knowledge/sources/{source_id}/review-items/{review_item_id}/ignore`

本次补齐：

- 列表支持 `parser_run_id` 筛选。
- item 返回 `created_at`。
- 操作响应增加 `source_quality_summary`，和 `source` / `summary` / `item` 一起返回。
- blocker ignore 错误信息明确要求 `allow_blocker_ignore=true` 和 `review_note`。

前端入口：

- 普通学习端 KnowledgeBase 的“解析校对” workspace 继续处理学习者可见的低置信词条。
- Dev Console Textbook Parsing 页面处理 source-level、ParserRun-level、review queue 和 evidence debug。

## ParserRun / Quality / Review / Evidence API

本次新增 Debug API，全部受 `require_debug_access` 保护：

- `GET /api/debug/textbook-sources`
- `GET /api/debug/textbook-sources/{source_id}/parsing-report`
- `GET /api/debug/textbook-sources/{source_id}/parser-runs`
- `GET /api/debug/textbook-sources/{source_id}/parser-runs/{parser_run_id}`
- `GET /api/debug/textbook-sources/{source_id}/review-items`
- `POST /api/debug/textbook-sources/{source_id}/review-items/{review_item_id}/confirm`
- `POST /api/debug/textbook-sources/{source_id}/review-items/{review_item_id}/update`
- `POST /api/debug/textbook-sources/{source_id}/review-items/{review_item_id}/ignore`
- `GET /api/debug/textbook-sources/{source_id}/evidence`

`/api/debug/textbook-sources` 只返回摘要：

- source id/title/status。
- quality status / overall score。
- latest parser run id/version/status。
- pending review/blocker/warning count。
- blocking reasons。
- created / updated time。

`/api/debug/textbook-sources/{source_id}/parsing-report` 返回：

- source summary。
- latest parser run summary。
- quality score。
- quality report。
- `quality_metrics_by_group`：intake、structure、vocabulary、knowledge、rag。
- blocking reasons / warnings。
- pending review count / blocker count / warning count。
- review summary by issue type / severity。
- parser artifact summary。
- evidence coverage summary。

字段缺失时返回 `null` 或空对象，保持 schema 稳定，不因为旧数据缺 metrics 抛 500。

## Parser Evidence 查询

Evidence API 支持：

```text
GET /api/debug/textbook-sources/{source_id}/evidence?target_type=knowledge_point&target_id=...
GET /api/debug/textbook-sources/{source_id}/evidence?target_type=exercise_question&target_id=...
GET /api/debug/textbook-sources/{source_id}/evidence?target_type=knowledge_chunk&target_id=...
GET /api/debug/textbook-sources/{source_id}/evidence?target_type=curriculum_node&target_id=...
GET /api/debug/textbook-sources/{source_id}/evidence?parser_run_id=...
GET /api/debug/textbook-sources/{source_id}/evidence?issue_type=missing_source_page
```

返回的 evidence item 包含：

- `target_type` / `target_id`
- `parser_run_id`
- `origin`
- `source_page` / `pdf_page`
- `raw_line`
- `raw_text_excerpt`
- `raw_text_span`
- `confidence`
- `warnings`
- `schema_version`
- `review_item_ids`
- `issue_types`

`raw_text_excerpt` 默认最多 500 字符。API 不返回整本 PDF 文本，也不返回 raw LLM prompt/output。缺 evidence 时返回空数组和 warning；`target_id` 不属于 `source_id` 时返回 404。

## 页面能力

`/dev/textbooks`：

- 展示教材 source 摘要、状态、质量状态、分数、latest ParserRun、pending review/blocker/warning 和 blocking reasons。
- 支持 status / quality_status 过滤。

`/dev/textbooks/:sourceId`：

- Source Summary。
- Quality Score Card。
- Metrics Tabs：intake、structure、vocabulary、knowledge、rag。
- Review Queue：选择 item 后可 confirm / update / ignore，并查看 selected item JSON。
- ParserRun History：查看每次 run 状态、耗时、分数和错误摘要。
- Evidence Browser：按 target、issue type 或 parser run 查询 evidence。
- 大 JSON 只放折叠区域。

`/dev/textbooks/:sourceId/parser-runs/:parserRunId`：

- 展示 ParserRun 完整详情、artifact refs、错误信息和 related review items。
- `source_id` 与 `parser_run.source_id` 必须匹配，否则返回 404。

## 仍未实现

本次没有引入：

- OCR。
- LLM parser。
- multi-parser registry。
- golden dataset parser eval。
- layout-aware extractor。
- 后台 ingest 任务队列。

这些仍属于后续质量治理和回归评估工作。
