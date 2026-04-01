from __future__ import annotations

from pathlib import Path
from typing import Any

from .io import read_json
from .validation import validate_document


COVERAGE_KEYS = ["meter", "key", "tune_type"]
SCORER_ONLY_FIELDS = {"reference_abc", "expected_choice"}


def load_dataset(dataset_dir: str | Path) -> dict[str, Any]:
    root = Path(dataset_dir)
    manifest_path = root / "manifest.json"
    manifest = read_json(manifest_path)
    instance_files = manifest.get("instance_files", [])
    instances = _load_instance_batches(root, instance_files)
    scoring_files = manifest.get("scoring_instance_files", [])
    scoring_overrides = _load_override_batches(root, scoring_files)
    merged_instances = merge_instances(instances, scoring_overrides)
    return {
        "root": root,
        "manifest_path": manifest_path,
        "manifest": manifest,
        "instances": merged_instances,
        "public_instances": instances,
        "scoring_overrides": scoring_overrides,
    }


def _load_instance_batches(root: Path, relative_paths: list[str]) -> list[dict[str, Any]]:
    instances: list[dict[str, Any]] = []
    for relative_path in relative_paths:
        batch = read_json(root / relative_path)
        if not isinstance(batch, list):
            raise ValueError(f"Instance file {relative_path} must contain a JSON array")
        instances.extend(batch)
    return instances


def _load_override_batches(root: Path, relative_paths: list[str]) -> list[dict[str, Any]]:
    overrides: list[dict[str, Any]] = []
    for relative_path in relative_paths:
        batch = read_json(root / relative_path)
        if not isinstance(batch, list):
            raise ValueError(f"Scoring override file {relative_path} must contain a JSON array")
        overrides.extend(batch)
    return overrides


def merge_instances(instances: list[dict[str, Any]], overrides: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged = {instance["id"]: dict(instance) for instance in instances}
    for override in overrides:
        instance_id = override["id"]
        if instance_id not in merged:
            raise ValueError(f"Override references unknown instance id: {instance_id}")
        merged[instance_id].update({key: value for key, value in override.items() if key != "id"})
    return list(merged.values())


def validate_dataset(dataset_dir: str | Path) -> list[str]:
    loaded = load_dataset(dataset_dir)
    manifest = loaded["manifest"]
    errors: list[str] = []
    errors.extend(validate_document(manifest, "benchmark_manifest.schema.json"))
    errors.extend(validate_document(loaded["public_instances"], "task_instances.schema.json"))
    if loaded["scoring_overrides"]:
        errors.extend(validate_document(loaded["scoring_overrides"], "task_overrides.schema.json"))

    ids: set[str] = set()
    for instance in loaded["public_instances"]:
        instance_id = instance["id"]
        if instance_id in ids:
            errors.append(f"instances.{instance_id}: duplicate instance id")
        ids.add(instance_id)

    override_ids: set[str] = set()
    for override in loaded["scoring_overrides"]:
        instance_id = override["id"]
        if instance_id in override_ids:
            errors.append(f"scoring_overrides.{instance_id}: duplicate override id")
        override_ids.add(instance_id)
        if instance_id not in ids:
            errors.append(f"scoring_overrides.{instance_id}: unknown instance id")

    prompt_policy = manifest.get("prompt_policy", {})
    visible_fields = set(prompt_policy.get("model_visible_fields", []))
    hidden_fields = set(prompt_policy.get("scorer_hidden_fields", []))
    overlap = sorted(visible_fields & hidden_fields)
    if overlap:
        errors.append(f"prompt_policy: overlapping visible and hidden fields: {', '.join(overlap)}")

    expected_count = manifest.get("expected_instance_count")
    if expected_count is not None and expected_count != len(loaded["public_instances"]):
        errors.append(
            f"expected_instance_count: manifest says {expected_count} but found {len(loaded['public_instances'])} public instances"
        )

    if manifest.get("split") == "hidden_eval" or manifest.get("scoring_instance_files"):
        for instance in loaded["public_instances"]:
            leaked = sorted(hidden_fields & set(instance.keys()))
            if leaked:
                errors.append(
                    f"instances.{instance['id']}: public task contains scorer-hidden fields: {', '.join(leaked)}"
                )

    return errors


def summarize_dataset(dataset_dir: str | Path) -> dict[str, Any]:
    loaded = load_dataset(dataset_dir)
    manifest = loaded["manifest"]
    instances = loaded["instances"]
    by_track: dict[str, int] = {}
    by_task_type: dict[str, int] = {}
    coverage: dict[str, set[str]] = {key: set() for key in COVERAGE_KEYS}
    reference_backed = 0
    for instance in instances:
        by_track[instance["track"]] = by_track.get(instance["track"], 0) + 1
        by_task_type[instance["task_type"]] = by_task_type.get(instance["task_type"], 0) + 1
        if "reference_abc" in instance:
            reference_backed += 1
        constraints = instance.get("constraints", {})
        for key in COVERAGE_KEYS:
            value = constraints.get(key)
            if value:
                coverage[key].add(str(value))
    prompt_policy = manifest.get("prompt_policy", {})
    return {
        "name": manifest["name"],
        "version": manifest["version"],
        "split": manifest["split"],
        "instance_count": len(loaded["public_instances"]),
        "tracks": by_track,
        "task_types": by_task_type,
        "reference_backed_instances": reference_backed,
        "prompt_policy": prompt_policy,
        "coverage": {key: sorted(values) for key, values in coverage.items()},
        "has_hidden_scoring": bool(manifest.get("scoring_instance_files")),
    }


def get_visible_prompt_fields(dataset: dict[str, Any]) -> list[str]:
    prompt_policy = dataset["manifest"].get("prompt_policy", {})
    fields = prompt_policy.get("model_visible_fields", [])
    if fields:
        return list(fields)
    return ["input_abc", "seed_abc", "candidate_abc"]
