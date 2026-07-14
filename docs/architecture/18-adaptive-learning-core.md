# 18. Adaptive Learning Core

## 目标与边界

自适应学习核心把开放交互收敛为可审计的学习证据，再分别处理当前能力、长期记忆和教学决策。各模型不合并为单一总分：

- `AssessmentEvidence` 判断交互是否有资格更新状态；
- Rasch/1PL IRT 解释能力、题目难度与成功概率；
- FSRS/DSR 状态维护 Difficulty、Stability、Retrievability 和复习时间；
- DKT 仅做影子预测，默认不影响线上教学；
- `TeachingPolicyCompiler` 把状态编译为受约束的难度、提示与练习形式。

## 数据链

```text
ExerciseAttempt
  → AssessmentEvidence
  → KnowledgeStateUpdate + FSRSReviewState + DKTShadowPrediction
  → TeachingPolicyDecision
  → DecisionTrace
  → PromptExecutionRecord.adaptive_policy_snapshot
```

`attempt_id` 在 AssessmentEvidence 上唯一，重复事件不会再次更新状态。低语义置信度证据会保留，但 `updates_learning_state=false`；浏览、解释和答案揭示不属于评测证据。每次状态更新保留 evidence refs、算法版本、输入快照和 fallback 状态。

学习者纠正系统评分时，`EvidenceCorrectionService` 会标记原证据失效、保留原因和原 DecisionTrace，再按时间顺序重放剩余有效证据，重建 IRT 掌握状态与 FSRS 调度；若没有剩余有效证据，则清空派生复习状态。

## 算法约束

IRT 首版使用 1PL，并按独立性、提示和重试降低证据权重。FSRS rating 由确定性规则隐式映射：错误为 Again，提示或重试后正确为 Hard，独立正确为 Good，快速独立或迁移成功为 Easy。所有调度逻辑接受可注入 `Clock`，测试不依赖真实等待。

DKT 使用 `BINN_DKT_SHADOW_ENABLED=true` 记录预测；`BINN_DKT_POLICY_ENABLED` 默认关闭。提供者不可用时写入 baseline 预测和错误摘要，不阻断练习。只有显式启用策略开关后，DKT 预测才进入策略编译。

## Feature flags

| 环境变量 | 默认值 | 作用 |
|---|---:|---|
| `BINN_ADAPTIVE_LEARNING_ENABLED` | `true` | 启用结构化自适应链 |
| `BINN_ADAPTIVE_SEMANTIC_CONFIDENCE_THRESHOLD` | `0.65` | 控制状态更新置信阈值 |
| `BINN_DKT_SHADOW_ENABLED` | `true` | 记录 DKT 影子预测 |
| `BINN_DKT_POLICY_ENABLED` | `false` | 允许 DKT 影响教学策略 |

## 验收

```bash
.venv/bin/python -m pytest tests/assessment tests/mastery tests/review tests/policy -q
.venv/bin/python scripts/validate_adaptive_learning.py --all
.venv/bin/python scripts/validate_adaptive_learning.py --all --json
.venv/bin/ruff check src tests scripts
```

一键脚本覆盖独立/提示作答、低置信阻断、浏览排除、IRT 单调性、FSRS 时间旅行、DKT fallback、低/高掌握策略、幂等约束和 trace 完整性。它验证工程行为，不代表 DKT 已优于真实业务 baseline；真实模型继续保持 shadow mode，待跨学习者序列数据足够后再做按学习者和时间隔离的离线评估。
