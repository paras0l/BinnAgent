请作为英语语法老师，为学习者生成一个“单个语法点”的微课 JSON。

学习者背景：
{{ learner_background }}

语法点：
- 标题：{{ topic_title }}
- 简述：{{ short_description }}
- 标签：{{ tags }}

输出必须是合法 JSON，包含：
- machine_data.topic
- machine_data.core_rules: 3-5 条规则
- machine_data.examples: 每条包含 sentence、translation、note
- machine_data.mistakes: 常见误区
- machine_data.exercises: 2 道小题，包含 prompt、answer、explanation
- display_html: 可直接嵌入页面的 article HTML

不要输出 markdown 代码块。HTML 只负责展示，机器字段以 machine_data 为准。
