from src.knowledge.parser_eval import compute_parser_eval_metrics, normalize_text


def test_normalized_vocabulary_matching_handles_case_space_and_punctuation() -> None:
    assert normalize_text(" Good   Morning! ") == "good morning"
    assert normalize_text("telephone/phone number") == "telephone phone number"
    expected = {
        "units": [],
        "vocabulary": [
            {
                "text": "Good morning!",
                "normalized_text": "good morning",
                "source_page": "P.1",
                "is_core": True,
            }
        ],
        "grammar": [],
        "phrases": [],
        "exercises": [],
    }
    actual = {
        "units": [],
        "vocabulary": [
            {
                "text": "good   morning",
                "normalized_text": "GOOD MORNING",
                "source_page": "1",
            }
        ],
        "grammar": [],
        "phrases": [],
        "exercises": [],
    }

    metrics, details = compute_parser_eval_metrics(expected=expected, actual=actual)

    assert metrics["vocabulary_recall"] == 1.0
    assert metrics["vocabulary_precision"] == 1.0
    assert metrics["core_vocabulary_hit_rate"] == 1.0
    assert metrics["source_page_accuracy"] == 1.0
    assert details["missing_items"]["vocabulary"] == []


def test_vocabulary_precision_recall_missing_and_extra_items() -> None:
    expected = {
        "units": [],
        "vocabulary": [
            {"text": "hello", "normalized_text": "hello", "source_page": "P.1", "is_core": True},
            {"text": "school", "normalized_text": "school", "source_page": "P.2", "is_core": False},
        ],
        "grammar": [],
        "phrases": [],
        "exercises": [],
    }
    actual = {
        "units": [],
        "vocabulary": [
            {"text": "hello", "normalized_text": "hello", "source_page": "P.1"},
            {"text": "extra", "normalized_text": "extra", "source_page": "P.9"},
            {"text": "hello", "normalized_text": "hello", "source_page": "P.1"},
        ],
        "grammar": [],
        "phrases": [],
        "exercises": [],
    }

    metrics, details = compute_parser_eval_metrics(expected=expected, actual=actual)

    assert metrics["vocabulary_precision"] == 0.6667
    assert metrics["vocabulary_recall"] == 0.5
    assert metrics["core_vocabulary_hit_rate"] == 1.0
    assert metrics["duplicate_rate"] == 0.3333
    assert [item["key"] for item in details["missing_items"]["vocabulary"]] == ["school"]
    assert [item["key"] for item in details["extra_items"]["vocabulary"]] == ["extra"]


def test_source_page_accuracy_dirty_token_rate_and_review_required_precision() -> None:
    expected = {
        "units": [],
        "vocabulary": [
            {"text": "hello", "normalized_text": "hello", "source_page": "P.1", "is_core": True},
            {"text": "school", "normalized_text": "school", "source_page": "P.2", "is_core": False},
        ],
        "grammar": [],
        "phrases": [],
        "exercises": [],
    }
    actual = {
        "units": [],
        "vocabulary": [
            {
                "text": "hello",
                "normalized_text": "hello",
                "source_page": "P.1",
                "requires_review": True,
                "warnings": ["missing_phonetic"],
                "confidence": 0.8,
            },
            {
                "text": "school",
                "normalized_text": "school",
                "source_page": "P.9",
                "requires_review": True,
                "warnings": [],
                "confidence": 0.95,
                "raw_line": "school Page PB",
            },
        ],
        "grammar": [],
        "phrases": [],
        "exercises": [],
    }

    metrics, details = compute_parser_eval_metrics(expected=expected, actual=actual)

    assert metrics["source_page_accuracy"] == 0.5
    assert metrics["dirty_token_rate"] == 0.5
    assert metrics["review_required_precision"] == 1.0
    assert details["mismatched_source_pages"] == [
        {
            "group": "vocabulary",
            "key": "school",
            "expected_source_page": "P.2",
            "actual_source_page": "P.9",
        }
    ]
