"""Strict JSON loading for public contract validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class DuplicateJSONKey(ValueError):
    """Raised when a JSON object repeats a member name."""


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, child in pairs:
        if key in value:
            raise DuplicateJSONKey(f"duplicate JSON object key {key!r}")
        value[key] = child
    return value


def loads_json_object(raw: str, source: Path) -> dict[str, Any]:
    try:
        value = json.loads(raw, object_pairs_hook=_strict_object)
    except DuplicateJSONKey as cause:
        raise ValueError(f"{source}: {cause}") from cause
    except json.JSONDecodeError as cause:
        raise ValueError(
            f"{source}: invalid JSON at line {cause.lineno}, column {cause.colno}"
        ) from cause
    if not isinstance(value, dict):
        raise ValueError(f"{source}: document root must be an object")
    return value


def load_json_object(path: Path) -> dict[str, Any]:
    return loads_json_object(path.read_text(encoding="utf-8"), path)
