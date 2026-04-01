from __future__ import annotations

from pathlib import Path
from typing import Any

from .dataset import load_dataset
from .io import read_json
from .validation import validate_document


def load_submission(path: str | Path) -> dict[str, Any]:
    return read_json(Path(path))


def validate_submission(dataset_dir: str | Path, submission_path: str | Path) -> list[str]:
    dataset = load_dataset(dataset_dir)
    submission = load_submission(submission_path)
    errors = validate_document(submission, "submission.schema.json")

    manifest = dataset["manifest"]
    if submission.get("benchmark_name") != manifest.get("name"):
        errors.append("benchmark_name: submission benchmark does not match dataset manifest")
    if submission.get("benchmark_version") != manifest.get("version"):
        errors.append("benchmark_version: submission benchmark version does not match dataset manifest")

    instance_ids = {instance["id"] for instance in dataset["instances"]}
    seen: set[str] = set()
    for response in submission.get("responses", []):
        instance_id = response["instance_id"]
        if instance_id not in instance_ids:
            errors.append(f"responses.{instance_id}: unknown instance id")
        if instance_id in seen:
            errors.append(f"responses.{instance_id}: duplicate response")
        seen.add(instance_id)

    missing = sorted(instance_ids - seen)
    for instance_id in missing:
        errors.append(f"responses.{instance_id}: missing response")
    return errors
