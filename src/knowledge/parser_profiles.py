from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ParserProfile:
    id: str
    page_offset: int = 0
    expected_unit_count: int | None = None
    min_vocabulary_count: int | None = None
    expected_unit_titles: tuple[str, ...] = ()
    expected_core_vocabulary: tuple[str, ...] = ()
    dirty_tokens: tuple[str, ...] = ("Page PB", "9594", "101100")


@dataclass(frozen=True)
class BookManifest:
    id: str
    filename: str
    parser_profile: str
    page_offset: int = 0
    expected_unit_count: int | None = None
    min_vocabulary_count: int | None = None
    unit_titles: tuple[str, ...] = ()


PARSER_PROFILES: dict[str, ParserProfile] = {
    "pep_grade7_upper_v1": ParserProfile(
        id="pep_grade7_upper_v1",
        page_offset=-23,
        expected_unit_count=12,
        min_vocabulary_count=250,
        expected_unit_titles=(
            "Starter Unit 1",
            "Starter Unit 2",
            "Starter Unit 3",
            "Unit 1",
            "Unit 2",
            "Unit 3",
            "Unit 4",
            "Unit 5",
            "Unit 6",
            "Unit 7",
            "Unit 8",
            "Unit 9",
        ),
        expected_core_vocabulary=("first name", "last name", "telephone number"),
    ),
    "pep_grade7_lower_v1": ParserProfile(
        id="pep_grade7_lower_v1",
        expected_unit_count=12,
        min_vocabulary_count=220,
        expected_unit_titles=(
            "Unit 1",
            "Unit 2",
            "Unit 3",
            "Unit 4",
            "Unit 5",
            "Unit 6",
            "Unit 7",
            "Unit 8",
            "Unit 9",
            "Unit 10",
            "Unit 11",
            "Unit 12",
        ),
        expected_core_vocabulary=("guitar", "usually", "train", "rule", "panda"),
    ),
}


def profile_for_source(filename: str, manifest_path: Path | None = None) -> tuple[BookManifest | None, ParserProfile | None]:
    manifest = find_book_manifest(filename, manifest_path=manifest_path)
    if manifest:
        return manifest, PARSER_PROFILES.get(manifest.parser_profile)
    if "七年级上册" in filename:
        profile = PARSER_PROFILES["pep_grade7_upper_v1"]
        return None, profile
    if "七年级下册" in filename:
        profile = PARSER_PROFILES["pep_grade7_lower_v1"]
        return None, profile
    return None, None


def find_book_manifest(filename: str, manifest_path: Path | None = None) -> BookManifest | None:
    path = manifest_path or Path("books/manifest.yaml")
    if not path.exists():
        return None
    books = _parse_manifest(path.read_text(encoding="utf-8")).get("books", [])
    for raw in books:
        if not isinstance(raw, dict) or raw.get("filename") != filename:
            continue
        expected = raw.get("expected") if isinstance(raw.get("expected"), dict) else {}
        page_offset = raw.get("page_offset") if isinstance(raw.get("page_offset"), dict) else {}
        units = raw.get("units") if isinstance(raw.get("units"), list) else []
        return BookManifest(
            id=str(raw.get("id") or filename),
            filename=filename,
            parser_profile=str(raw.get("parser_profile") or ""),
            page_offset=int(page_offset.get("pdf_to_printed") or 0),
            expected_unit_count=_optional_int(expected.get("unit_count")),
            min_vocabulary_count=_optional_int(expected.get("min_vocabulary_count")),
            unit_titles=tuple(str(unit.get("title")) for unit in units if isinstance(unit, dict) and unit.get("title")),
        )
    return None


def _optional_int(value: Any) -> int | None:
    return int(value) if isinstance(value, int) else None


def _parse_manifest(text: str) -> dict[str, Any]:
    # Tiny YAML subset parser for the checked-in manifest shape. This keeps
    # ingestion usable without adding a runtime dependency.
    books: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    section: str | None = None
    current_unit: dict[str, Any] | None = None
    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()
        if line == "books:":
            continue
        if indent == 2 and line.startswith("- "):
            current = {}
            books.append(current)
            section = None
            key, value = _split_key_value(line[2:])
            current[key] = value
            continue
        if current is None:
            continue
        if indent == 4 and line.endswith(":"):
            section = line[:-1]
            current.setdefault(section, [] if section == "units" else {})
            continue
        if indent == 4:
            key, value = _split_key_value(line)
            current[key] = value
            section = None
            continue
        if indent == 6 and section == "units" and line.startswith("- "):
            current_unit = {}
            current.setdefault("units", []).append(current_unit)
            key, value = _split_key_value(line[2:])
            current_unit[key] = value
            continue
        if indent == 6 and section and isinstance(current.get(section), dict):
            key, value = _split_key_value(line)
            current[section][key] = value
            continue
        if indent == 8 and section == "units" and current_unit is not None:
            key, value = _split_key_value(line)
            current_unit[key] = value
    return {"books": books}


def _split_key_value(line: str) -> tuple[str, Any]:
    key, _, raw_value = line.partition(":")
    value = raw_value.strip()
    if value.startswith('"') and value.endswith('"'):
        return key.strip(), value[1:-1]
    if value.isdigit():
        return key.strip(), int(value)
    return key.strip(), value
