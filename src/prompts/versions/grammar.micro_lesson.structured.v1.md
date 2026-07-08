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
- machine_data.exercises: 2 道小题；优先使用 grammar_fill_blank，包含 type、prompt、answer、accepted_answers、explanation
- display_html: 可直接嵌入页面的 article HTML

习题要求：
- grammar_fill_blank 必须是语法填空题，题干用完整英文句子挖空，验收当前语法点的形式或规则。
- display_html 中每道小题外层使用 `data-exercise="true"`，并带上 `data-exercise-type`、`data-answer`、`data-explanation`，方便系统从 HTML 中提取题目。
- 不要把答案藏在脚本、表单或交互控件里。

不要输出 markdown 代码块。HTML 只负责展示，机器字段以 machine_data 为准。
