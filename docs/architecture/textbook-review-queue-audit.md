# Textbook Review Queue Audit

> 更新时间：2026-07-03
> 范围：教材解析后的人工审核、发布门禁和旧 `requires_review` 兼容路径。

## 旧 review 机制

旧机制把待审状态散落在知识点 JSON 中：

- `KnowledgePoint.content.requires_review`
- `KnowledgePoint.content.warnings`
- `KnowledgePoint.content.confidence`
- `KnowledgePoint.content.raw_line`
- `KnowledgePoint.source_page`

旧 API `PATCH /api/learners/{learner_id}/knowledge-base/review-items/{knowledge_point_id}` 直接操作 `KnowledgePoint`：

- `confirm`：发布知识点，清除 `requires_review`。
- `update`：更新 title / summary / source_page，发布知识点，清除 `requires_review`。
- `ignore`：把知识点置为 `ignored`，清除 `requires_review`。

第一阶段质量门禁会在旧 API 后统计剩余 `requires_review=true` 的知识点；如果没有剩余待审项且质量报告达标，`KnowledgeSource.status` 可以变为 `published`。

## 旧机制缺口

旧机制只能追踪“知识点需要审核”，无法独立追踪：

- dirty PDF token。
- 缺 source page。
- 缺 evidence / raw line / origin。
- 重复知识点。
- schema invalid。
- source-level coverage gap。
- TextbookQualityScore blocker。
- curriculum node、exercise question、knowledge chunk 等非知识点产物问题。

因此低质量解析结果可能以单个 `requires_review` 字段的形式被隐藏，前端和 API 也无法区分 warning 与 blocker。

## 新队列

`ParserReviewItem` 是新的 review source of truth。旧 `requires_review` 字段保留为兼容字段，避免旧 API 和前端崩溃。

队列项包含：

- target：`target_type` + `target_id`。
- issue：`issue_type`。
- severity：`blocker` / `warning` / `info`。
- evidence：只保存摘要，如 `raw_line`、`source_page`、`confidence`、`warnings`、`parser_run_id`、`origin`。
- decision：`pending` / `confirmed` / `updated` / `ignored`。

## 兼容策略

- 解析完成后自动从知识点内容、ParserQualityReport 和 TextbookQualityScore 生成 `ParserReviewItem`。
- 旧 `requires_review=true` 会生成 `low_confidence` 或相关 review item。
- 新 review API 修改 decision 时，会同步目标对象的兼容字段，例如把 `requires_review` 置为 false。
- 旧 `review_knowledge_point` API 仍可用；如果目标知识点已有 pending `ParserReviewItem`，旧 API 会同步这些 item 的 decision。

## 发布门禁

Review 后统一重新计算：

- `pending_review_count`
- `pending_blocker_count`
- `review_warning_count`
- `quality_status`
- `blocking_reasons`

发布规则：

- `pending_blocker_count > 0`：不能 `published`。
- `pending_review_count > 0`：不能 `published`，通常为 `review_required`。
- 所有 pending item 清空且质量指标达标：可以 `published`。
- blocker 默认不能直接 ignore；必须显式传 `allow_blocker_ignore=true` 并记录 `review_note`。即使强制忽略，底层质量指标仍可能让教材保持 `blocked` 或 `review_required`。

## 价值

Review Queue 把解析问题从“散落字段”升级为可查询、可统计、可审计的队列，避免低质量解析结果污染学习路径、RAG、Mastery、Memory 和 Recommendation。
