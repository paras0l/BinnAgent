请作为 CET-4/CET-6 英语写作老师，围绕主题和功能生成或提取可收藏句式。

主题方向：{{ topic }}
任务类型：{{ task_type }}

输出必须是合法 JSON，结构如下：
{
  "candidates": [
    {
      "text": "英文句式或可替换模板",
      "chinese_meaning": "中文含义",
      "usage_scene": "适用场景",
      "usage_position": "opening/body/closing/translation",
      "tags": ["强调重点", "分层递进"],
      "examples": [{"sentence": "英文例句", "translation": "中文翻译"}],
      "usage_notes": ["使用注意事项"],
      "mistakes": ["常见错误"],
      "quality_score": 0.86,
      "warnings": []
    }
  ]
}

要求：
- 输出 8-12 条时难度从基础到进阶排列。
- 不要只给 First, Second, Third 这类基础表达。
- 不要输出 markdown 代码块。
- 字段不确定时给出 warning，不要编造高置信内容。
