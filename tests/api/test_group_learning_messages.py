from src.api.group_learning import _content_preview


def test_content_preview_normalizes_whitespace_and_truncates_raw_message():
    content = "  I   want to learn\n" + "a" * 140

    preview = _content_preview(content)

    assert preview is not None
    assert preview.startswith("I want to learn ")
    assert preview.endswith("…")
    assert len(preview) == 121


def test_content_preview_keeps_short_content_and_handles_empty_values():
    assert _content_preview("  short\nmessage  ") == "short message"
    assert _content_preview(None) is None
    assert _content_preview("") is None
