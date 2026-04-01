# Contributing

## Setup

```bash
uv sync
```

## Before opening a PR

Run:

```bash
uv run abcgenbench validate-dataset fixtures/demo
uv run abcgenbench validate-dataset fixtures/eval
uv run abcgenbench validate-dataset fixtures/hidden_eval
uv run python -m unittest discover -s tests -v
```

## Data changes

- Keep `fixtures/demo` small and representative.
- Keep `fixtures/eval` public and non-leaky.
- Keep `fixtures/hidden_eval/public_tasks.json` free of scorer-only fields.
- Put sealed references and labels for hidden evaluation in `fixtures/hidden_eval/scoring_overrides.json`.
- Update `expected_instance_count` in each manifest when changing split size.

## Leaderboard changes

- Public leaderboard rows should be based on validated `report.json` files.
- Mark unofficial or self-run results as `community`.
- Reserve `official` for maintainer-run hidden-eval scoring.
