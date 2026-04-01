from __future__ import annotations

import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib import error, request

from jsonschema import Draft202012Validator

from .dataset import load_dataset
from .prompts import export_prompt_pack, load_responses
from .validation import format_error


DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-5-mini"
RETRYABLE_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504}


class OpenAIRequestError(RuntimeError):
    def __init__(self, message: str, retryable: bool) -> None:
        super().__init__(message)
        self.retryable = retryable


class OpenAIResponsesClient:
    def __init__(self, api_key: str, base_url: str = DEFAULT_BASE_URL, timeout_seconds: float = 120.0) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def create_structured_response(
        self,
        model: str,
        instructions: str,
        user_prompt: str,
        schema_name: str,
        schema: dict[str, Any],
        reasoning_effort: str | None = None,
        verbosity: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model,
            "instructions": instructions,
            "input": user_prompt,
            "store": False,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "strict": True,
                    "schema": schema,
                }
            },
        }
        if verbosity:
            payload["text"]["verbosity"] = verbosity
        if reasoning_effort:
            payload["reasoning"] = {"effort": reasoning_effort}

        req = request.Request(
            f"{self.base_url}/responses",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            retryable = exc.code in RETRYABLE_STATUS_CODES
            raise OpenAIRequestError(
                f"OpenAI API request failed: HTTP {exc.code} {detail}",
                retryable=retryable,
            ) from exc
        except error.URLError as exc:
            raise OpenAIRequestError(
                f"OpenAI API request failed: {exc.reason}",
                retryable=True,
            ) from exc

        text = extract_output_text(raw)
        if not text:
            raise OpenAIRequestError(
                f"OpenAI API response did not include output text: {raw}",
                retryable=False,
            )

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise OpenAIRequestError(
                f"Model returned non-JSON output: {text}",
                retryable=False,
            ) from exc
        return {
            "request_payload": payload,
            "raw_response": raw,
            "parsed_response": parsed,
            "output_text": text,
        }


def extract_output_text(payload: dict[str, Any]) -> str:
    if isinstance(payload.get("output_text"), str) and payload["output_text"]:
        return payload["output_text"]

    collected: list[str] = []
    for item in payload.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            text = content.get("text")
            if content.get("type") in {"output_text", "text"} and isinstance(text, str):
                collected.append(text)
    return "".join(collected).strip()


def run_openai_benchmark(
    dataset_dir: str | Path,
    output_dir: str | Path,
    model: str = DEFAULT_MODEL,
    base_url: str = DEFAULT_BASE_URL,
    api_key_env: str = "OPENAI_API_KEY",
    reasoning_effort: str | None = "low",
    verbosity: str | None = "low",
    limit: int | None = None,
    delay_seconds: float = 0.0,
    max_retries: int = 3,
    retry_backoff_seconds: float = 2.0,
    timeout_seconds: float = 120.0,
    resume: bool = True,
    progress_callback: Callable[[str], None] | None = None,
    client: OpenAIResponsesClient | None = None,
) -> dict[str, Path]:
    api_key = os.environ.get(api_key_env)
    if client is None and not api_key:
        raise RuntimeError(f"Missing required environment variable: {api_key_env}")

    dataset = load_dataset(dataset_dir)
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    paths = {
        "run_dir": output_root,
        "config_path": output_root / "config.json",
        "status_path": output_root / "status.json",
        "prompts_path": output_root / "prompts.jsonl",
        "responses_path": output_root / "responses.jsonl",
        "raw_responses_path": output_root / "raw_responses.jsonl",
        "failures_path": output_root / "failures.jsonl",
    }
    if not resume:
        for key in ["responses_path", "raw_responses_path", "failures_path", "status_path"]:
            if paths[key].exists():
                paths[key].unlink()
    export_prompt_pack(dataset_dir, paths["prompts_path"])
    records = load_responses(paths["prompts_path"])
    if limit is not None:
        records = records[:limit]

    effective_client = client or OpenAIResponsesClient(
        api_key=api_key or "",
        base_url=base_url,
        timeout_seconds=timeout_seconds,
    )
    config = build_run_config(
        dataset=dataset,
        model=model,
        base_url=base_url,
        api_key_env=api_key_env,
        reasoning_effort=reasoning_effort,
        verbosity=verbosity,
        limit=limit,
        delay_seconds=delay_seconds,
        max_retries=max_retries,
        retry_backoff_seconds=retry_backoff_seconds,
        timeout_seconds=timeout_seconds,
        output_dir=output_root,
    )
    write_json(paths["config_path"], config)

    known_ids = {record["instance_id"] for record in records}
    existing_responses = load_indexed_jsonl(paths["responses_path"], allowed_ids=known_ids) if resume else {}
    pending_records = [record for record in records if record["instance_id"] not in existing_responses]
    if progress_callback:
        progress_callback(
            f"Run {config['run_id']}: {len(existing_responses)}/{len(records)} completed, "
            f"{len(pending_records)} pending"
        )

    failures = count_jsonl(paths["failures_path"])
    for offset, record in enumerate(pending_records, start=len(existing_responses) + 1):
        instance_id = record["instance_id"]
        if progress_callback:
            progress_callback(f"[{offset}/{len(records)}] running {instance_id}")

        completed = False
        for attempt in range(1, max_retries + 2):
            try:
                result = effective_client.create_structured_response(
                    model=model,
                    instructions=record["system_prompt"],
                    user_prompt=record["user_prompt"],
                    schema_name=f"abcgenbench_{instance_id}",
                    schema=record["response_schema"],
                    reasoning_effort=reasoning_effort,
                    verbosity=verbosity,
                )
                validate_response_shape(record["response_schema"], result["parsed_response"], instance_id)
                append_jsonl(
                    paths["raw_responses_path"],
                    {
                        "timestamp": now_iso(),
                        "instance_id": instance_id,
                        "attempt": attempt,
                        "ok": True,
                        "request_payload": result["request_payload"],
                        "raw_response": result["raw_response"],
                    },
                )
                append_jsonl(paths["responses_path"], result["parsed_response"])
                existing_responses[instance_id] = result["parsed_response"]
                completed = True
                update_status(
                    paths["status_path"],
                    config=config,
                    total=len(records),
                    completed=len(existing_responses),
                    failed=failures,
                    state="running",
                )
                if progress_callback:
                    progress_callback(f"[{offset}/{len(records)}] completed {instance_id} on attempt {attempt}")
                break
            except OpenAIRequestError as exc:
                append_jsonl(
                    paths["failures_path"],
                    {
                        "timestamp": now_iso(),
                        "instance_id": instance_id,
                        "attempt": attempt,
                        "retryable": exc.retryable,
                        "error": str(exc),
                    },
                )
                failures += 1
                update_status(
                    paths["status_path"],
                    config=config,
                    total=len(records),
                    completed=len(existing_responses),
                    failed=failures,
                    state="running",
                )
                if attempt > max_retries or not exc.retryable:
                    raise RuntimeError(f"Failed instance {instance_id}: {exc}") from exc
                wait_seconds = retry_backoff_seconds * (2 ** (attempt - 1))
                if progress_callback:
                    progress_callback(
                        f"[{offset}/{len(records)}] retrying {instance_id} after attempt {attempt}: "
                        f"{exc} (sleep {wait_seconds:.1f}s)"
                    )
                time.sleep(wait_seconds)
        if not completed:
            raise RuntimeError(f"Failed instance {instance_id}: exhausted retries")
        if delay_seconds and offset < len(records):
            time.sleep(delay_seconds)

    update_status(
        paths["status_path"],
        config=config,
        total=len(records),
        completed=len(existing_responses),
        failed=failures,
        state="completed",
    )
    return paths


def build_run_config(
    *,
    dataset: dict[str, Any],
    model: str,
    base_url: str,
    api_key_env: str,
    reasoning_effort: str | None,
    verbosity: str | None,
    limit: int | None,
    delay_seconds: float,
    max_retries: int,
    retry_backoff_seconds: float,
    timeout_seconds: float,
    output_dir: Path,
) -> dict[str, Any]:
    manifest = dataset["manifest"]
    return {
        "run_id": f"{timestamp_slug()}-{slugify(model)}",
        "created_at": now_iso(),
        "benchmark": {
            "name": manifest["name"],
            "version": manifest["version"],
            "tracks": manifest["tracks"],
            "instance_count": len(dataset["instances"]) if isinstance(dataset["instances"], list) else None,
        },
        "provider": {
            "type": "openai_compatible_responses_api",
            "model": model,
            "base_url": base_url,
            "api_key_env": api_key_env,
            "reasoning_effort": reasoning_effort,
            "verbosity": verbosity,
            "timeout_seconds": timeout_seconds,
        },
        "execution": {
            "limit": limit,
            "delay_seconds": delay_seconds,
            "max_retries": max_retries,
            "retry_backoff_seconds": retry_backoff_seconds,
            "output_dir": str(output_dir),
            "resume_supported": True,
        },
        "git_commit": get_git_commit(output_dir),
    }


def validate_response_shape(schema: dict[str, Any], response: dict[str, Any], instance_id: str) -> None:
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(response), key=lambda err: list(err.path))
    if errors:
        formatted = "; ".join(format_error(error) for error in errors)
        raise OpenAIRequestError(
            f"Model response for {instance_id} failed schema validation: {formatted}",
            retryable=False,
        )


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True))
        handle.write("\n")


def load_indexed_jsonl(path: str | Path, allowed_ids: set[str] | None = None) -> dict[str, dict[str, Any]]:
    source = Path(path)
    if not source.exists():
        return {}
    payload: dict[str, dict[str, Any]] = {}
    with source.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            instance_id = item.get("instance_id")
            if instance_id and (allowed_ids is None or instance_id in allowed_ids):
                payload[instance_id] = item
    return payload


def count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


def update_status(
    path: Path,
    *,
    config: dict[str, Any],
    total: int,
    completed: int,
    failed: int,
    state: str,
) -> None:
    write_json(
        path,
        {
            "run_id": config["run_id"],
            "updated_at": now_iso(),
            "state": state,
            "progress": {
                "completed": completed,
                "failed_attempts": failed,
                "total": total,
                "remaining": max(total - completed, 0),
            },
            "provider": config["provider"],
            "benchmark": config["benchmark"],
        },
    )


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=True)
        handle.write("\n")


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def timestamp_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def slugify(value: str) -> str:
    allowed = [char.lower() if char.isalnum() else "-" for char in value]
    slug = "".join(allowed).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or "model"


def get_git_commit(workdir: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=workdir,
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return None
    return result.stdout.strip() or None
