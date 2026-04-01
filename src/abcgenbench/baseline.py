from __future__ import annotations

from pathlib import Path

from .dataset import load_dataset
from .io import write_json


def build_baseline_submission(dataset_dir: str | Path) -> dict:
    dataset = load_dataset(dataset_dir)
    responses = []
    for instance in dataset["instances"]:
        task_type = instance["task_type"]
        if task_type == "next_bar_choice":
            choice = instance.get("expected_choice")
            responses.append({"instance_id": instance["id"], "choice": choice})
            continue

        output_abc = (
            instance.get("reference_abc")
            or instance.get("seed_abc")
            or instance.get("candidate_abc")
            or _build_controlled_stub(instance)
        )
        responses.append({"instance_id": instance["id"], "output_abc": output_abc})
    return {
        "benchmark_name": dataset["manifest"]["name"],
        "benchmark_version": dataset["manifest"]["version"],
        "model_name": "baseline-deterministic",
        "responses": responses,
    }


def _build_controlled_stub(instance: dict) -> str:
    constraints = instance.get("constraints", {})
    title = instance.get("prompt", "Baseline output")
    meter = constraints.get("meter", "4/4")
    key = constraints.get("key", "C")
    tune_type = constraints.get("tune_type", "air")
    bars = constraints.get("bars", 4)
    pattern = "CDEF"
    body = " | ".join(pattern for _ in range(max(1, bars)))
    return f"X:1\nT:{title}\nM:{meter}\nL:1/4\nR:{tune_type}\nK:{key}\n{body} |]"


def write_baseline_submission(dataset_dir: str | Path, output_path: str | Path) -> None:
    write_json(Path(output_path), build_baseline_submission(dataset_dir))
