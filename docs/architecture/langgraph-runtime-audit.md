# LangGraph Runtime Audit

> 更新时间：2026-07-03

## 结论

当前 Daily Lesson 已从“出题后直接结束或跳到反馈”的早期链路，升级为可暂停、可恢复、可验证的单题学习闭环。

- LangGraph 编译层支持可选 checkpointer：`build_graph(checkpointer=None)`、`build_resume_graph(start_node="grade_attempt", checkpointer=None)`。
- `build_checkpointer(kind="memory")` 可为测试和本地实验创建 `InMemorySaver`；默认 `None` 不改变生产行为。
- 项目内 `LearningGraphCheckpoint` 仍是业务 checkpoint，用于前端刷新恢复题面、schema、episode/checkpoint 状态；它不是 LangGraph checkpoint。
- 稳定 thread id 使用 `daily-lesson:{episode_id}`，graph invoke 始终传 `{"configurable": {"thread_id": thread_id}}`。
- 恢复默认从 `grade_attempt` 进入，避免跳过评分、掌握度、记忆、复习和推荐节点。

## 当前 Daily Lesson 链路

```text
load_profile
-> detect_intent
-> select_learning_goal
-> route_skill_agent
-> run_learning_task
-> wait_for_answer
-> grade_attempt
-> update_mastery
-> generate_feedback
-> update_memory
-> schedule_review
-> recommend_learning_action
-> verify_episode
-> summarize_session
```

`wait_for_answer` 是 interrupt-compatible 节点。没有答案时，它只返回：

- `answer_required=true`
- `current_task_id`
- `prompt_payload`
- `required_input_schema`
- `resume_from="grade_attempt"`
- `checkpoint_status="waiting_user"`

随后 graph 路由到 `END`，不会执行 `grade_attempt`、`update_memory`、`schedule_review` 等副作用节点。有答案时，graph 继续进入 `grade_attempt`。

## 新增状态字段

`LearningGraphState` 已补齐闭环字段：

- `exercise_attempt_id`
- `grade_result`
- `wrong_reason`
- `knowledge_point_ids`
- `evidence_refs`
- `mastery_update`
- `memory_write_result`
- `review_schedule_result`
- `recommended_action`
- `recommendation_result`
- `prompt_payload`
- `required_input_schema`

`side_effect_mode="dry_run"` 用于 orchestrator 恢复时运行 graph 状态闭环，但不让 graph 节点重复写 DB。

## 节点边界

| 节点 | 当前职责 |
|---|---|
| `wait_for_answer` | 生成前端题面和输入 schema；缺答案时暂停 |
| `grade_attempt` | 复用 `grade_exercise_answer` 的评分语义，生成稳定 `exercise_attempt_id` 和 evidence refs |
| `update_mastery` | 输出与 `MasteryUpdateResult` 兼容的 rule fallback；真实 DB mastery 写入仍在 orchestrator |
| `recommend_learning_action` | 根据 grade/mastery/wrong_reason 给出下一步 action |
| `verify_episode` | 支持 `TaskSpec.verification_policy.required_checks`，检查 graph 字段和节点产物 |

## API / Orchestrator 边界

`start_daily_lesson`：

- 创建 `AgentEpisode`。
- 调用 graph 到 `wait_for_answer`。
- 如果等待答案，创建 `LearningGraphCheckpoint`，episode 进入 `waiting_user`。
- 返回旧字段，并新增 `thread_id`、`prompt_payload`、`required_input_schema`。

`submit_answer`：

- 校验 active business checkpoint。
- 标记 checkpoint `resumed`，注入 `learner_answer`。
- 以 `side_effect_mode="dry_run"` 从 `grade_attempt` 运行 resume graph，获得 graph-level 闭环状态。
- 继续使用现有持久化路径保存 `ExerciseAttempt`、更新 `MasteryEngine`、写 Memory、安排 Review、写 runtime events。
- 标记 checkpoint `completed`，返回原有字段，并附带 `exercise_attempt_id`、`review_schedule_result`、`recommendation_result`。

## Verification

第一阶段支持以下 required checks：

- `task_prepared`
- `learner_answer_received`
- `exercise_attempt_created`
- `exercise_graded`
- `mastery_updated`
- `memory_event_written`
- `review_scheduled`
- `next_action_recommended`

runtime verification 同时兼容旧别名：

- `exercise_attempt_saved` -> attempt payload check
- `grading_result_exists` -> `exercise_graded`
- `memory_event_written` -> `memory_written`

## 当前限制

- 生产默认仍未启用持久化 LangGraph checkpointer；PostgresSaver 接入留到后续。
- 真实 DB 副作用仍集中在 `LearningOrchestrator.submit_answer`，graph 节点以状态产物和 dry-run 兼容为主。
- 当前 Daily Lesson 仍是单 active checkpoint、单题闭环；多题 lesson 和官方 `interrupt()/Command(resume=...)` 深度集成还未完成。
