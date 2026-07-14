# 17. Shared Base Dictionary

## 目标与边界

基础词库是所有学习者共享的只读词典资产，不保存掌握度、笔记、复习状态或任何
`learner_id`。个人词卡仍使用 `VocabularyItem`；共享词典通过 `/api/dictionary` 提供检索，
已有 Dictionary Tool 在数据库会话可用时优先读取共享词库，未命中才走原有本地词典或
LLM fallback。

运行时接入遵循“已有内容不覆盖、缺失内容优先补全”：

- 教材单元批量入词汇本使用一次批量词库查询，教材知识点练习入词汇本与
  `VocabularyStore.add_word()` 也会按规范化词元查询基础词库；个人词卡缺少音标、义项、
  词形、例句或关系字段时优先复制共享内容，保留原始 `source_ref` 和所有已有字段。
- 阅读精读划词翻译先精确查询基础词库；命中带中文释义的常用义项时直接返回并标记
  `source=base_dictionary`，只有未命中或中文义项缺失时才调用
  `reading.selection_translation` 模型。
- 词汇详解页默认从 `/api/dictionary/entries/{term}` 查询共享词条，直接展示常用义项、发音、
  词形、WordNet 关系和 Tatoeba 例句；命中后可通过个人词汇本 `add` 接口写入，缺失字段仍
  由共享词库补全。未命中时才引导进入扩展 HTML 详解生成流程。
- Dev Console 的 `Base Dictionary` 页面通过单一聚合接口展示当前发布版本、活跃词条、类型
  分布、英文义项、中文释义、例句和 WordNet 关系覆盖率，以及构建参数与来源清单。

首版构建目标：

- 约 10,000 个常用英文词元；
- 另选高频短语、固定表达和短语动词，默认上限 2,000；
- 每个词条保留 1–3 个现代常用英文义项；
- Kaikki/Wiktionary 提供词头、词性、音标、词形和英文释义；
- Princeton WordNet 3.0 只补语义关系；
- Tatoeba 英中句对只补例句及例句译文；
- `wordfreq` Zipf frequency 负责门槛与排序；
- 中文义项由单独、可追踪的 PromptExecutor 阶段生成，不改写来源英文义项。

## 数据模型

| 表 | 内容 |
|---|---|
| `base_dictionary_builds` | 构建版本、来源清单、筛选参数、数量统计和发布状态 |
| `base_dictionary_entries` | 共享英文词条、1–3 个义项、关系、例句、频率和来源署名 |
| `base_dictionary_translations` | 以 `entry_id + sense_key + locale` 独立保存生成的中文释义 |

中文释义保存英文义项哈希、prompt 版本、生成模型与置信度。以后英文来源义项变化时，
可用哈希识别过期译文并重新生成。

## 确定性筛选

`src/base_dictionary/pipeline.py` 使用以下规则：

1. Unicode NFKC、统一大小写和空格后按 canonical key 聚合 Kaikki 词性变体。
2. 排除 `archaic / dated / historical / obsolete / rare / reconstruction` 义项。
3. 按 Kaikki 原始顺序去重，最多保留 3 个当前义项。
4. 单词与多词表达使用独立配额，避免短语挤占约 10,000 个词元目标。
5. 默认单词最低 Zipf 2.5、短语最低 Zipf 2.0，再按 Zipf 降序稳定排序。
6. `verb + particle` 识别为 `phrasal_verb`，其他多词条目归为 `phrase` 或
   `fixed_expression`。
7. WordNet 对每个词条最多取前三个 synset，并限制每类关系数量。
8. Tatoeba 例句必须覆盖完整词元/短语，排除 URL、过长文本，优先约 12 词的句子，
   每条最多保留 3 句。

## 构建与发布

原始语料和生成的完整 JSONL 都属于本地构建资产，不提交仓库。先安装可选构建依赖：

```bash
pip install -e ".[dictionary]"
.venv/bin/python -m nltk.downloader wordnet
```

从 [Kaikki English dictionary](https://kaikki.org/dictionary/English/)、
[Tatoeba Downloads](https://tatoeba.org/en/downloads) 获取带版本日期的原始文件。
Tatoeba 使用 English → Mandarin Chinese 的 custom sentence-pair TSV（四列依次为英文
sentence id、英文文本、中文 sentence id、中文文本）。

```bash
.venv/bin/python scripts/build_base_dictionary.py prepare-tatoeba \
  --english var/dictionary/raw/tatoeba/eng_sentences.tsv.bz2 \
  --chinese var/dictionary/raw/tatoeba/cmn_sentences.tsv.bz2 \
  --links var/dictionary/raw/tatoeba/links.tar.bz2 \
  --output var/dictionary/raw/tatoeba-eng-cmn.tsv

.venv/bin/python scripts/build_base_dictionary.py build \
  --kaikki var/dictionary/raw/kaikki-en.jsonl \
  --tatoeba var/dictionary/raw/tatoeba-eng-cmn.tsv \
  --output var/dictionary/staged/base-dictionary-2026-07-12.jsonl

alembic upgrade head

.venv/bin/python scripts/build_base_dictionary.py load \
  --input var/dictionary/staged/base-dictionary-2026-07-12.jsonl \
  --version 2026-07-12.1 \
  --kaikki-version 2026-07-12 \
  --tatoeba-version 2026-07-12

.venv/bin/python scripts/build_base_dictionary.py translate-zh \
  --limit 1000 --batch-size 12
```

`build` 不连接数据库；相同输入和依赖版本产生稳定排序。`load` 保存 staged 文件 SHA-256
并幂等 upsert，当前构建中消失的旧条目标记为 inactive。中文生成支持分批重复执行，已存在
译文的词条默认跳过。

当前开发数据库已发布 `2026-07-13.2`：12,000 个活跃词条，其中 10,000 个词元、
1,566 个短语、434 个短语动词；9,535 条带 WordNet 关系，8,623 条带 Tatoeba 例句。
中文义项使用 LongCat 分批续跑，Dev Console 直接展示实时覆盖率，不把未完成批次伪装成
完整覆盖。

## 来源与许可

- Kaikki 数据来自 Wiktionary 提取结果；发布或分发构建产物时必须保留其中要求的
  Wiktionary/Kaikki 署名与相应许可证信息。
- Princeton WordNet 3.0 允许免费使用、复制、修改和分发，但要求保留版权声明与免责声明；
  见 [WordNet license](https://wordnet.princeton.edu/license-and-commercial-use)。
- Tatoeba 文本默认使用 CC BY 2.0 FR，部分句子为 CC0；本实现保存 sentence id 与来源，
  见 [Tatoeba downloads](https://tatoeba.org/en/downloads)。
- `wordfreq` 只参与评分，不把其内部频率表作为独立数据源对外发布。部署前仍需按目标分发方式
  完成一次完整许可证审查，并在产品词典页展示来源署名。

## 验收

```bash
.venv/bin/python -m pytest tests/base_dictionary tests/db/test_migrations.py -q
.venv/bin/ruff check src/base_dictionary src/models/base_dictionary.py \
  src/api/base_dictionary.py scripts/build_base_dictionary.py
```

正式数据验收还应检查：词元数量接近 10,000、每条义项数为 1–3、排名无重复、中文译文
覆盖率、例句覆盖率、来源字段完整率，以及随机分层抽样中的释义与短语质量。
