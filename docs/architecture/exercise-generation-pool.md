# 异步练习题池与质量排序

> 实现日期：2026-07-09  
> 适用范围：教材单元练习生成、审核、持久化、选题与前端等待状态。

## 1. 问题与决策

练习生成需要候选生成、确定性校验和独立 LLM 审题，属于秒级到分钟级任务，不适合占用用户请求。最终方案是：

- PostgreSQL 同时保存可用题目和持久化生成任务，API 不同步调用 LLM。
- 独立 `exercise-worker` 领取任务，生成、审核、评分后写入题池。
- 有旧题时立即返回当前最佳题目，同时后台补池；完全没有题时返回 `202 Accepted`。
- 前端根据 `retry_after_seconds` 轮询题池接口；用户也可以离开页面，任务不会因此丢失。
- Redis 不作为题目真相源。当前规模用 PostgreSQL 的行锁、部分唯一索引和租约已足够；未来只有在高并发下需要降低热点读取时才增加 Redis 状态缓存。

不使用 FastAPI `BackgroundTasks` 承载这条链路，因为进程重启会丢失内存任务，也不便于多实例抢占、重试、去重和审计。

## 2. 请求与后台生成链路

```text
POST unit exercises
  -> 查询 published + accepted 题池
  -> 按质量、掌握度、题型和知识点选择最多 8 题
  -> 题池不足 16 或当前生成器题目不足 8：幂等入队
  -> 有题：200 + 当前最佳题目 + pool.status
  -> 无题：202 + generation_run_id + retry_after_seconds

exercise-worker
  -> SELECT ... FOR UPDATE SKIP LOCKED 领取 queued/租约过期任务
  -> coverage plan
  -> exercise.unit_candidates
  -> schema + deterministic quality gate
  -> exercise.unit_review
  -> 六维质量评分 + 硬门槛
  -> accepted 题目写入 exercise_questions
  -> 题池未达到 24：追加补池任务
```

轮询接口：

```text
GET /api/learners/{learner_id}/knowledge-base/units/{node_id}/exercise-pool
```

返回状态：

| 状态 | 含义 | HTTP |
|---|---|---|
| `ready` | 至少 8 题，且无需补池 | 200 |
| `refreshing` | 已有题可做，后台正在补池 | 200 |
| `degraded` | 题量不足且当前无法排入任务；有题返回 200，空池返回 503 | 200/503 |
| `generating` | 当前无题，已入队或等待可生成条件 | 202 |

## 3. 数据模型

`exercise_questions` 新增：

- `quality_score`：0–1 综合质量分，用于题池排序。
- `quality_status`：`accepted` / `rejected` / `retired` 等质量生命周期。
- `generator_version`：区分人工题、旧生成器和当前生成器。
- `quality_dimensions`：保存知识对齐、可作答性、自然度、干扰项、解析、创新度等分项。

`exercise_generation_runs` 是持久化任务表，包含：

- 单元、来源、请求学习者和生成器版本；
- `dedupe_key`、知识点 `input_hash`；
- `queued/running/completed/failed` 状态；
- 优先级、请求数、生成/接受/拒绝数；
- 尝试次数、租约、错误摘要和运行指标。

部分唯一索引只允许同一 `dedupe_key` 存在一个 `queued/running` 任务，避免用户连续点击造成重复生成。完成记录保留用于审计。

## 4. 质量评分与选题

Reviewer 输出六个 0–1 分项，综合分为：

```text
quality =
  0.30 * knowledge_alignment
  + 0.25 * answerability
  + 0.15 * naturalness
  + 0.10 * distractor_quality
  + 0.10 * explanation_quality
  + 0.10 * novelty
```

`knowledge_alignment` 或 `answerability` 低于 `0.75` 时直接拒绝，不能靠其他分项拉高平均分。确定性门禁还检查答案泄露、空格、选项唯一性、场景/rubric 完整性、题型与认知层级覆盖。

返回 8 题不是简单 `ORDER BY quality_score LIMIT 8`。系统先根据学习者知识点掌握度推导目标难度，再以“难度距离 55% + 质量损失 45%”排序，并分三轮保证题型多样性、知识点覆盖和最终题数。因此质量分是准入与排序信号，掌握度和覆盖约束决定个性化组合。

## 5. 容量、降级与恢复

默认参数：

| 参数 | 默认值 | 作用 |
|---|---:|---|
| ready size | 8 | 一次学习会话目标题数 |
| refill threshold | 16 | 低于此数量触发补池 |
| target size | 24 | Worker 最终补充目标 |
| minimum current generated | 8 | 确保旧题池逐步被当前质量链路覆盖 |
| lease | 900 秒 | Worker 崩溃后允许其他实例重领 |
| max attempts | 2 | 有限重试，避免毒任务无限循环 |

降级优先级：

1. 当前生成器且通过双门禁的题。
2. 已验收的教材题或人工题。
3. 数量不足时少返回，不再用固定模板凑满 8 题。
4. 完全无题时返回 202，而不是阻塞请求或返回低质量伪题。

只有一批至少达到 ready size 的新题成功写入后，未经过质量门禁的旧生成题才会归档。任务异常会记录错误并重新排队；超过最大次数转为 `failed`，后续请求仍可使用已有题。

## 6. 运行与运维

Docker Compose 会同时启动 API 与 Worker：

```bash
docker compose up -d
docker compose exec app alembic upgrade head
```

本地可以单独运行：

```bash
.venv/bin/python scripts/run_exercise_worker.py
.venv/bin/python scripts/run_exercise_worker.py --once
```

关键观测指标包括：排队时长、生成耗时、schema/审题通过率、平均质量分、拒绝率、重试率、失败任务数、各单元可用题数、首次请求返回 200/202 比例和用户作答正确率。质量分只代表生成时的静态判断；后续应结合真实作答、歧义反馈和跳过率做题目淘汰。

## 7. 已知边界

- 当前 PostgreSQL 队列适合项目现阶段规模；高吞吐、跨地域或复杂定时任务可迁移到专用队列，但题目与运行审计仍应落库。
- Reviewer 与 generator 当前使用同一模型路由但不同 prompt。更高要求下可将 reviewer 路由到更强模型或加入人工抽检。
- 当前租约按最长正常生成时间配置；生产环境应增加心跳续租和 worker ownership token，进一步防止超长任务被重复领取。
- 当前质量分尚未融合真实学习效果，后续可用题目曝光量、正确率、区分度、投诉/跳过信号做离线重估。
