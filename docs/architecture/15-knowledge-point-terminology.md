# 知识点与能力维度术语

## 1. 统一概念

BinnAgent 统一使用“知识点”描述可讲解、练习、追踪掌握度的语言知识，不再使用“技能点”“微知识点”或“语法点”作为同级概念。

```text
知识点
└── 语言知识点
    ├── 词汇项
    └── 语法知识点

能力维度
├── 听
├── 说
├── 读
└── 写
```

“知识点”与“能力维度”是两个正交维度：知识点说明“学什么”，能力维度说明“能够如何运用”。一个词汇项或语法知识点可以分别在听、说、读、写中形成不同的练习证据和掌握表现。

## 2. 稳定标识

语言知识点使用稳定、与教材来源无关的 `canonical_key`：

```text
vocabulary.shut
vocabulary.shut_down
grammar.simple_past
grammar.past_be
grammar.did_base_form
grammar.present_vs_past
```

约束如下：

- 词汇项使用 `vocabulary.<slug>`。
- 语法知识点使用 `grammar.<slug>`。
- `<slug>` 使用小写 `snake_case`；短语和复合概念用下划线连接。
- `canonical_key` 不包含教材、单元、页码、数据库 ID 或解析批次；这些信息属于来源证据。
- 同一知识点在多本教材中出现时复用稳定标识，通过 evidence/provenance 关联来源。

## 3. 代码与界面映射

| 中文术语 | 稳定类型或标识 | 用途 |
|---|---|---|
| 知识点 | `KnowledgePoint` | 统一领域实体 |
| 词汇项 | `type="vocabulary"`、`vocabulary.*` | 单词、短语及其规范词汇实体 |
| 语法知识点 | `type="grammar"`、`grammar.*` | 可独立讲解和验收的语法概念 |
| 能力维度 | `listening / speaking / reading / writing` | 练习、证据和掌握表现维度 |

历史字段 `skill`、`subskill`、`learning_skill` 在迁移完成前可继续作为兼容字段，但新增产品文案、schema 和业务逻辑不得把 `grammar`、`vocabulary` 与听、说、读、写并列称为“能力维度”。内部 Agent 能力或工具能力使用 `capability`，避免与学习领域术语混淆。

## 4. 文案规则

- 用户界面统一显示“词汇项”和“语法知识点”。
- 泛称统一显示“知识点”或“语言知识点”。
- “听力、口语、阅读、写作”在分类语境中统一称为“能力维度”。
- “微课”可以描述内容形态，但不得把领域实体命名为“微知识点”。

