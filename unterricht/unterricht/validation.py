"""JSON-Schema- und Gleichwertigkeitspruefung fuer Replay-Antworten."""

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from unterricht.models import JsonObject


ROOT = Path(__file__).resolve().parent


def validate_schema(payload: JsonObject, schema_file: str) -> None:
    schema_path = ROOT / schema_file
    schema: Any = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(payload)


def without_ignored_paths(payload: JsonObject, ignore_paths: list[str]) -> JsonObject:
    """Remove the small documented JSONPath subset ``$.a.b`` from a copy."""
    result = deepcopy(payload)
    for path in ignore_paths:
        if not path.startswith("$."):
            raise ValueError(f"Unterstuetzt wird nur $.a.b, erhalten: {path}")
        parts = path[2:].split(".")
        cursor: dict[str, Any] = result
        for part in parts[:-1]:
            child = cursor.get(part)
            if not isinstance(child, dict):
                break
            cursor = child
        else:
            cursor.pop(parts[-1], None)
    return result


def assert_equivalent(
    discovery_payload: JsonObject,
    replay_payload: JsonObject,
    ignore_paths: list[str],
) -> None:
    expected = without_ignored_paths(discovery_payload, ignore_paths)
    actual = without_ignored_paths(replay_payload, ignore_paths)
    if actual != expected:
        raise AssertionError(f"Replay ist nicht gleichwertig:\nErwartet: {expected}\nErhalten: {actual}")
