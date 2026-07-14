# 19. Grammar Can-do Core

## 目标与边界

语法核心把“现在完成时”“定语从句”等课程主题拆成一次聚焦练习能够判断的 can-do KnowledgePoint。当前目录已扩展为论文口径的 1,211 个带 CEFR learner examples 的 English Grammar Profile（EGP）语法项；课程主题仍负责教学顺序，can-do 点负责证据和掌握追踪。

## 数据模型

- `KnowledgePoint` 是全局可追踪实体。全局 can-do 不强制属于单一教材，因此 `source_id` 和 `curriculum_node_id` 可空。
- `GrammarCanDoProfile` 一对一保存 EGP ID、category、subcategory、CEFR、FORM/USE、guideword、lexical range、成功/失败标准、learner examples、先修点、检测提示和来源致谢。
- `GrammarCurriculumMapping` 将同一个 can-do 映射到多个教材单元，并记录关系、来源和置信度。
- 学习状态继续复用 `LearnerKnowledgeState`、`AssessmentEvidence`、`KnowledgeStateUpdate`、`FSRSReviewState` 和 `DKTShadowPrediction`，不另建平行掌握系统。

迁移 `a7b8c9d0e1f3` 创建画像和映射表，`b8c9d0e1f2a4` 增加 EGP 编号、guideword、lexical range 和来源字段。导入器以 `grammar.egp.{EGP ID}` 和 UUIDv5 建立稳定身份，重复导入不会重复数据。原 `g7-v1` 30 点会归档但不删除，已有学习证据仍然保留。

## 完整目录导入

官网当前导出有 1,222 行，其中 1,215 行 Example 非空。论文的 1,211 项口径按以下可复现规则得到：

1. can-do 和 Example 均非空；
2. Example 包含 A1–C2 learner metadata；
3. EGP ID 唯一；
4. 最终必须恰好为 1,211 项，否则导入失败。

当前快照统计见 `data/grammar/egp_1211_manifest.json`：1,211 个语法项、3,600 个 learner examples、19 个 SuperCategory，覆盖 A1–C2。

EGP 内容受 Cambridge 条款约束，原始导出不提交到 Git。取得合法下载后放入：

```text
data/private/egp/egponline.csv
```

执行：

```bash
.venv/bin/python scripts/import_egp_catalog.py \
  data/private/egp/egponline.csv \
  --validate-only \
  --manifest data/grammar/egp_1211_manifest.json

alembic upgrade head

.venv/bin/python scripts/import_egp_catalog.py \
  data/private/egp/egponline.csv
```

导入器是幂等的。部署环境必须单独获得授权快照；不能从仓库恢复 learner examples。

## 证据与状态

`AssessmentEvidence.evidence_mode` 使用 `recognition`、`recall`、`production`。API 只聚合 `updates_learning_state=true` 且未失效的证据；提示后完成会降低权重，语义置信度参与维度分数和置信度计算。

用户端状态由证据而非“完成”按钮推导：

- `stable`：掌握度至少 0.8，且当前可提取率没有跌破稳定阈值；
- `forming`：已有有效证据，能力仍在形成；
- `review`：已到复习时间或 FSRS 可提取率低于 0.6；
- `repeated_failure`：最近两次有效证据均低于 0.5；
- `no_evidence`：没有可用于更新学习状态的证据。

## API

- `GET /api/learners/{learner_id}/grammar/map`：返回 1,211 个 can-do、目录/例句总数、来源致谢、三维掌握度和 category × CEFR 矩阵。
- `GET /api/learners/{learner_id}/grammar/can-do/{point_id}`：返回判断标准、例句、FSRS 状态和最近 20 条证据轨迹。

两个接口都经过 current-user / learner ownership 校验。HTML 微课缓存接口保持原有兼容路径。

## 前端

Grammar Workspace 默认进入“语法地图”：

1. 第一层用 19 类 × CEFR 矩阵展示稳定/形成/复习/失败/无证据状态；
2. 第二层支持 EGP ID、can-do、guideword 搜索，以及 CEFR/类别筛选和分批渲染；
3. 详情侧栏显示 EGP ID、guideword、全部 learner examples、独立成功率、证据置信度、辨认/回忆/产出、下次复习、判断标准和最近证据；
4. 页面展示 EGP 指定致谢和来源链接。

原知识点微课生成、HTML 预览和练习工作区继续保留。

## 后续扩展

- 将 1,211 个 can-do 与教材 `CurriculumNode` 建立分册、人工审核的稀疏映射；
- 让 Grammar Workspace 创建的练习直接绑定 can-do UUID，而不是旧的 topic slug；
- 为 Expression Lab 增加 schema-first 的成功/失败/未尝试/无关错误检测 prompt 与 eval set；
- 在 Dev Console 增加完整 IRT、DKT、FSRS 曲线和模型版本切换标记；
- 用真实标注数据校准检测阈值，不能用 baseline 更新掩盖识别回归。

## 来源与许可

- English Grammar Profile：<https://englishprofile.org/?menu=egp-online>
- 使用条款：<https://englishprofile.org/?menu=egp-terms-of-use>
- 引用：O’Keeffe, A. and Mark, G. (2017), *The English Grammar Profile of learner competence: Methodology and key findings*。

EGP 原始内容只允许在条款授权范围内使用。仓库仅提交导入代码、结构和不含原文的聚合 manifest；任何公开发布或商业用途均需自行确认并取得 Cambridge 的书面许可。
