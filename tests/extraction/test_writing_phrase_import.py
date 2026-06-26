from src.extraction import extract_writing_phrase_candidates


def test_writing_phrase_import_prefers_json_schema() -> None:
    result = extract_writing_phrase_candidates(
        """
```json
{
  "candidates": [
    {
      "text": "What is more noteworthy is that...",
      "chinese_meaning": "更值得注意的是……",
      "usage_scene": "用于引出更重要的补充观点",
      "usage_position": "body",
      "tags": ["强调重点"],
      "examples": [
        {
          "sentence": "What is more noteworthy is that online learning requires self-discipline.",
          "translation": "更值得注意的是，在线学习需要自律。"
        }
      ],
      "quality_score": 0.88,
      "warnings": []
    }
  ]
}
```
""",
        "online learning",
    )

    assert result.parse_mode == "json_schema"
    assert result.candidates[0].text == "What is more noteworthy is that..."
    assert result.candidates[0].usage_position == "body"
    assert "online learning" in result.candidates[0].tags
    assert result.candidates[0].confidence == 0.88


def test_writing_phrase_import_marks_regex_fallback() -> None:
    result = extract_writing_phrase_candidates(
        """
1. 英文句式：What is more noteworthy is that...
中文含义：更值得注意的一点是……
句式功能：强调重点 / 分层递进
例句：What is more noteworthy is that online learning requires self-discipline.
""",
        "online learning",
    )

    assert result.parse_mode == "regex_fallback"
    assert result.warnings
    assert result.candidates[0].parse_mode == "regex_fallback"
    assert result.candidates[0].warnings
