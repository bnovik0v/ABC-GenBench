from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CLISmokeTests(unittest.TestCase):
    def test_end_to_end_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            submission = Path(tmpdir) / "baseline_submission.json"
            report = Path(tmpdir) / "baseline_report.json"

            self.run_cli("make-baseline", "fixtures/demo", str(submission))
            self.run_cli("validate-dataset", "fixtures/demo")
            self.run_cli("validate-submission", "fixtures/demo", str(submission))
            self.run_cli("score", "fixtures/demo", str(submission), "--output", str(report))

            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["benchmark_name"], "ABC-GenBench")
            self.assertEqual(payload["benchmark_split"], "demo")
            self.assertIn("validity_renderability", payload["aggregate_scores"])
            self.assertIn("task_type_scores", payload)

    def test_describe_dataset(self) -> None:
        result = subprocess.run(
            ["uv", "run", "abcgenbench", "describe-dataset", "fixtures/eval"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn("Split: eval", result.stdout)
        self.assertIn("Instances: 100", result.stdout)
        self.assertIn("Visible prompt fields:", result.stdout)
        self.assertIn("Hidden scoring fields:", result.stdout)

    def test_prompt_export_and_submission_build(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            prompts = Path(tmpdir) / "prompts.jsonl"
            responses = Path(tmpdir) / "responses.jsonl"
            submission = Path(tmpdir) / "submission.json"

            self.run_cli("export-prompts", "fixtures/eval", str(prompts))

            records = []
            for line in prompts.read_text(encoding="utf-8").splitlines():
                item = json.loads(line)
                self.assertEqual(
                    item["response_schema"]["properties"]["instance_id"]["const"],
                    item["instance_id"],
                )
                self.assertNotIn("reference_abc:", item["user_prompt"])
                self.assertNotIn("expected_choice", item["user_prompt"])
                if item["task_type"] == "next_bar_choice":
                    records.append({"instance_id": item["instance_id"], "choice": "A"})
                else:
                    records.append(
                        {
                            "instance_id": item["instance_id"],
                            "output_abc": "X:1\nT:Stub\nM:4/4\nL:1/4\nK:C\nCDEF | GABc | cBAG | FEDC |]",
                        }
                    )
            responses.write_text(
                "\n".join(json.dumps(record) for record in records) + "\n",
                encoding="utf-8",
            )

            self.run_cli(
                "build-submission",
                "fixtures/eval",
                str(responses),
                str(submission),
                "--model-name",
                "stub-model",
            )
            payload = json.loads(submission.read_text(encoding="utf-8"))
            self.assertEqual(payload["model_name"], "stub-model")
            self.assertEqual(len(payload["responses"]), len(records))

    def test_hidden_eval_prompt_export_and_score(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            prompts = Path(tmpdir) / "hidden_prompts.jsonl"
            submission = Path(tmpdir) / "hidden_submission.json"
            report = Path(tmpdir) / "hidden_report.json"

            self.run_cli("validate-dataset", "fixtures/hidden_eval")
            self.run_cli("export-prompts", "fixtures/hidden_eval", str(prompts))
            text = prompts.read_text(encoding="utf-8")
            self.assertNotIn("reference_abc:", text)
            self.assertNotIn("expected_choice", text)

            self.run_cli("make-baseline", "fixtures/hidden_eval", str(submission))
            self.run_cli("validate-submission", "fixtures/hidden_eval", str(submission))
            self.run_cli("score", "fixtures/hidden_eval", str(submission), "--output", str(report))
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["benchmark_split"], "hidden_eval")

    def test_compare_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            submission = Path(tmpdir) / "baseline_submission.json"
            report_a = Path(tmpdir) / "report_a.json"
            report_b = Path(tmpdir) / "report_b.json"
            csv_path = Path(tmpdir) / "comparison.csv"

            self.run_cli("make-baseline", "fixtures/demo", str(submission))
            self.run_cli("score", "fixtures/demo", str(submission), "--output", str(report_a))
            self.run_cli("score", "fixtures/demo", str(submission), "--output", str(report_b))

            result = subprocess.run(
                [
                    "uv",
                    "run",
                    "abcgenbench",
                    "compare-reports",
                    str(report_a),
                    str(report_b),
                    "--csv-output",
                    str(csv_path),
                ],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn("Model comparison:", result.stdout)
            self.assertTrue(csv_path.exists())
            self.assertIn("composite_score", csv_path.read_text(encoding="utf-8"))

    def test_ingest_and_render_leaderboard(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            submission = Path(tmpdir) / "baseline_submission.json"
            report = Path(tmpdir) / "baseline_report.json"
            leaderboard = Path(tmpdir) / "results.json"
            markdown = Path(tmpdir) / "leaderboard.md"

            self.run_cli("make-baseline", "fixtures/eval", str(submission))
            self.run_cli("score", "fixtures/eval", str(submission), "--output", str(report))
            ingest = subprocess.run(
                [
                    "uv",
                    "run",
                    "abcgenbench",
                    "ingest-report",
                    str(report),
                    str(leaderboard),
                    "--label",
                    "eval-baseline",
                    "--provider",
                    "local",
                    "--model-version",
                    "0.2.0",
                    "--run-type",
                    "baseline",
                    "--markdown-output",
                    str(markdown),
                ],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn("ingested report into", ingest.stdout)
            payload = json.loads(leaderboard.read_text(encoding="utf-8"))
            self.assertEqual(len(payload["entries"]), 1)
            self.assertEqual(payload["entries"][0]["label"], "eval-baseline")
            self.assertIn("## eval", markdown.read_text(encoding="utf-8"))

            render = subprocess.run(
                [
                    "uv",
                    "run",
                    "abcgenbench",
                    "render-leaderboard",
                    str(leaderboard),
                ],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn("# Leaderboard", render.stdout)
            self.assertIn("eval-baseline", render.stdout)

    def test_official_ingest_requires_hidden_eval(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            submission = Path(tmpdir) / "baseline_submission.json"
            report = Path(tmpdir) / "baseline_report.json"
            leaderboard = Path(tmpdir) / "results.json"

            self.run_cli("make-baseline", "fixtures/eval", str(submission))
            self.run_cli("score", "fixtures/eval", str(submission), "--output", str(report))
            result = subprocess.run(
                [
                    "uv",
                    "run",
                    "abcgenbench",
                    "ingest-report",
                    str(report),
                    str(leaderboard),
                    "--label",
                    "bad-official",
                    "--provider",
                    "local",
                    "--model-version",
                    "0.2.0",
                    "--run-type",
                    "official",
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("hidden_eval", result.stderr + result.stdout)

    def test_run_openai_requires_api_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                ["uv", "run", "abcgenbench", "run-openai", "fixtures/eval", tmpdir],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
                env={"PATH": os.environ["PATH"]},
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Missing required environment variable", result.stderr + result.stdout)

    def run_cli(self, *args: str) -> None:
        subprocess.run(
            ["uv", "run", "abcgenbench", *args],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )


if __name__ == "__main__":
    unittest.main()
