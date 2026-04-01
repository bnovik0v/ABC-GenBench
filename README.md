# ABC-GenBench

ABC-GenBench is a runnable benchmark toolkit for monophonic ABC melody generation and editing.

Version `0.2.0` ships three automated tracks:

- validity and renderability
- constraint-following / controllable generation
- continuation, infilling, correction, and editing

The repo is self-contained and includes:

- versioned JSON schemas
- a reference CLI
- dual-parser validity checks with a lightweight parser and `music21`
- public `demo` and `eval` splits
- a sealed local `hidden_eval` split format
- a deterministic baseline submission generator
- prompt export and response import for external LLMs
- an OpenAI-compatible runner with resumable run artifacts
- report comparison tooling
- a file-based leaderboard workflow

## Install

```bash
uv sync
```

## Quickstart

```bash
uv run abcgenbench validate-dataset fixtures/eval
uv run abcgenbench export-prompts fixtures/eval /tmp/eval_prompts.jsonl
uv run abcgenbench make-baseline fixtures/eval /tmp/eval_baseline_submission.json
uv run abcgenbench score fixtures/eval /tmp/eval_baseline_submission.json --output /tmp/eval_baseline_report.json
uv run abcgenbench report /tmp/eval_baseline_report.json
```

## CLI

Validate a dataset:

```bash
uv run abcgenbench validate-dataset fixtures/eval
```

Describe a dataset:

```bash
uv run abcgenbench describe-dataset fixtures/eval
```

Generate a baseline submission:

```bash
uv run abcgenbench make-baseline fixtures/demo /tmp/demo_baseline_submission.json
```

Export prompts for an external LLM run:

```bash
uv run abcgenbench export-prompts fixtures/eval /tmp/eval_prompts.jsonl
```

Build a submission from model responses:

```bash
uv run abcgenbench build-submission fixtures/eval /tmp/model_responses.jsonl /tmp/model_submission.json --model-name my-model
```

Run the full benchmark against an OpenAI-compatible Responses API:

```bash
export OPENAI_API_KEY=...
uv run abcgenbench run-openai fixtures/eval runs/openai-eval --model gpt-5-mini
```

Score a submission:

```bash
uv run abcgenbench score fixtures/eval /tmp/model_submission.json --output /tmp/model_report.json
```

Render a readable report:

```bash
uv run abcgenbench report /tmp/model_report.json
```

Compare reports:

```bash
uv run abcgenbench compare-reports /tmp/model_a.json /tmp/model_b.json --csv-output /tmp/comparison.csv
```

Ingest a report into a local leaderboard:

```bash
uv run abcgenbench ingest-report /tmp/model_report.json leaderboard/results.json \
  --label gpt-5-mini-eval \
  --provider openai \
  --model-version 2026-04-01 \
  --run-type community \
  --markdown-output docs/leaderboard.md
```

Render the leaderboard markdown again later:

```bash
uv run abcgenbench render-leaderboard leaderboard/results.json --output docs/leaderboard.md
```

## Splits

- `fixtures/demo`: small smoke-test split with one example from each task family
- `fixtures/eval`: public evaluation split with 100 items
- `fixtures/hidden_eval`: local sealed split with public prompts/tasks plus scorer-only overrides

For `hidden_eval`, prompt export only reads model-visible fields. Scoring still uses the sealed hidden references and labels stored locally in `scoring_instance_files`.

## Current Eval Coverage

`fixtures/eval` currently contains:

- 20 validity tasks
- 20 controlled-generation tasks
- 60 editing/continuation tasks

Coverage includes:

- meters: `4/4`, `6/8`
- keys/modes: `C`, `G`, `D`, `Am`, `Ddor`, `Gdor`
- tune types: `reel`, `jig`, `march`, `air`

## OpenAI-Compatible Runner

`run-openai` targets the Responses API directly and writes:

- `config.json`
- `status.json`
- `prompts.jsonl`
- `raw_responses.jsonl`
- `responses.jsonl`
- `failures.jsonl`
- `submission.json`
- `report.json`

It supports:

- resumable runs from partial `responses.jsonl`
- retry/backoff for transient API failures
- per-instance progress logs
- preserved raw provider payloads for debugging and audit

## Public Leaderboard

The public leaderboard lives in [docs/leaderboard.md](docs/leaderboard.md) and is generated from [leaderboard/results.json](leaderboard/results.json).

The intended policy is:

- `community` rows come from validated public `eval` reports
- `official` rows come from maintainer-run `hidden_eval` scoring
- `baseline` rows are deterministic reference runs

When `leaderboard/results.json` changes, the GitHub Actions workflow in [.github/workflows/leaderboard.yml](.github/workflows/leaderboard.yml) regenerates `docs/leaderboard.md` automatically. That keeps the visible leaderboard page in sync with the canonical JSON results file.

## Parser Agreement

Validity scoring checks agreement across two parser backends:

- the built-in lightweight ABC parser
- `music21` ABC import support

## Release Readiness

The repo includes:

- `LICENSE`
- `CONTRIBUTING.md`
- `CHANGELOG.md`
- GitHub Actions CI in `.github/workflows/ci.yml`
- a leaderboard refresh workflow in `.github/workflows/leaderboard.yml`
- benchmark manifests and schema validation for all splits

## Notes

- v1 remains monophonic and ABC-only.
- Public prompt export does not leak `reference_abc` or `expected_choice`.
- The hidden split is local and sealed, not a hosted evaluation service.
- Submission and governance details are in [docs/submissions.md](docs/submissions.md).
