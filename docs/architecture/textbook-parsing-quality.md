# Textbook Parsing Quality

> 更新时间：2026-07-04
> 目的：定义教材解析质量报告、评分和发布门禁的当前实现契约。

## 数据模型

`parser_runs` 记录每次 `process_uploaded_textbook()`：

- parser identity：`parser_id`、`parser_version`、`parser_profile_id`、`book_manifest_id`。
- input identity：`source_id`、`pdf_sha256`、`input_hash`。
- lifecycle：`running`、`completed`、`failed`，以及 `started_at` / `completed_at`。
- outputs：`quality_report`、`quality_score`、`artifact_refs`、`error_message`。

`KnowledgeSource.metadata` 保存最近一次 run 摘要：

- `latest_parser_run_id`
- `parser_status`
- `parser_report`
- `quality_score`
- `quality_status`
- `blocking_reasons`
- `pending_review_count`
- `pending_blocker_count`
- `review_warning_count`
- `parser_report_summary`

`parser_review_items` 是解析审核队列：

- `target_type` / `target_id` 定位知识点、课程节点、练习题、RAG chunk 或 source 级问题。
- `issue_type` 表示 `low_confidence`、`missing_source_page`、`missing_evidence`、`dirty_token`、`duplicate`、`schema_invalid`、`coverage_gap`、`parser_warning`、`quality_gate_blocker`。
- `severity` 区分 `blocker`、`warning`、`info`。
- `decision` 只能通过 review API 从 `pending` 改为 `confirmed`、`updated` 或 `ignored`。

`ParserReviewItem` 是新的 review source of truth；旧 `requires_review` 字段只作为兼容字段保留。

## ParserQualityReport

报告由 `src/knowledge/parser_report.py` 生成，当前覆盖五组指标：

| 类别 | 指标 |
|---|---|
| intake | `page_count`、`text_char_count`、`avg_text_chars_per_page`、`empty_page_ratio`、`has_text_layer`、`is_scanned_pdf_suspected` |
| structure | `unit_title_match_rate`、`unit_order_valid`、`section_count`、`section_coverage_rate` |
| knowledge | `knowledge_count_by_type`、`source_page_coverage_rate`、`evidence_ref_coverage_rate`、`duplicate_knowledge_count`、`requires_review_count` |
| vocab | `core_vocabulary_hit_rate`、`low_confidence_vocabulary_ratio`、`dirty_token_entry_count` |
| RAG | `rag_chunk_count`、`rag_page_coverage_rate`、`chunk_avg_size` |

这些指标只依赖解析结果、profile、知识点内容和 chunk 切分，便于单元测试和 simulation 回归。

## Golden Parser Evaluation

本批新增离线 golden dataset 评估，用于检查 parser 是否仍命中已知正确样例：

- golden 数据位于 `books/golden/`，当前 profile 为 `pep_grade7_upper`。
- baseline 位于 `var/parser_eval/baselines/pep_grade7_upper.json`。
- CLI 为 `scripts/evaluate_textbook_parser.py`，支持 `--json`、`--all`、`--fail-on-threshold`、`--fail-on-regression` 和 `--update-baseline`。
- 指标覆盖单元标题、单元顺序、词汇 precision/recall/core hit、语法/短语/练习 recall、来源页准确率、重复率、脏 token 率和 review_required precision。

Golden evaluation 不替代 `ParserQualityReport`。前者用于回归已知答案，后者用于每次 ingest 的质量治理和发布门禁。详细用法见 [Textbook Parser Evaluation](./textbook-parser-evaluation.md)。

## TextbookQualityScore

`src/knowledge/quality.py` 将报告转换为 deterministic score：

- `overall_score`
- `structure_score`
- `vocabulary_score`
- `rag_score`
- `provenance_score`
- `status`
- `blocking_reasons`
- `warnings`

当前发布状态：

| 状态 | 含义 |
|---|---|
| `published` | 核心阈值通过且没有待审项 |
| `review_required` | 有低置信、轻量覆盖不足或待人工确认项 |
| `partial_indexed` | 有结构风险但 RAG 至少部分可用 |
| `blocked` | 结构、证据或核心词表缺失到不适合学习使用 |
| `failed` | parser run 失败或疑似扫描 PDF 无可用 text layer |

## 质量门禁

解析成功后，`KnowledgeSource.status = quality_score.status`。解析失败时状态为 `failed`，并保留失败报告和错误摘要。

Review API 在 confirm / update / ignore 后都会重新计算门禁：

1. 更新 review item 的 `decision`。
2. 同步 target 的兼容字段，例如 `requires_review=false`。
3. 统计同一 source 的 `pending_review_count`、`pending_blocker_count` 和 `review_warning_count`。
4. 更新 report 的 `requires_review_count`、`pending_blocker_count` 和 `review_warning_count`。
5. 调用 `score_textbook_quality()`。
6. 回写 `KnowledgeSource.status` 与 metadata 摘要。

因此 `ignore` 只能处理单个 review item，不能绕过 `blocking_reasons`。`blocker` 默认不能 ignore，除非显式传 `allow_blocker_ignore=true` 且记录 `review_note`。

## Review Queue API

- `GET /api/knowledge/sources/{source_id}/review-items`
- `GET /api/knowledge/sources/{source_id}/review-items/{review_item_id}`
- `POST /api/knowledge/sources/{source_id}/review-items/{review_item_id}/confirm`
- `POST /api/knowledge/sources/{source_id}/review-items/{review_item_id}/update`
- `POST /api/knowledge/sources/{source_id}/review-items/{review_item_id}/ignore`

列表支持 `decision`、`severity`、`issue_type`、`target_type` 筛选。操作 payload：

```json
{
  "patch": {
    "title": "hello",
    "source_page": "P.95",
    "content": {
      "confidence": 0.95,
      "source_page": "P.95"
    }
  },
  "review_note": "fixed source page",
  "allow_blocker_ignore": false
}
```

`update` 使用白名单 patch，不允许覆盖 `id`、`source_id`、`parser_run_id` 等危险字段。

## API 暴露

source 列表和详情统一返回：

- `latest_parser_run_id`
- `parser_status`
- `quality_score`
- `quality_status`
- `blocking_reasons`
- `pending_review_count`
- `pending_blocker_count`
- `review_warning_count`
- `parser_report_summary`

`parser_evidence.report` 仍保留完整 report，用于 Dev Console 或解析校对工作台排查。

## Debug Textbook Parsing Report API

Dev Console 新增受 `require_debug_access` 保护的教材解析治理 API：

- `GET /api/debug/textbook-sources`
- `GET /api/debug/textbook-sources/{source_id}/parsing-report`
- `GET /api/debug/textbook-sources/{source_id}/parser-runs`
- `GET /api/debug/textbook-sources/{source_id}/parser-runs/{parser_run_id}`
- `GET /api/debug/textbook-sources/{source_id}/review-items`
- `POST /api/debug/textbook-sources/{source_id}/review-items/{review_item_id}/confirm`
- `POST /api/debug/textbook-sources/{source_id}/review-items/{review_item_id}/update`
- `POST /api/debug/textbook-sources/{source_id}/review-items/{review_item_id}/ignore`
- `GET /api/debug/textbook-sources/{source_id}/evidence`

`/api/debug/textbook-sources` 只返回摘要字段：source title/status、quality status、overall score、latest parser run id/version、pending review/blocker/warning count、blocking reasons 和时间戳，不返回完整 `quality_report` 或大 evidence snapshot。

`/api/debug/textbook-sources/{source_id}/parsing-report` 返回：

- `source`
- `latest_parser_run`
- `quality_score`
- `quality_report`
- `quality_metrics_by_group`
- `blocking_reasons`
- `warnings`
- `pending_review_count`
- `pending_blocker_count`
- `review_summary_by_issue_type`
- `review_summary_by_severity`
- `parser_artifacts`
- `evidence_coverage`

`quality_metrics_by_group` 固定包含 `intake`、`structure`、`vocabulary`、`knowledge`、`rag` 五组。旧数据缺失字段时返回 `null`，以便前端稳定渲染。

ParserRun detail 必须用 `source_id + parser_run_id` 查询；`parser_run.source_id` 不匹配时返回 404，避免跨教材读取。

## Parser Evidence API

Evidence 查询用于从知识点、课程节点、练习题或 RAG chunk 回溯 parser provenance：

```text
GET /api/debug/textbook-sources/{source_id}/evidence?target_type=knowledge_point&target_id=...
GET /api/debug/textbook-sources/{source_id}/evidence?target_type=exercise_question&target_id=...
GET /api/debug/textbook-sources/{source_id}/evidence?target_type=knowledge_chunk&target_id=...
GET /api/debug/textbook-sources/{source_id}/evidence?target_type=curriculum_node&target_id=...
GET /api/debug/textbook-sources/{source_id}/evidence?parser_run_id=...
GET /api/debug/textbook-sources/{source_id}/evidence?issue_type=missing_source_page
```

返回 item 包含 `target_type`、`target_id`、`parser_run_id`、`origin`、`source_page`、`pdf_page`、`raw_line`、`raw_text_excerpt`、`raw_text_span`、`confidence`、`warnings`、`schema_version`、`review_item_ids` 和 `issue_types`。

约束：

- `raw_text_excerpt` 默认最多 500 字符。
- 不返回整本 PDF 原文。
- 不返回 raw LLM prompt/output。
- `target_id` 必须属于当前 `source_id`。
- 缺 evidence 时返回空数组和 warning，不抛 500。

## Dev Console 页面

新增 `/dev/textbooks` 工作台：

- source 列表显示 status、quality status、overall score、latest parser run、pending review/blocker/warning 和 blocking reasons。
- source 详情显示 Source Summary、Quality Score Card、metrics tabs、Review Queue、ParserRun History 和 Evidence Browser。
- ParserRun 详情页面显示完整 run、artifact refs、错误摘要和 related review item summary。
- 大 JSON 均放在折叠区域。
- warning / blocker 用明显视觉样式区分。

## Provenance

- `KnowledgePoint.content.parser_run_id` 标记知识点来源 run。
- 词表知识点保留 `raw_line`、`source_page`、`confidence`、`warnings` 和 `parser_run_id`。
- `KnowledgeChunk.metadata.parser_run_id` 标记 RAG chunk 来源 run。
- 生成练习题写入 `metadata.generated_from`，指向 source、curriculum node、knowledge point 和可用的 parser run。
