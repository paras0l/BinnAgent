# Textbook Parsing Audit

> 更新时间：2026-07-03
> 范围：教材 PDF 上传后的解析、知识点生成、RAG chunk、校对入口和 API 暴露链路。

## 当前链路

```text
KnowledgeSource(uploaded)
-> process_uploaded_textbook()
-> _parse_pdf / PdfReader text layer
-> parser profile / manifest fallback
-> CurriculumNode / KnowledgePoint
-> build_chunks()
-> parser_report metadata
-> KnowledgeBase overview / review queue
```

## 已有能力

- 支持七年级上/下册 manifest 与 parser profile。
- PDF text layer 可生成单元、词表、附录知识点和 RAG chunks。
- 词表条目已保存 `raw_line`、`confidence`、`warnings`、`requires_review`。
- KnowledgeBase overview 已能显示 parser evidence 和低置信 review queue。
- 未知教材有“全册材料”fallback，可至少生成 RAG chunk 和人工校对入口。

## 主要风险

| 风险 | 影响 | 新增治理 |
|---|---|---|
| 解析运行没有独立审计实体 | 无法回答“本批知识来自哪次 parser run” | 新增 `parser_runs` 表记录 run、报告、评分、错误和 artifact refs |
| `KnowledgeSource.status` 由局部状态拼接 | RAG 失败、待审、结构缺失之间语义混杂 | 新增 `TextbookQualityScore` 统一输出 `published/review_required/partial_indexed/blocked/failed` |
| parser report 偏词表 | 扫描 PDF、空页、页码覆盖、RAG 覆盖不可见 | 扩展 intake / structure / knowledge / vocab / RAG 五类指标 |
| 校对完成后直接发布 | `ignore` 可能绕过结构或证据 blocker | Review API 重算质量门禁，blocker 保持阻断 |
| provenance 不完整 | 知识点、词表、chunk 难以回溯到解析批次 | `parser_run_id` 写入 KnowledgePoint content 和 KnowledgeChunk metadata |

## 审计结论

教材解析已能支撑本地 MVP，但此前更像“生成结果”而非“可治理 ingest pipeline”。第 27 批改造后，解析链路具备三层治理：

1. `ParserRun`：记录每次解析执行和产物引用。
2. `ParserQualityReport`：给出 deterministic、可测试的解析质量指标。
3. `TextbookQualityScore`：把指标转换成可被 API、前端和审核流程共用的发布门禁。

后续仍建议补 layout-aware extractor、批量校对审计历史、golden PDF 回归集和后台 ingest 任务队列。
