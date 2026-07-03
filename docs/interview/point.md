简历要围绕"做出来了什么，达成了什么效果展开"，必须体现“踩坑经验”和“工程取舍”。

# 学习型Agent冷启动问题
Textbook-guided cold start
Curriculum as high-confidence scaffold
Learning path bootstrapping
问题解释：初期，在用户能力画像不足时，以教材目录、单元和知识点作为高置信学习骨架，引导用户逐步学习、练习和标注掌握情况，为后续个性化推荐和长期记忆沉淀提供结构化行为数据。
引入痛点：教材PDF如何解析才能不遗漏知识点（包括但不限于单词，词汇，句式，固定搭配，语法等）
因此项目必须提出教材解析质量治理的方案

# LangGraph的引入必要性分析
[LangGraph最佳实践](LangGraph最佳实践.md)
# Memory系统真正做了哪些事
1. 把不同模块的学习行为写成统一事件, 用户行为变成可追溯、可审计、可反思的学习证据。
2. 防止碎片化学习，并加上时间序列标签
3. 形成长期学习者画像
4. 记录“什么教学方式对这个人有效”
5. 反向驱动推荐、练习、反馈和复习。

我把 Memory 拆成了 Retain、Recall、Reflect、Control 四个动作：Retain 用 LearningMemoryEvent 记录跨模块学习证据；Reflect 用 MemoryCurator 把事件聚合成 LearningEpisode、LearnerModelMemory 和 TeachingStrategyMemory；Recall 用 MemoryRetriever 按 Chat、Daily Plan、Knowledge Exercise 等场景取最小必要记忆；Control 用 MemoryOperation 支持删除、禁用、纠正和标记改善，避免 Agent 单方面永久记住错误判断。
# ExerciseAttempt + Mastery 更新闭环
练习确定掌握度也是此项目的核心
[练习最佳实践](练习最佳实践.md)

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

[Prompt工程经验](Prompt工程经验.md)

# Dev Console + Langfuse 可观测性分层
Langfuse 看模型调用，Dev Console 看业务运行时。
[Langfuse最佳实践](Langfuse最佳实践.md)

# Simulation / Evaluation
不能依赖人工点测,效率太低
如何模拟不同学习者？
[模拟学习者最佳实践](模拟学习者最佳实践.md)

# 学习路径中的学习功能推荐器
探索 Tab 里有很多功能入口，但用户不知道什么时候该用哪个。
每日学习过程中，系统根据当前知识点、练习结果、Memory 和掌握度，主动推荐最合适的探索功能。
规则生成候选，LLM 负责排序和解释。
我设计了一个基于 Mastery、Memory、当前知识点、学习路径和练习结果的上下文感知学习动作推荐器，用于在每日学习流中动态推荐最合适的探索功能，并通过规则生成候选、LLM 排序解释、用户反馈反向更新策略。
1. 推荐依据是什么？ 
2. 和普通规则推荐有什么区别？ 
3. 为什么要用 LLM？ 
4. 推荐效果怎么评估？ 
5. 用户不接受推荐怎么办？ 
6. 推荐失败会不会打乱学习路径？

设计上下文感知的 Learning Action Recommender，将当前知识点、ExerciseAttempt 结果、Mastery 状态、Memory 画像、ReviewSchedule 和学习路径阶段统一作为推荐上下文。系统先通过规则生成候选学习动作，再由 LLM 对候选动作进行排序与解释，向用户推荐最合适的探索功能，例如错因讲解、对比练习、单词复习、语法巩固、例句生成或下一单元预习。用户的点击、跳过、完成和反馈行为会再次写入 Memory，用于优化后续推荐策略。

# 数据隔离与权限边界
PostgreSQL RLS ： Row-Level Security
SaaS tenant 暂不做
设计基于 learner ownership 的资源隔离模型，将 Memory、Episode、Attempt、Preference、ReviewSchedule 等用户私有资源统一纳入 scoped query / get-by-id ownership check，并在 Dev Console 中区分 debug access 与 learner data scope。
