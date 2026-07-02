import hashlib
import json
from typing import Any


def stable_json_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, default=str, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()
