# Textbook Parser Evaluation Audit

> 更新时间：2026-07-04
> 范围：教材解析 profile、fixture、ParserQualityReport 和 golden parser regression 的当前实现边界。

## 当前 Parser Profile

`src/knowledge/parser_profiles.py` 目前内置两个 profile：

| profile | 作用 |
|---|---|
| `pep_grade7_upper_v1` | 人教版七年级上册；包含期望单元标题、核心词汇、最低词汇量和 dirty token 规则 |
| `pep_grade7_lower_v1` | 人教版七年级下册；包含期望单元标题、核心词汇和最低词汇量 |

Profile 服务于 ingest 阶段的 deterministic 质量报告；golden evaluation 使用 `books/golden/{profile}/manifest.json` 将 golden profile 映射到这些 parser profile。

## 当前 Fixture 现状

- 真实教材 PDF 仍位于 `docs/books/`，由 `books/manifest.yaml` 记录教材元信息。
- 仓库此前没有独立的 `tests/fixtures/textbooks/` golden fixture 目录。
- 本批新增 `books/golden/pep_grade7_upper/`，只保存结构化期望 JSON，不保存整本教材长文本。
- CLI 测试使用临时 JSON fixture，避免在单元测试中反复解析 PDF。

## 当前 Parser 输出

教材 ingest 主链路仍是：

```text
process_uploaded_textbook()
-> _parse_pdf() / pypdf text layer
-> _parse_unit_vocabulary()
-> CurriculumNode / KnowledgePoint / KnowledgeChunk
-> ParserQualityReport
-> TextbookQualityScore / ParserReviewItem
```

主要输出对象：

- `ParsedTextbook` / `ParsedUnit`：单元结构、页码和文本片段。
- `ParsedVocabularyEntry`：词条表达、规范化表达、单元、原始行、置信度、warning 和 `requires_review`。
- `ParserQualityReport`：intake / structure / knowledge / vocab / RAG 指标。
- `TextbookQualityScore`：发布门禁状态。
- `ParserReviewItem`：低置信、脏 token、缺证据等人工审核项。

## Golden Evaluation 定位

`ParserQualityReport` 回答“这次 ingest 自身看起来是否健康”，例如空页、核心词命中、RAG 覆盖和待审数量。

Golden evaluation 回答“当前 parser 是否仍能抽中已知正确答案”，例如指定单元标题、核心词汇、语法点、短语和来源页是否匹配。它不替代 ParserRun，也不写入业务数据库。

## MVP Profile

当前 MVP golden profile：

| golden profile | source fixture | parser profile | 覆盖 |
|---|---|---|---|
| `pep_grade7_upper` | `docs/books/义务教育教科书·英语七年级上册.pdf` | `pep_grade7_upper_v1` | 12 个单元、少量核心词/短语、3 个语法点、空 exercises 集合 |

该 profile 重点约束稳定信号：单元标题、核心词命中、语法/短语召回、来源页、脏 token 和重复率。`unit_order_accuracy` 目前只记录 baseline，不作为硬阈值，因为当前 pypdf text layer 解析顺序仍会受版式影响。

## 非目标

本批没有引入 OCR、pdfplumber、layout-aware extractor、LLM parser 或 parser registry。解析仍使用现有 pypdf/text-layer 逻辑；新增能力是 golden dataset、指标计算、baseline comparison 和 CLI gate。

## 后续建议

- 为七年级下册、八年级、九年级补 golden profile。
- 将 exercises expected 从空集合扩展为可校验题型样例。
- 增加 layout-aware extractor 后，把同一 golden dataset 用作 parser registry 对比。
- 在 CI 中对 changed parser path 运行 `--fail-on-threshold --fail-on-regression`。
