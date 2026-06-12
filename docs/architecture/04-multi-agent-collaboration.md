# 04. 多智能体协作方案

## 1. 模块目标

多智能体的目标不是制造角色复杂度，而是让不同学习技能拥有独立的教学策略、工具和 Memory 写入规则。

核心原则：

- Learning Supervisor 控制节奏和任务量。
- 技能 Agent 专注自己的教学目标。
- Agent 之间通过结构化状态协作，而不是互相甩长文本。
- 每个 Agent 都必须推动用户主动输出。

## 2. Agent 总览

| Agent | 核心职责 | 主要 Memory | 主要工具 |
|---|---|---|---|
| Learning Supervisor | 调度、计划、总结、节奏控制 | Profile, Plan, Rhythm | Progress Analytics |
| Vocabulary Coach | 单词、搭配、复习 | Vocabulary | Dictionary, SRS |
| Listening Coach | 精听、转写、听力题 | Listening Errors, Materials | ASR, TTS, Question Bank |
| Reading Coach | 阅读题、精读、泛读 | Reading Errors, Vocabulary | Question Bank, Dictionary |
| Writing Coach | 作文、翻译、二次修改 | Writing Errors | Essay Scoring |
| Speaking Coach | 口语陪练、场景表达 | Speaking Errors | ASR, TTS |
| CET Strategy | 四六级策略、模考复盘 | Exam Performance | Question Bank |
| Motivation & Rhythm | 降低压力、恢复节奏 | Emotion & Rhythm | Plan Analytics |

## 3. Learning Supervisor Agent

### 3.1 职责

- 决定今天练什么。
- 控制任务数量和难度。
- 调用技能 Agent。
- 汇总反馈。
- 更新计划。
- 避免用户被任务压垮。

### 3.2 输入

- 用户目标。
- 今日时间预算。
- 到期复习。
- 最近表现。
- 用户当前请求。
- 情绪信号。

### 3.3 输出

```json
{
  "selected_skill": "reading",
  "today_goal": "练习六级阅读转折定位题",
  "reason": "最近两次阅读错因都与转折后信息有关",
  "estimated_minutes": 20,
  "agent_instruction": "选择一篇中等难度短文，重点训练 however/but/yet 后的信息定位。"
}
```

## 4. Vocabulary Coach Agent

### 4.1 教学策略

- 不只给中文释义。
- 必须包含发音、语境、搭配和练习。
- 对总错词切换训练方式。
- 高频词优先服务四六级阅读和听力。

### 4.2 输出 Schema

```json
{
  "new_words": [],
  "review_words": [],
  "quiz_items": [],
  "mistake_summary": [],
  "memory_updates": [],
  "next_review_schedule": []
}
```

## 5. Listening Coach Agent

### 5.1 教学流程

```text
预习关键词 -> 听主旨 -> 听细节 -> 逐句转写 -> 对照原文 -> 错听分析 -> 跟读复述
```

### 5.2 错因分类

- 生词导致听不懂。
- 熟词发音不熟。
- 连读弱读。
- 转折信号漏听。
- 只抓单词，没理解句子。
- 题目定位失败。

## 6. Reading Coach Agent

### 6.1 教学策略

- 不默认全文翻译。
- 先让用户说主旨。
- 再处理关键句和题目逻辑。
- 最后要求英文总结或 paraphrase。

### 6.2 错因分类

- 主旨判断错误。
- 细节定位错误。
- 转折关系漏看。
- 词义题依赖孤立释义。
- 推断题过度脑补。
- 耗时过长。

## 7. Writing Coach Agent

### 7.1 批改流程

```text
用户初稿 -> 总体诊断 -> 标出关键问题 -> 用户二次修改 -> 给升级版 -> 写入错误模式
```

### 7.2 反馈限制

每次最多指出：

- 1 个结构问题。
- 1-2 个语言问题。
- 1 个最值得复用的表达。

避免把作文批成红海。

## 8. Speaking Coach Agent

### 8.1 训练场景

- 自我介绍。
- 家乡、校园、兴趣。
- 四六级口语模拟。
- 图片描述。
- 观点表达。
- 技术/职场场景。

### 8.2 反馈策略

- 对话中少打断。
- 每 3-5 轮小结一次。
- 优先清晰度和自然度。
- 记录卡壳表达。

## 9. CET Strategy Agent

### 9.1 职责

- 制定阶段计划。
- 解释题型策略。
- 分析模考。
- 做考前冲刺优先级。

### 9.2 输出

```json
{
  "score_diagnosis": {},
  "section_priorities": ["listening", "reading"],
  "next_week_focus": [],
  "time_allocation_advice": {},
  "risk": "作文模板依赖较高，建议增加例证训练"
}
```

## 10. Motivation & Rhythm Agent

### 10.1 职责边界

它不是心理咨询 Agent，而是学习节奏调节 Agent。

可以做：

- 降低任务量。
- 解释挫败原因。
- 帮用户从最小任务恢复。
- 给温和、具体的复盘。

不做：

- 医学诊断。
- 情绪标签化。
- 空泛鸡汤。

## 11. 协作模式

### 11.1 Supervisor -> Specialist

默认模式。Supervisor 选择一个技能 Agent。

适合：

- 每日课程。
- 明确技能训练。
- 控制任务量。

### 11.2 Parallel Specialists

多个 Agent 并行分析。

适合：

- 模考复盘。
- 综合诊断。
- 周报生成。

### 11.3 Handoff

一个 Agent 发现问题后转交另一个 Agent。

示例：

- Reading Agent 发现生词密度过高，handoff 给 Vocabulary Agent 做预习。
- Writing Agent 发现作文主要问题是观点素材不足，handoff 给 Reading Agent 推荐输入材料。

## 12. Agent 输出统一要求

所有 Agent 输出都应包含：

- 用户可见反馈。
- 结构化评分或判断。
- Memory candidates。
- 下一步建议。
- 是否需要复习调度。

这保证多 Agent 不只是聊天角色，而是能进入系统闭环。
