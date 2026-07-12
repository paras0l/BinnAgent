# Unit Reading Fluency Training Spec

## 背景

单元学习不能只停留在词汇、语法和碎片练习。每个单元需要把本单元主题、语法、词汇和学习者当前水平融合成可阅读的连续输入：长对话或短文。用户通过泛读抓主旨、精读拆句、标记语法卡点，最终把阅读行为沉淀为学习画像中的阅读证据。

## 目标

1. 在单元学习界面增加“阅读语感训练”入口。
2. LLM 生成的材料必须结合当前单元语法、主题、核心词汇和 learner profile。
3. 生成内容进入现有 Reading Workshop，而不是新建孤立页面。
4. 完成阅读后写入 reading exercise attempt，让 Dashboard / 学习画像的阅读值获得证据。
5. 所有结构化 LLM 输出必须走 PromptExecutor、schema validation 和 prompt eval fixture。

## 用户流程

1. 用户进入学习中心的当前单元。
2. 在“今日课程任务”点击“阅读语感”，或在“本单元材料”点击“生成阅读”。
3. 用户选择材料类型：短文或对话；选择长度：短材料或长材料。
4. 系统调用后端生成英文材料，并保存为 ReadingMaterialHistory。
5. 前端自动打开 Reading Workshop：
   - 材料输入页展示生成标题、正文、难度、训练目标。
   - 泛读页记录主旨、态度、中心句。
   - 精读页选择句子、标记语法知识点、可跳转语法知识点学习页。
   - 复盘页点击“完成阅读”，写入 reading attempt。
6. Dashboard 阅读能力值通过已有 `ExerciseAttempt.target_type=reading_passage` 统计获得更新。

## 后端设计

### 数据模型

扩展 `reading_material_histories`：

- `curriculum_node_id`: 关联生成来源单元。
- `material_type`: `dialogue` 或 `passage`。
- `generation_context`: 保存 prompt 版本、schema 状态、单元、主题、语法、词汇和理解题。

### API

`POST /api/learners/{learner_id}/reading-workshop/generated-materials`

请求：

```json
{
  "curriculum_node_id": "uuid",
  "material_type": "passage",
  "length": "short",
  "goal": "mixed",
  "level": "junior"
}
```

行为：

- 校验 learner 存在。
- 只允许访问公共教材或 learner 自有教材单元。
- 读取 LearnerProfile、CurriculumNode、KnowledgePoint。
- 通过 `reading.material_generation@v1` 生成结构化 JSON。
- schema accepted 后保存材料历史。

`POST /api/learners/{learner_id}/reading-workshop/materials/{material_id}/complete`

行为：

- 校验材料属于当前 learner。
- 写入 `ExerciseAttempt`：
  - `target_type=reading_passage`
  - `exercise_id=reading-material-{material_id}`
  - `metadata.reading_value`
  - `source_context.generation_context`
- 不直接更新 mastery，先作为 Dashboard/画像阅读能力证据。

## Prompt 设计

新增：

- Prompt metadata: `reading.material_generation@v1`
- Template: `src/prompts/versions/reading.material_generation.v1.md`
- Schema: `ReadingMaterialGenerationOutput`
- Eval set: `evals/prompts/reading_material_generation_v1.jsonl`

输出字段：

- `title`
- `material_type`
- `text`
- `theme`
- `grammar_focus`
- `vocabulary_used`
- `level_rationale`
- `comprehension_checks`
- `confidence`

## 前端设计

### 单元学习页

在“今日课程任务”增加任务卡：

- 标题：阅读语感
- 描述：把本单元词汇、语法和主题生成连续阅读输入。
- 控件：材料类型 segmented control、长度 segmented control。
- 行为：生成成功后打开 Reading Workshop。

在“本单元材料”增加卡片：

- 标题：阅读材料
- 描述：生成一篇本单元短文或对话，进入精读与泛读。
- 行为同上。

### Reading Workshop

新增能力：

- 支持从外部传入初始材料。
- 保存后维护 active material id。
- 复盘页展示“完成阅读”按钮。
- 完成后调用 completion API，并显示 reading_value 反馈。

## 验收标准

- 后端 reading API 测试覆盖生成与完成记录。
- Prompt registry / regression 测试覆盖新 prompt schema。
- 前端 lint/build 通过。
- 用户可从单元学习页生成阅读材料并进入 Reading Workshop。
- 完成阅读后可在数据库中看到 `reading_passage` attempt。

## 后续

- 根据阅读理解题答案计算更细的 reading score。
- 把 completion evidence 接入 MemoryWriter 的更细粒度 Retain。
- 在 Dashboard 展示“本周阅读输入量”和“阅读材料来源”。
