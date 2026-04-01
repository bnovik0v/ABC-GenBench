from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator

from .schema_loader import load_schema


def validate_document(data: Any, schema_name: str) -> list[str]:
    schema = load_schema(schema_name)
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda err: list(err.path))
    return [format_error(error) for error in errors]


def format_error(error: Any) -> str:
    path = ".".join(str(part) for part in error.path) or "<root>"
    return f"{path}: {error.message}"
