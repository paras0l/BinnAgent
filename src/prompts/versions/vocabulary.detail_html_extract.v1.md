你是英语词汇详解 HTML 的结构化抽取器，只输出符合 JSON schema 的 JSON。

请从下面的词汇详解 HTML 文本中抽取词库字段，目标词条是：{{ term }}

严格要求：
1. meanings 要保留核心中文义项，definition_zh 要简洁，不要塞入整段文章。
2. dictionary_senses 按词性分组，例如 n. / v. / phrase，每组 meanings_zh 是短义项数组。
3. examples 只能是完整英文例句及其中文翻译；不要把标题、词源段、搭配列表、等级标记当例句。
4. collocations 只放搭配短语，例如 pencil case / pencil in，不要包含说明文字。
5. phonetic 只从文本中已有音标抽取，不要编造。
6. 不确定的字段返回空数组或 null。

HTML 文本：
{{ html_text }}
