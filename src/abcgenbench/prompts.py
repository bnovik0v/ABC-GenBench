from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .dataset import get_visible_prompt_fields, load_dataset
from .io import read_json, write_json


SYSTEM_PROMPT = (
    "You are being evaluated on ABC music tasks. Follow the task exactly. "
    "Return only valid JSON matching the requested response schema."
)


def export_prompt_pack(dataset_dir: str | Path, output_path: str | Path) -> None:
    dataset = load_dataset(dataset_dir)
    visible_fields = get_visible_prompt_fields(dataset)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with output.open("w", encoding="utf-8") as handle:
        for instance in dataset["public_instances"]:
            record = {
                "instance_id": instance["id"],
                "track": instance["track"],
                "task_type": instance["task_type"],
                "system_prompt": SYSTEM_PROMPT,
                "user_prompt": render_instance_prompt(instance, visible_fields=visible_fields),
                "response_schema": response_schema_for_task(instance["task_type"], instance["id"]),
            }
            handle.write(json.dumps(record, ensure_ascii=True))
            handle.write("\n")


def render_instance_prompt(instance: dict[str, Any], *, visible_fields: list[str]) -> str:
    task_type = instance["task_type"]
    lines = [
        f"Task ID: {instance['id']}",
        f"Track: {instance['track']}",
        f"Task Type: {task_type}",
        f"Instruction: {instance['prompt']}",
    ]

    if "constraints" in instance and "constraints" in visible_fields:
        lines.append("Constraints:")
        for key, value in instance["constraints"].items():
            lines.append(f"- {key}: {value}")

    for field in visible_fields:
        if field in {"constraints", "choices"}:
            continue
        if field in instance:
            lines.append(f"{field}:")
            lines.append(instance[field])

    if "choices" in instance and "choices" in visible_fields:
        lines.append("Choices:")
        for choice in instance["choices"]:
            lines.append(f"- {choice['id']}: {choice['abc']}")

    lines.append("Return JSON only.")
    lines.append(f"The instance_id must be exactly: {instance['id']}")
    if task_type == "next_bar_choice":
        lines.append('Response format: {"instance_id":"...", "choice":"A"}')
    else:
        lines.append('Response format: {"instance_id":"...", "output_abc":"..."}')
    return "\n".join(lines)


def response_schema_for_task(task_type: str, instance_id: str) -> dict[str, Any]:
    if task_type == "next_bar_choice":
        return {
            "type": "object",
            "required": ["instance_id", "choice"],
            "properties": {
                "instance_id": {"type": "string", "const": instance_id},
                "choice": {"type": "string"},
            },
            "additionalProperties": False,
        }
    return {
        "type": "object",
        "required": ["instance_id", "output_abc"],
        "properties": {
            "instance_id": {"type": "string", "const": instance_id},
            "output_abc": {"type": "string"},
        },
        "additionalProperties": False,
    }


def build_submission_from_responses(
    dataset_dir: str | Path,
    responses_path: str | Path,
    output_path: str | Path,
    model_name: str,
) -> None:
    dataset = load_dataset(dataset_dir)
    valid_ids = {instance["id"] for instance in dataset["instances"]}
    responses = [
        response
        for response in load_responses(responses_path)
        if response.get("instance_id") in valid_ids
    ]
    payload = {
        "benchmark_name": dataset["manifest"]["name"],
        "benchmark_version": dataset["manifest"]["version"],
        "model_name": model_name,
        "responses": responses,
    }
    write_json(output_path, payload)


def load_responses(path: str | Path) -> list[dict[str, Any]]:
    source = Path(path)
    if source.suffix == ".jsonl":
        items: list[dict[str, Any]] = []
        with source.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    items.append(json.loads(line))
        return items

    payload = read_json(source)
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and "responses" in payload:
        return payload["responses"]
    raise ValueError("Responses file must be JSONL, a JSON array, or a JSON object with 'responses'")
