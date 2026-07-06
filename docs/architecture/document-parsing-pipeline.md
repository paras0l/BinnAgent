# Document Parsing Pipeline

> 更新时间：2026-07-05

## 背景

教材解析不再继续扩展教材硬编码、seed pack 或 `PEP_GRADE*_KNOWLEDGE` 类兜底路线。第一阶段目标是先把“文档解析”和“教材知识抽取”拆开，让后续 PDF、DOCX、PPTX、HTML 或 OCR-capable engine 都能进入同一个中间表示。

## Pipeline

```text
Upload local file
→ background ingest job
→ ParserRouter
→ MarkItDownEngine baseline
→ PyPdfEngine fallback
→ DocumentParseArtifact
→ DocumentQualityEvaluator
→ TextbookExtractor candidates
→ chunks / review queue / quality gate
```

`POST /api/knowledge/sources/{source_id}/ingest` 返回 `202 Accepted`，只创建或复用 `ParserRun` 并调度后台任务。前端通过 `GET /api/knowledge/sources/{source_id}/ingest-status` 轮询 `stage`、`progress`、`selected_engine`、`attempted_engines` 和 `quality_summary`。

## DocumentParseArtifact

统一 artifact 位于 `src/documents/artifact.py`，字段包括：

- `source_id`
- `parser_engine`
- `parser_version`
- `markdown`
- `pages`
- `blocks`
- `warnings`
- `quality`
- `created_at`

业务层不直接依赖 MarkItDown 或 pypdf 原始返回值，只消费 artifact。

## Engine 定位

MarkItDown 是 baseline engine：负责把上传目录内的本地文件转换成 Markdown。它不是完整 OCR 方案，也不处理远程 URL。依赖未安装、导入失败、转换失败或输出为空时，engine 抛出可识别错误，交给 `ParserRouter` fallback。

pypdf 是第一阶段 fallback / 对照 engine：封装现有 `extract_text()` 能力，输出同样的 `DocumentParseArtifact`。它不支持 OCR，也不承诺版面还原。

## Router 行为

`ParserRouter` 默认顺序：

1. `MarkItDownEngine`
2. `PyPdfEngine`

Router 记录：

- `attempted_engines`
- `selected_engine`
- `fallback_used`
- 每个 engine 的 attempt 状态和错误摘要

当文本层质量弱时，质量评估标记 `needs_ocr=true`。第一阶段只暴露状态和提示，不实现 OCR pipeline。

## 质量评估

`src/documents/quality.py` 评估以下指标：

- `page_count`
- `text_char_count`
- `text_coverage_score`
- `empty_page_ratio`
- `block_count`
- `heading_count`
- `needs_ocr`
- `needs_review`
- `warnings`

质量判断不再只用 `text_char_count` 直接判 failed。低覆盖、空页比例高、缺结构块或缺标题会进入 warning / review / OCR 标记。

## 教材抽取边界

`src/knowledge/textbook_extractor.py` 只接受 `DocumentParseArtifact`，输出 curriculum / knowledge / vocabulary / exercise candidates，并保留 evidence：

- `page_number`
- `block_id`
- `parser_engine`
- `confidence`

它不读 PDF、不依赖 pypdf，也不新增教材硬编码知识字典。教材抽取仍是候选生成，不等于发布到知识库；后续质量门禁和 review queue 决定可用性。

## 状态拆分

第一阶段状态先写入 `KnowledgeSource.metadata_`：

- `processing_status`: `uploaded` / `queued` / `running` / `completed` / `failed`
- `parse_quality_status`: `good` / `needs_review` / `needs_ocr` / `failed`
- `availability_status`: `available` / `partially_available` / `unavailable`

`source.status` 仅保留兼容性的粗流程值，不再作为质量和可用性的唯一来源。
