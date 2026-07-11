from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


CATALOG_ROOT = Path(__file__).resolve().parent / "assets" / "pep_grade7_upper_2024"
CATALOG_PATH = CATALOG_ROOT / "catalog.json"
EXERCISE_ROOT = CATALOG_ROOT / "exercises"


@lru_cache(maxsize=1)
def grade7_upper_catalog() -> dict[str, Any]:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def unit_catalog(ordinal: int) -> dict[str, Any] | None:
    return next(
        (unit for unit in grade7_upper_catalog()["units"] if unit["ordinal"] == ordinal),
        None,
    )


def exercise_asset_path(filename: str) -> Path:
    allowed = {
        task["asset"]
        for unit in grade7_upper_catalog()["units"]
        for task in unit["textbook_tasks"]
    }
    if filename not in allowed:
        raise FileNotFoundError(filename)
    path = EXERCISE_ROOT / filename
    if not path.is_file():
        raise FileNotFoundError(filename)
    return path
