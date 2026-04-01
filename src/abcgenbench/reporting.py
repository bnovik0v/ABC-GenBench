from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any


def render_report(report: dict[str, Any]) -> str:
    lines = [
        f"Benchmark: {report['benchmark_name']} {report['benchmark_version']}",
        f"Model: {report['model_name']}",
        "",
        "Aggregate scores:",
    ]
    for track, score in report["aggregate_scores"].items():
        lines.append(f"- {track}: {score:.4f}")
    lines.append(f"- composite_score: {report['composite_score']:.4f}")
    lines.append("")
    lines.append("Per-instance summary:")
    for item in report["instance_results"]:
        lines.append(
            f"- {item['instance_id']} [{item['task_type']}] {item['summary_score']:.4f}"
        )
    return "\n".join(lines)


def summarize_report(report: dict[str, Any]) -> dict[str, Any]:
    by_task_type: dict[str, list[float]] = defaultdict(list)
    for item in report["instance_results"]:
        by_task_type[item["task_type"]].append(item["summary_score"])
    task_type_scores = {
        task_type: round(mean(scores), 4)
        for task_type, scores in sorted(by_task_type.items())
    }
    return {
        "model_name": report["model_name"],
        "aggregate_scores": dict(report["aggregate_scores"]),
        "task_type_scores": task_type_scores,
        "composite_score": report["composite_score"],
    }


def render_report_comparison(reports: list[dict[str, Any]]) -> str:
    summaries = [summarize_report(report) for report in reports]
    tracks = sorted({key for summary in summaries for key in summary["aggregate_scores"]})
    task_types = sorted({key for summary in summaries for key in summary["task_type_scores"]})

    lines = ["Model comparison:", ""]
    for summary in summaries:
        lines.append(f"- {summary['model_name']}: composite_score={summary['composite_score']:.4f}")
    lines.append("")
    lines.append("Per-track:")
    for track in tracks:
        line = [track]
        for summary in summaries:
            value = summary["aggregate_scores"].get(track, 0.0)
            line.append(f"{summary['model_name']}={value:.4f}")
        lines.append("- " + " | ".join(line))
    lines.append("")
    lines.append("Per-task-type:")
    for task_type in task_types:
        line = [task_type]
        for summary in summaries:
            value = summary["task_type_scores"].get(task_type, 0.0)
            line.append(f"{summary['model_name']}={value:.4f}")
        lines.append("- " + " | ".join(line))
    return "\n".join(lines)


def write_report_comparison_csv(reports: list[dict[str, Any]], output_path: str | Path) -> None:
    summaries = [summarize_report(report) for report in reports]
    rows: list[dict[str, Any]] = []
    for summary in summaries:
        rows.append(
            {
                "model_name": summary["model_name"],
                "scope": "aggregate",
                "metric": "composite_score",
                "score": summary["composite_score"],
            }
        )
        for metric, score in summary["aggregate_scores"].items():
            rows.append(
                {
                    "model_name": summary["model_name"],
                    "scope": "track",
                    "metric": metric,
                    "score": score,
                }
            )
        for metric, score in summary["task_type_scores"].items():
            rows.append(
                {
                    "model_name": summary["model_name"],
                    "scope": "task_type",
                    "metric": metric,
                    "score": score,
                }
            )

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["model_name", "scope", "metric", "score"])
        writer.writeheader()
        writer.writerows(rows)
