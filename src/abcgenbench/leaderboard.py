from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .io import read_json, write_json
from .validation import validate_document


VALID_RUN_TYPES = {"official", "community", "baseline"}


def load_leaderboard(leaderboard_path: str | Path) -> dict[str, Any]:
    target = Path(leaderboard_path)
    if not target.exists():
        payload = {"entries": []}
        errors = validate_document(payload, "leaderboard_results.schema.json")
        if errors:
            raise ValueError("; ".join(errors))
        return payload
    payload = read_json(target)
    errors = validate_document(payload, "leaderboard_results.schema.json")
    if errors:
        raise ValueError("; ".join(errors))
    return payload


def ingest_report(
    report_path: str | Path,
    leaderboard_path: str | Path,
    *,
    label: str,
    provider: str,
    model_version: str,
    run_type: str,
    submission_date: str | None = None,
    notes: str = "",
) -> dict[str, Any]:
    if run_type not in VALID_RUN_TYPES:
        raise ValueError(f"unsupported run type: {run_type}")

    report = read_json(report_path)
    submission_date = submission_date or datetime.now(timezone.utc).date().isoformat()
    entry = {
        "label": label,
        "model_name": report["model_name"],
        "provider": provider,
        "model_version": model_version,
        "benchmark_name": report["benchmark_name"],
        "benchmark_version": report["benchmark_version"],
        "benchmark_split": report["benchmark_split"],
        "run_type": run_type,
        "submission_date": submission_date,
        "notes": notes,
        "aggregate_scores": report["aggregate_scores"],
        "task_type_scores": report["task_type_scores"],
        "composite_score": report["composite_score"],
    }
    if run_type == "official" and entry["benchmark_split"] != "hidden_eval":
        raise ValueError("official leaderboard entries must come from hidden_eval reports")

    entry_errors = validate_document(entry, "leaderboard_entry.schema.json")
    if entry_errors:
        raise ValueError("; ".join(entry_errors))

    payload = load_leaderboard(leaderboard_path)
    payload["entries"] = [row for row in payload["entries"] if row["label"] != label]
    payload["entries"].append(entry)
    payload["entries"].sort(
        key=lambda row: (row["benchmark_split"], -row["composite_score"], row["label"])
    )

    errors = validate_document(payload, "leaderboard_results.schema.json")
    if errors:
        raise ValueError("; ".join(errors))
    write_json(leaderboard_path, payload)
    return payload


def render_leaderboard_markdown(payload: dict[str, Any]) -> str:
    entries = sorted(
        payload["entries"],
        key=lambda row: (row["benchmark_split"], -row["composite_score"], row["label"]),
    )
    lines = [
        "# Leaderboard",
        "",
        "Maintainer policy:",
        "- `official` rows should come from maintainer-run `hidden_eval` scoring.",
        "- `community` rows should use validated public `eval` reports plus metadata.",
        "- `baseline` rows are deterministic smoke-test references.",
        "",
    ]
    if not entries:
        lines.append("No results ingested yet.")
        return "\n".join(lines)

    splits = sorted({row["benchmark_split"] for row in entries})
    for split in splits:
        split_entries = [row for row in entries if row["benchmark_split"] == split]
        lines.append(f"## {split}")
        lines.append("")
        lines.append(
            "| Rank | Label | Model | Provider | Version | Type | Composite | Validity | Control | Editing | Date |"
        )
        lines.append(
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"
        )
        for rank, row in enumerate(split_entries, start=1):
            label = row["label"]
            model_name = row["model_name"]
            provider = row["provider"]
            version = row["model_version"]
            entry_run_type = row["run_type"]
            composite_score = row["composite_score"]
            submission_date = row["submission_date"]
            aggregate = row["aggregate_scores"]
            validity = aggregate.get("validity_renderability", 0.0)
            control = aggregate.get("constraint_following", 0.0)
            editing = aggregate.get("editing_continuation", 0.0)
            lines.append(
                f"| {rank} | {label} | {model_name} | {provider} | {version} | {entry_run_type} | "
                f"{composite_score:.4f} | {validity:.4f} | {control:.4f} | {editing:.4f} | {submission_date} |"
            )
        lines.append("")
    return "\n".join(lines)


def write_leaderboard_markdown(payload: dict[str, Any], output_path: str | Path) -> None:
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_leaderboard_markdown(payload) + "\n", encoding="utf-8")