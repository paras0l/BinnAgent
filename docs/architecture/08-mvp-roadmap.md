# 08. MVP Roadmap

## 1. MVP 目标

第一版证明一个核心命题：

> 系统能围绕四六级目标，持续记录用户错词错因，生成每日可执行任务，并通过反馈和复习帮助用户看到进步。

## 2. MVP 范围

### 必做

- 本地 Ollama 模型 Provider。
- 用户目标设置。
- 学习画像。
- 7 天计划。
- 每日课程 LangGraph。
- 词汇 Memory。
- 间隔复习。
- 阅读题训练。
- 写作批改和二次修改。
- 错因 Memory。
- 周报。

### 延后

- 完整 ASR 口语评分。
- 大规模听力材料库。
- 外部 MCP 插件生态。
- 社区排行榜。
- 复杂游戏化。
- 班级/教师端。

## 3. 里程碑

### M1：项目骨架与学习画像

目标：

- FastAPI 后端。
- Ollama Model Provider 健康检查。
- 用户画像表。
- 目标设置。
- 简单学习工作台接口。

验收：

- 系统能检测本地 Ollama 是否可用。
- 用户可设置四级/六级、考试日期、每日时间。
- 系统可生成初始 profile。

### M2：LangGraph 每日课程

目标：

- 实现顶层 Graph。
- 支持 start daily lesson。
- 支持状态 checkpoint。
- 支持 session summary。

验收：

- 用户能开始一节课程。
- 中断后能恢复。
- 每节课有结构化 session 记录。

### M3：词汇 Memory + 复习调度

目标：

- vocabulary_items。
- review_schedules。
- Dictionary Tool mock，并预留有道词典 provider 配置。
- SRS scheduler。

验收：

- 系统能写入错词。
- 第二天能自动安排复习。
- 用户答题后更新掌握度。
- 词典工具调用不依赖具体 provider，后续可切到有道词典 MCP。

### M4：阅读训练

目标：

- CET 阅读题模型。
- Reading Coach Agent。
- question_attempts。
- 错因分类。

验收：

- 用户完成阅读题。
- 系统能解释错因。
- 错因写入 Error Pattern Memory。

### M5：写作训练

目标：

- Writing Coach Agent。
- 作文提交。
- 批改反馈。
- 二次修改。

验收：

- 用户先写草稿。
- 系统给 1-3 个关键问题。
- 用户二改后系统给对照反馈。

### M6：周报和评估

目标：

- 周学习统计。
- 高频错因。
- 下周计划。
- 基础 Agent eval。

验收：

- 用户能看到一周总结。
- 系统能调整下周重点。

## 4. MVP Demo 脚本

1. 用户选择“六级，12 周后考试，每天 30 分钟”。
2. 系统生成 profile 和第一周计划。
3. 用户开始今日课程。
4. Supervisor 选择阅读训练。
5. Reading Agent 给一篇短阅读和 3 道题。
6. 用户答错 1 道转折逻辑题。
7. Agent 解释错因，并抽取 3 个生词。
8. Memory 写入错因和生词。
9. SRS 安排第二天复习。
10. 用户提交一段作文。
11. Writing Agent 先指出关键问题，要求二次修改。
12. 用户修改后，系统给升级版对照。
13. 周报展示：词汇复习、阅读错因、写作进步和下周重点。

## 5. 技术验收标准

### Runtime

- Graph 节点可追踪。
- session 可恢复。
- 默认模型调用走本地 Ollama Provider。
- 工具失败不导致整节课崩溃。

### Memory

- 错词不会重复写多条。
- 错误模式有 evidence。
- 复习时间可动态更新。

### Agent

- 不直接代写作文。
- 反馈不超过关键 3 点。
- 每节课必须有用户主动输出。

### Product

- 今日任务能在时间预算内完成。
- 用户能看到为什么今天练这个。
- 周报能解释下周计划。

## 6. 简历包装

项目名称：

> 基于 LangGraph 的英语学习陪伴多智能体系统

项目描述：

> 面向英语四六级备考场景，设计基于 LangGraph 的长期陪伴型学习 Agent。系统通过 Learning Supervisor 调度 Vocabulary、Reading、Writing 等专家 Agent，将每日学习编排为诊断、训练、反馈、复习和记忆更新的状态化流程。构建学习专属 Memory，追踪错词、错因、写作错误模式、复习计划和学习节奏，并通过间隔复习和周报形成个性化提分闭环。

亮点：

- LangGraph 状态化学习流程。
- 学习场景专属长期 Memory。
- 多 Agent 教学协作。
- 间隔复习和错因归因。
- Agent Eval 与学习效果指标。
- 本地 Ollama 优先的模型 Provider 设计。

## 7. 后续扩展

MVP 成功后扩展：

- 听力精听和转写。
- 口语陪练和 ASR。
- 真题套卷模考。
- MCP 工具化。
- 有道词典 MCP provider 接入。
- 教师/班级端。
- 个性化材料推荐。
