# Textbook Parser Evaluation

> 更新时间：2026-07-04
> 目的：说明教材解析 golden dataset、评估指标、baseline 和回归门禁的使用方式。

## Golden Dataset

Golden dataset 位于 `books/golden/`。每个 profile 一个目录：

```text
books/golden/{profile_id}/
├── manifest.json
├── units.expected.json
├── vocabulary.expected.json
├── grammar.expected.json
├── phrases.expected.json
└── exercises.expected.json
```

当前 profile：

- `pep_grade7_upper`：人教版七年级上册 parser evaluation MVP。

这些 JSON 只保存短结构化期望，不保存整页教材原文或长段落。`manifest.json` 的 `source_fixture` 可以指向真实 PDF，也可以指向 CLI 测试用 JSON fixture。

## Expected Schema

| 文件 | 必填字段 |
|---|---|
| `units.expected.json` | `unit_id`、`title`、`order`、`expected_source_pages` |
| `vocabulary.expected.json` | `text`、`normalized_text`、`unit_id`、`part_of_speech`、`chinese_meaning`、`source_page`、`is_core` |
| `grammar.expected.json` | `topic`、`unit_id`、`source_page`、`keywords` |
| `phrases.expected.json` | `text`、`normalized_text`、`unit_id`、`source_page` |
| `exercises.expected.json` | `question_key`、`unit_id`、`source_page`、`answer_required`、`knowledge_refs` |

空集合必须显式写成 `[]`，这样 schema 校验和报告字段可以保持稳定。

## CLI

运行单个 profile：

```bash
python scripts/evaluate_textbook_parser.py --profile pep_grade7_upper --json
```

运行所有 profile：

```bash
python scripts/evaluate_textbook_parser.py --all --json
```

门禁参数：

```bash
python scripts/evaluate_textbook_parser.py \
  --profile pep_grade7_upper \
  --fail-on-threshold \
  --fail-on-regression
```

更新 baseline：

```bash
python scripts/evaluate_textbook_parser.py \
  --profile pep_grade7_upper \
  --update-baseline \
  --json
```

`--update-baseline` 只应在确认 parser 行为变化是有意且健康后使用，不能用来掩盖回归。

报告默认写入 `var/parser_eval/`：

- `{profile_id}_{timestamp}.json`
- `latest_report.json`

这些运行报告是本地产物，不提交。可提交 baseline 位于 `var/parser_eval/baselines/{profile_id}.json`。

## Metrics

| 指标 | 计算口径 |
|---|---|
| `unit_title_exact_match` | 期望单元标题经 normalization 后被解析命中的比例 |
| `unit_order_accuracy` | 期望单元顺序位置与实际顺序一致的比例 |
| `vocabulary_precision` | 实际词汇条目中命中 expected vocabulary 的比例，重复实际条目会计入分母 |
| `vocabulary_recall` | expected vocabulary 被解析命中的比例 |
| `core_vocabulary_hit_rate` | `is_core=true` 的 expected vocabulary 被命中的比例 |
| `grammar_topic_recall` | expected grammar topic 被命中的比例 |
| `phrase_recall` | expected phrase 被命中的比例 |
| `exercise_recall` | expected exercise 被命中的比例；expected 为空时为 `null` |
| `source_page_accuracy` | 已命中 item 的 `source_page` 匹配比例 |
| `duplicate_rate` | vocabulary / grammar / phrase / exercise 实际输出中重复 key 的比例 |
| `dirty_token_rate` | 实际输出中包含配置脏 token 的条目比例 |
| `review_required_precision` | 被标为 `requires_review` 的条目中确有 warning、低置信、缺页码或脏 token 的比例 |

文本匹配会做大小写、空白、标点和中英文破折号规范化。页码匹配会忽略 `P.` 前缀和空白。

## Baseline 与 Threshold

Baseline 示例：

```json
{
  "profile_id": "pep_grade7_upper",
  "version": 1,
  "metrics": {
    "unit_title_exact_match": 1.0,
    "vocabulary_recall": 1.0
  },
  "thresholds": {
    "unit_title_exact_match": { "min": 1.0 },
    "dirty_token_rate": { "max": 0.02 }
  }
}
```

回归方向：

- 命中率、召回率、准确率类指标下降视为 regression。
- `dirty_token_rate`、`duplicate_rate` 上升视为 regression。
- threshold 支持 `min` 和 `max`。

缺 baseline 不会失败；报告会记录 `baseline_found=false`。

## CI 建议

Parser 相关路径变化时可运行：

```bash
python scripts/evaluate_textbook_parser.py \
  --profile pep_grade7_upper \
  --fail-on-threshold \
  --fail-on-regression
```

当前没有把 PDF parser evaluation 强制放入全量测试，因为真实 PDF 解析比单元测试慢。单元测试通过 JSON fixture 覆盖 CLI、schema、指标和 baseline 逻辑。

## 当前边界

- 不引入 OCR、pdfplumber、layout-aware extractor、LLM parser 或 parser registry。
- 不把 golden evaluation 写入 `ParserRun` 表。
- 不在 expected JSON 中保存整页教材内容。
- exercises expected 暂为空，后续应补代表性题型样例。
