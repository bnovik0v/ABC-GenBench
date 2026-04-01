from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from abcgenbench.openai_runner import OpenAIRequestError, run_openai_benchmark


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.fail_once_for: set[str] = set()

    def create_structured_response(
        self,
        *,
        model: str,
        instructions: str,
        user_prompt: str,
        schema_name: str,
        schema: dict,
        reasoning_effort: str | None = None,
        verbosity: str | None = None,
    ) -> dict:
        instance_id = schema_name.removeprefix("abcgenbench_")
        self.calls.append(instance_id)
        if instance_id in self.fail_once_for:
            self.fail_once_for.remove(instance_id)
            raise OpenAIRequestError("transient failure", retryable=True)
        payload = {"instance_id": instance_id}
        if "choice" in schema["properties"]:
            payload["choice"] = "A"
        else:
            payload["output_abc"] = "X:1\nT:Stub\nM:4/4\nL:1/4\nK:C\nCDEF | GABc | cBAG | FEDC |]"
        return {
            "request_payload": {"model": model, "input": user_prompt},
            "raw_response": {"output_text": json.dumps(payload)},
            "parsed_response": payload,
            "output_text": json.dumps(payload),
        }


class OpenAIRunnerTests(unittest.TestCase):
    def test_run_writes_artifacts_and_resumes(self) -> None:
        client = FakeClient()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "run"
            first = run_openai_benchmark(
                "fixtures/eval",
                output_dir,
                client=client,
                limit=2,
                progress_callback=None,
            )
            self.assertTrue(first["config_path"].exists())
            self.assertTrue(first["status_path"].exists())
            self.assertTrue(first["raw_responses_path"].exists())
            self.assertEqual(len(client.calls), 2)

            run_openai_benchmark(
                "fixtures/eval",
                output_dir,
                client=client,
                limit=2,
                progress_callback=None,
            )
            self.assertEqual(len(client.calls), 2)

            status = json.loads(first["status_path"].read_text(encoding="utf-8"))
            self.assertEqual(status["state"], "completed")
            self.assertEqual(status["progress"]["completed"], 2)

    def test_retryable_failure_is_retried(self) -> None:
        client = FakeClient()
        client.fail_once_for.add("eval-valid-001")
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "run"
            paths = run_openai_benchmark(
                "fixtures/eval",
                output_dir,
                client=client,
                limit=1,
                retry_backoff_seconds=0.0,
                progress_callback=None,
            )
            failures = paths["failures_path"].read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(failures), 1)
            responses = paths["responses_path"].read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(responses), 1)


if __name__ == "__main__":
    unittest.main()
