from __future__ import annotations

from collections import defaultdict
from statistics import mean
from typing import Any

from .canon import canonicalize_abc, normalized_levenshtein
from .dataset import load_dataset
from .parsers import DEFAULT_PARSERS
from .submission import load_submission
from .validation import validate_document


def score_submission(dataset_dir: str, submission_path: str) -> dict[str, Any]:
    dataset = load_dataset(dataset_dir)
    submission = load_submission(submission_path)
    schema_errors = validate_document(submission, "submission.schema.json")
    if schema_errors:
        raise ValueError("Submission schema is invalid; run validate-submission first")

    response_map = {response["instance_id"]: response for response in submission["responses"]}
    instance_results: list[dict[str, Any]] = []
    per_track_scores: dict[str, list[float]] = defaultdict(list)
    per_task_type_scores: dict[str, list[float]] = defaultdict(list)

    for instance in dataset["instances"]:
        response = response_map[instance["id"]]
        result = score_instance(instance, response)
        instance_results.append(result)
        per_track_scores[instance["track"]].append(result["summary_score"])
        per_task_type_scores[instance["task_type"]].append(result["summary_score"])

    aggregate_scores = {
        track: round(mean(scores), 4) if scores else 0.0
        for track, scores in sorted(per_track_scores.items())
    }
    task_type_scores = {
        task_type: round(mean(scores), 4) if scores else 0.0
        for task_type, scores in sorted(per_task_type_scores.items())
    }

    composite = 0.0
    if aggregate_scores:
        validity = aggregate_scores.get("validity_renderability", 0.0)
        if validity > 0:
            composite = round(mean(aggregate_scores.values()), 4)

    return {
        "benchmark_name": dataset["manifest"]["name"],
        "benchmark_version": dataset["manifest"]["version"],
        "benchmark_split": dataset["manifest"]["split"],
        "model_name": submission["model_name"],
        "instance_results": instance_results,
        "aggregate_scores": aggregate_scores,
        "task_type_scores": task_type_scores,
        "composite_score": composite,
    }


def score_instance(instance: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    task_type = instance["task_type"]
    if task_type == "validity_check":
        metrics = score_validity(response.get("output_abc", ""))
    elif task_type == "controlled_generation":
        metrics = score_control(instance, response.get("output_abc", ""))
    elif task_type == "next_bar_choice":
        metrics = score_choice(instance, response.get("choice"))
    else:
        metrics = score_reference_generation(instance, response.get("output_abc", ""))

    summary_score = round(mean(metrics.values()) if metrics else 0.0, 4)
    return {
        "instance_id": instance["id"],
        "track": instance["track"],
        "task_type": task_type,
        "metrics": {key: round(value, 4) for key, value in metrics.items()},
        "summary_score": summary_score,
    }


def score_validity(output_abc: str) -> dict[str, float]:
    parser_results = [parser.parse(output_abc) for parser in DEFAULT_PARSERS]
    agreement = all(result.parse_success for result in parser_results)
    reference = parser_results[0]
    header_valid = float(all(header in reference.headers for header in ["X", "T", "M", "L", "K"]))
    repeat_consistent = float(reference.repeat_consistent)
    duration_consistent = float(reference.bar_duration_consistent)
    invalid_rate = 1.0 / (1.0 + reference.invalid_token_count)
    return {
        "parser_agreement_rate": float(agreement),
        "header_validity": header_valid,
        "repeat_consistency": repeat_consistent,
        "bar_duration_consistency": duration_consistent,
        "invalid_token_score": invalid_rate,
    }


def score_control(instance: dict[str, Any], output_abc: str) -> dict[str, float]:
    parsed = DEFAULT_PARSERS[0].parse(output_abc)
    constraints = instance.get("constraints", {})
    pitches = parsed.note_pitches
    actual_min = min(pitches) if pitches else None
    actual_max = max(pitches) if pitches else None
    range_ok = 1.0
    if actual_min is not None and actual_max is not None:
        range_ok = soft_range_score(
            actual_min=actual_min,
            actual_max=actual_max,
            min_pitch=constraints.get("min_pitch"),
            max_pitch=constraints.get("max_pitch"),
        )

    metadata_checks = [
        parsed.headers.get("M") == constraints.get("meter"),
        parsed.headers.get("K") == constraints.get("key"),
    ]
    control_checks = metadata_checks.copy()
    tune_type = constraints.get("tune_type")
    if tune_type is not None:
        control_checks.append(parsed.headers.get("R") == tune_type)

    metadata_accuracy = sum(bool(hit) for hit in metadata_checks) / len(metadata_checks)
    control_similarity = sum(bool(hit) for hit in control_checks) / len(control_checks)
    target_bars = constraints.get("bars")
    bar_count_accuracy = 1.0
    if target_bars:
        bar_count_accuracy = max(0.0, 1.0 - (abs(parsed.bar_count - target_bars) / target_bars))

    return {
        "metadata_accuracy": metadata_accuracy,
        "section_count_accuracy": float(parsed.section_count == constraints.get("sections")),
        "bar_count_accuracy": bar_count_accuracy,
        "range_violation_score": range_ok,
        "control_code_similarity": control_similarity,
    }


def score_choice(instance: dict[str, Any], choice: str | None) -> dict[str, float]:
    expected = instance.get("expected_choice")
    return {
        "accuracy": float(choice == expected),
    }


def score_reference_generation(instance: dict[str, Any], output_abc: str) -> dict[str, float]:
    canonical_output = canonicalize_abc(output_abc)
    canonical_reference = canonicalize_abc(instance.get("reference_abc", ""))
    distance = normalized_levenshtein(canonical_output, canonical_reference)
    parsed = DEFAULT_PARSERS[0].parse(output_abc)
    return {
        "validity": float(parsed.parse_success),
        "normalized_levenshtein_score": 1.0 - distance,
    }


def soft_range_score(
    *,
    actual_min: int,
    actual_max: int,
    min_pitch: int | None,
    max_pitch: int | None,
) -> float:
    if min_pitch is None and max_pitch is None:
        return 1.0
    lower_violation = max((min_pitch - actual_min), 0) if min_pitch is not None else 0
    upper_violation = max((actual_max - max_pitch), 0) if max_pitch is not None else 0
    total_violation = lower_violation + upper_violation
    if total_violation <= 0:
        return 1.0
    tolerance = 12.0
    return max(0.0, 1.0 - (total_violation / tolerance))
