# 学习型Agent冷启动问题
Textbook-guided cold start
Curriculum as high-confidence scaffold
Learning path bootstrapping
问题解释：初期，在用户能力画像不足时，以教材目录、单元和知识点作为高置信学习骨架，引导用户逐步学习、练习和标注掌握情况，为后续个性化推荐和长期记忆沉淀提供结构化行为数据。
引入痛点：教材PDF如何解析才能不遗漏知识点（包括但不限于单词，词汇，句式，固定搭配，语法等）
因此项目必须提出教材解析质量治理的方案

# LangGraph的引入必要性分析

# Memory系统真正做了哪些事
1. 把不同模块的学习行为写成统一事件, 用户行为变成可追溯、可审计、可反思的学习证据。
2. 防止碎片化学习，并加上时间序列标签
3. 形成长期学习者画像
4. 记录“什么教学方式对这个人有效”
5. 反向驱动推荐、练习、反馈和复习。

我把 Memory 拆成了 Retain、Recall、Reflect、Control 四个动作：Retain 用 LearningMemoryEvent 记录跨模块学习证据；Reflect 用 MemoryCurator 把事件聚合成 LearningEpisode、LearnerModelMemory 和 TeachingStrategyMemory；Recall 用 MemoryRetriever 按 Chat、Daily Plan、Knowledge Exercise 等场景取最小必要记忆；Control 用 MemoryOperation 支持删除、禁用、纠正和标记改善，避免 Agent 单方面永久记住错误判断。
# ExerciseAttempt + Mastery 更新闭环
练习确定掌握度也是此项目的核心

# Prompt Registry + Schema-first
Prompt versioning
prompt_hash
input_hash
output_schema
model_policy
JSON repair
必须考虑的问题
1. 怎么保证 prompt 可复现？
2. 本地模型结构化输出不稳定怎么办？
3. LLM 字段提取失败如何 repair？

# Dev Console + Langfuse 可观测性分层
Langfuse 看模型调用，Dev Console 看业务运行时。
[Langfuse最佳实践](Langfuse最佳实践.md)

# Simulation / Evaluation
不能依赖人工点测,效率太低
如何模拟不同学习者？

# 学习路径中的学习功能推荐器
探索 Tab 里有很多功能入口，但用户不知道什么时候该用哪个。
每日学习过程中，系统根据当前知识点、练习结果、Memory 和掌握度，主动推荐最合适的探索功能。
规则生成候选，LLM 负责排序和解释。
