from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPECTED_GROUPS = ("units", "vocabulary", "grammar", "phrases", "exercises")
ITEM_GROUPS = ("vocabulary", "grammar", "phrases", "exercises")
LOW_CONFIDENCE_THRESHOLD = 0.75
DETAIL_ITEM_LIMIT = 50


@dataclass(frozen=True)
class GoldenDataset:
    profile_id: str
    root: Path
    manifest: dict[str, Any]
    expected: dict[str, list[dict[str, Any]]]


def load_golden_dataset(profile_id: str, golden_root: Path | str = Path("books/golden")) -> GoldenDataset:
    root = Path(golden_root) / profile_id
    manifest_path = root / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Golden manifest not found: {manifest_path}")
    manifest = _read_json_object(manifest_path)
    expected = {
        group: _read_json_list(root / f"{group}.expected.json")
        for group in EXPECTED_GROUPS
    }
    return GoldenDataset(profile_id=profile_id, root=root, manifest=manifest, expected=expected)


def list_golden_profiles(golden_root: Path | str = Path("books/golden")) -> list[str]:
    root = Path(golden_root)
    if not root.exists():
        return []
    return sorted(
        path.name
        for path in root.iterdir()
        if path.is_dir() and (path / "manifest.json").exists()
    )


def build_parser_evaluation_report(
    *,
    profile_id: str,
    parser_id: str,
    parser_version: str,
    expected: dict[str, list[dict[str, Any]]],
    actual: dict[str, list[dict[str, Any]]],
    started_at: datetime,
    completed_at: datetime | None = None,
    parser_run_id: str | None = None,
    quality_report_summary: dict[str, Any] | None = None,
    baseline: dict[str, Any] | None = None,
    thresholds: dict[str, dict[str, float]] | None = None,
) -> dict[str, Any]:
    completed = completed_at or datetime.now(timezone.utc)
    metrics, details = compute_parser_eval_metrics(expected=expected, actual=actual)
    active_thresholds = thresholds or (baseline or {}).get("thresholds") or {}
    threshold_failures = evaluate_thresholds(metrics, active_thresholds)
    baseline_comparison = compare_with_baseline(metrics, baseline)
    failures = [
        f"{failure['metric']}={failure['value']} violates {failure['rule']} {failure['expected']}"
        for failure in threshold_failures
    ]
    return {
        "profile_id": profile_id,
        "parser_id": parser_id,
        "parser_version": parser_version,
        "parser_run_id": parser_run_id,
        "started_at": started_at.isoformat(),
        "completed_at": completed.isoformat(),
        "status": "failed" if threshold_failures else "passed",
        "metrics": metrics,
        "failures": failures,
        "missing_items": details["missing_items"],
        "extra_items": details["extra_items"],
        "mismatched_source_pages": details["mismatched_source_pages"],
        "detail_counts": details["detail_counts"],
        "quality_report_summary": quality_report_summary or {},
        "baseline_comparison": baseline_comparison,
        "threshold_failures": threshold_failures,
        "actual_counts": {group: len(actual.get(group) or []) for group in EXPECTED_GROUPS},
        "expected_counts": {group: len(expected.get(group) or []) for group in EXPECTED_GROUPS},
    }


def compute_parser_eval_metrics(
    *,
    expected: dict[str, list[dict[str, Any]]],
    actual: dict[str, list[dict[str, Any]]],
    dirty_tokens: list[str] | tuple[str, ...] | None = None,
) -> tuple[dict[str, float | None], dict[str, Any]]:
    dirty = tuple(dirty_tokens or ("Page PB", "9594", "101100"))
    expected_maps = {group: _item_map(group, expected.get(group, [])) for group in EXPECTED_GROUPS}
    actual_maps = {group: _item_map(group, actual.get(group, [])) for group in EXPECTED_GROUPS}

    matched_units = set(expected_maps["units"]).intersection(actual_maps["units"])
    expected_unit_order = [_item_key("units", item) for item in expected.get("units", [])]
    actual_unit_order = [_item_key("units", item) for item in actual.get("units", [])]
    matched_vocabulary = set(expected_maps["vocabulary"]).intersection(actual_maps["vocabulary"])
    actual_vocabulary_keys = [
        key
        for item in actual.get("vocabulary", [])
        if (key := _item_key("vocabulary", item))
    ]
    matched_actual_vocabulary_count = sum(
        1 for key in actual_vocabulary_keys if key in expected_maps["vocabulary"]
    )
    matched_core_vocabulary = {
        key
        for key, item in expected_maps["vocabulary"].items()
        if item.get("is_core") and key in actual_maps["vocabulary"]
    }

    matched_by_group = {
        group: set(expected_maps[group]).intersection(actual_maps[group])
        for group in EXPECTED_GROUPS
    }
    matched_source_pages = _matched_source_pages(expected_maps, actual_maps)
    duplicate_rate = _duplicate_rate(actual)
    dirty_token_rate = _dirty_token_rate(actual, dirty)
    review_required_precision = _review_required_precision(actual, dirty)

    metrics: dict[str, float | None] = {
        "unit_title_exact_match": _ratio(len(matched_units), len(expected_maps["units"])),
        "unit_order_accuracy": _unit_order_accuracy(expected_unit_order, actual_unit_order),
        "vocabulary_precision": _ratio(
            matched_actual_vocabulary_count,
            len(actual_vocabulary_keys),
        ),
        "vocabulary_recall": _ratio(
            len(matched_vocabulary),
            len(expected_maps["vocabulary"]),
        ),
        "core_vocabulary_hit_rate": _ratio(
            len(matched_core_vocabulary),
            sum(1 for item in expected_maps["vocabulary"].values() if item.get("is_core")),
        ),
        "grammar_topic_recall": _ratio(
            len(matched_by_group["grammar"]),
            len(expected_maps["grammar"]),
        ),
        "phrase_recall": _ratio(
            len(matched_by_group["phrases"]),
            len(expected_maps["phrases"]),
        ),
        "exercise_recall": _ratio(
            len(matched_by_group["exercises"]),
            len(expected_maps["exercises"]),
        ),
        "source_page_accuracy": _ratio(
            matched_source_pages["matched"],
            matched_source_pages["total"],
        ),
        "duplicate_rate": duplicate_rate,
        "dirty_token_rate": dirty_token_rate,
        "review_required_precision": review_required_precision,
    }
    missing_by_group = {
        group: [
            _expected_missing_payload(group, item)
            for key, item in expected_maps[group].items()
            if key not in actual_maps[group]
        ]
        for group in EXPECTED_GROUPS
    }
    extra_by_group = {
        group: [
            _actual_extra_payload(group, item)
            for key, item in actual_maps[group].items()
            if key not in expected_maps[group]
        ]
        for group in EXPECTED_GROUPS
    }
    details = {
        "missing_items": {
            group: items[:DETAIL_ITEM_LIMIT]
            for group, items in missing_by_group.items()
        },
        "extra_items": {
            group: items[:DETAIL_ITEM_LIMIT]
            for group, items in extra_by_group.items()
        },
        "detail_counts": {
            "missing_items": {
                group: len(items)
                for group, items in missing_by_group.items()
            },
            "extra_items": {
                group: len(items)
                for group, items in extra_by_group.items()
            },
            "mismatched_source_pages": len(matched_source_pages["mismatches"]),
            "detail_item_limit": DETAIL_ITEM_LIMIT,
        },
        "mismatched_source_pages": matched_source_pages["mismatches"][:DETAIL_ITEM_LIMIT],
    }
    return metrics, details


def evaluate_thresholds(
    metrics: dict[str, float | None],
    thresholds: dict[str, dict[str, float]],
) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for metric, threshold in thresholds.items():
        value = metrics.get(metric)
        if value is None:
            continue
        if "min" in threshold and value < float(threshold["min"]):
            failures.append(
                {
                    "metric": metric,
                    "value": value,
                    "rule": "min",
                    "expected": float(threshold["min"]),
                }
            )
        if "max" in threshold and value > float(threshold["max"]):
            failures.append(
                {
                    "metric": metric,
                    "value": value,
                    "rule": "max",
                    "expected": float(threshold["max"]),
                }
            )
    return failures


def compare_with_baseline(
    metrics: dict[str, float | None],
    baseline: dict[str, Any] | None,
) -> dict[str, Any]:
    if not baseline:
        return {"baseline_found": False, "metric_deltas": {}, "regressions": []}
    baseline_metrics = baseline.get("metrics") if isinstance(baseline.get("metrics"), dict) else {}
    thresholds = baseline.get("thresholds") if isinstance(baseline.get("thresholds"), dict) else {}
    deltas: dict[str, float | None] = {}
    regressions: list[dict[str, Any]] = []
    for metric, raw_baseline_value in baseline_metrics.items():
        current_value = metrics.get(metric)
        baseline_value = _float_or_none(raw_baseline_value)
        if current_value is None or baseline_value is None:
            deltas[metric] = None
            continue
        delta = round(current_value - baseline_value, 6)
        deltas[metric] = delta
        if _is_regression(metric, current_value, baseline_value, thresholds.get(metric)):
            regressions.append(
                {
                    "metric": metric,
                    "current": current_value,
                    "baseline": baseline_value,
                    "delta": delta,
                }
            )
    return {
        "baseline_found": True,
        "version": baseline.get("version"),
        "metric_deltas": deltas,
        "regressions": regressions,
    }


def load_baseline(profile_id: str, baseline_dir: Path | str = Path("var/parser_eval/baselines")) -> dict[str, Any] | None:
    path = Path(baseline_dir) / f"{profile_id}.json"
    if not path.exists():
        return None
    return _read_json_object(path)


def write_baseline(
    *,
    profile_id: str,
    report: dict[str, Any],
    baseline_dir: Path | str = Path("var/parser_eval/baselines"),
    existing_baseline: dict[str, Any] | None = None,
) -> Path:
    path = Path(baseline_dir) / f"{profile_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = existing_baseline or (load_baseline(profile_id, baseline_dir) or {})
    payload = {
        "profile_id": profile_id,
        "version": int(existing.get("version") or 1),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "metrics": report.get("metrics") or {},
        "thresholds": existing.get("thresholds") or {},
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def validate_expected_schema(expected: dict[str, list[dict[str, Any]]]) -> list[str]:
    errors: list[str] = []
    required_by_group = {
        "units": {"unit_id", "title", "order", "expected_source_pages"},
        "vocabulary": {
            "text",
            "normalized_text",
            "unit_id",
            "part_of_speech",
            "chinese_meaning",
            "source_page",
            "is_core",
        },
        "grammar": {"topic", "unit_id", "source_page", "keywords"},
        "phrases": {"text", "normalized_text", "unit_id", "source_page"},
        "exercises": {"question_key", "unit_id", "source_page", "answer_required", "knowledge_refs"},
    }
    for group, required in required_by_group.items():
        items = expected.get(group)
        if not isinstance(items, list):
            errors.append(f"{group} expected data must be a list")
            continue
        for index, item in enumerate(items):
            missing = sorted(required.difference(item))
            if missing:
                errors.append(f"{group}[{index}] missing fields: {', '.join(missing)}")
    return errors


def normalize_text(value: Any) -> str:
    text = str(value or "").casefold().replace("’", "'")
    text = re.sub(r"[\u2010-\u2015]", "-", text)
    text = re.sub(r"[^a-z0-9\u3400-\u9fff]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_source_page(value: Any) -> str:
    text = str(value or "").casefold().strip()
    text = text.removeprefix("p.")
    text = text.replace("p.", "")
    text = re.sub(r"\s+", "", text)
    return text


def _item_map(group: str, items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items:
        key = _item_key(group, item)
        if key:
            result.setdefault(key, item)
    return result


def _item_key(group: str, item: dict[str, Any]) -> str:
    if group == "units":
        return normalize_text(item.get("title"))
    if group == "vocabulary":
        return normalize_text(item.get("normalized_text") or item.get("text"))
    if group == "grammar":
        return normalize_text(item.get("topic") or item.get("normalized_text"))
    if group == "phrases":
        return normalize_text(item.get("normalized_text") or item.get("text"))
    if group == "exercises":
        return normalize_text(item.get("question_key"))
    return normalize_text(item.get("normalized_text") or item.get("text") or item.get("title"))


def _unit_order_accuracy(expected_order: list[str], actual_order: list[str]) -> float | None:
    if not expected_order:
        return None
    matched = 0
    for index, expected_key in enumerate(expected_order):
        if index < len(actual_order) and actual_order[index] == expected_key:
            matched += 1
    return round(matched / len(expected_order), 4)


def _matched_source_pages(
    expected_maps: dict[str, dict[str, dict[str, Any]]],
    actual_maps: dict[str, dict[str, dict[str, Any]]],
) -> dict[str, Any]:
    total = 0
    matched = 0
    mismatches: list[dict[str, Any]] = []
    for group in ITEM_GROUPS:
        for key, expected_item in expected_maps[group].items():
            if key not in actual_maps[group]:
                continue
            expected_page = expected_item.get("source_page")
            if expected_page in (None, ""):
                continue
            actual_page = actual_maps[group][key].get("source_page")
            total += 1
            if normalize_source_page(expected_page) == normalize_source_page(actual_page):
                matched += 1
            else:
                mismatches.append(
                    {
                        "group": group,
                        "key": key,
                        "expected_source_page": expected_page,
                        "actual_source_page": actual_page,
                    }
                )
    return {"matched": matched, "total": total, "mismatches": mismatches}


def _duplicate_rate(actual: dict[str, list[dict[str, Any]]]) -> float | None:
    keys: list[str] = []
    for group in ITEM_GROUPS:
        for item in actual.get(group, []):
            key = _item_key(group, item)
            if key:
                keys.append(f"{group}:{key}")
    if not keys:
        return None
    duplicate_count = len(keys) - len(set(keys))
    return round(duplicate_count / len(keys), 4)


def _dirty_token_rate(
    actual: dict[str, list[dict[str, Any]]],
    dirty_tokens: tuple[str, ...],
) -> float | None:
    values = [
        _searchable_item_text(item)
        for group in ITEM_GROUPS
        for item in actual.get(group, [])
    ]
    if not values:
        return None
    normalized_tokens = [normalize_text(token) for token in dirty_tokens if normalize_text(token)]
    dirty_count = sum(
        1
        for value in values
        if any(token in normalize_text(value) for token in normalized_tokens)
    )
    return round(dirty_count / len(values), 4)


def _review_required_precision(
    actual: dict[str, list[dict[str, Any]]],
    dirty_tokens: tuple[str, ...],
) -> float | None:
    flagged = [
        item
        for group in ITEM_GROUPS
        for item in actual.get(group, [])
        if bool(item.get("requires_review"))
    ]
    if not flagged:
        return None
    valid = sum(1 for item in flagged if _has_review_reason(item, dirty_tokens))
    return round(valid / len(flagged), 4)


def _has_review_reason(item: dict[str, Any], dirty_tokens: tuple[str, ...]) -> bool:
    confidence = _float_or_none(item.get("confidence"))
    warnings = item.get("warnings") if isinstance(item.get("warnings"), list) else []
    if confidence is not None and confidence < LOW_CONFIDENCE_THRESHOLD:
        return True
    if warnings:
        return True
    if not item.get("source_page"):
        return True
    if any(normalize_text(token) in normalize_text(_searchable_item_text(item)) for token in dirty_tokens):
        return True
    return False


def _searchable_item_text(item: dict[str, Any]) -> str:
    parts = [
        item.get("text"),
        item.get("normalized_text"),
        item.get("topic"),
        item.get("question_key"),
        item.get("raw_line"),
    ]
    return " ".join(str(part) for part in parts if part is not None)


def _expected_missing_payload(group: str, item: dict[str, Any]) -> dict[str, Any]:
    return {
        "group": group,
        "key": _item_key(group, item),
        "item": item,
    }


def _actual_extra_payload(group: str, item: dict[str, Any]) -> dict[str, Any]:
    return {
        "group": group,
        "key": _item_key(group, item),
        "item": _compact_item(item),
    }


def _compact_item(item: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "unit_id",
        "title",
        "text",
        "normalized_text",
        "topic",
        "question_key",
        "source_page",
        "confidence",
        "warnings",
        "requires_review",
    }
    return {key: item.get(key) for key in allowed if key in item}


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(numerator / denominator, 4)


def _is_regression(
    metric: str,
    current_value: float,
    baseline_value: float,
    threshold: Any,
) -> bool:
    if isinstance(threshold, dict) and "max" in threshold:
        return current_value > baseline_value
    if isinstance(threshold, dict) and "min" in threshold:
        return current_value < baseline_value
    if metric in {"dirty_token_rate", "duplicate_rate"}:
        return current_value > baseline_value
    return current_value < baseline_value


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _read_json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _read_json_list(path: Path) -> list[dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, list):
        raise ValueError(f"{path} must contain a JSON array")
    return [item for item in value if isinstance(item, dict)]
