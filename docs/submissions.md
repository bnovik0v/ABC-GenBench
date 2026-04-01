# Submission Policy

## Submission Bundle

A leaderboard submission should include:

- `report.json`
- model/provider metadata used for ingestion
- optional notes about prompting, decoding, or checkpoint date

The canonical ingestion path is:

```bash
uv run abcgenbench ingest-report /path/to/report.json leaderboard/results.json   --label my-model-eval   --provider my-provider   --model-version 2026-04-01   --run-type community   --markdown-output docs/leaderboard.md
```

## Row Types

- `community`: validated public `eval` report, typically self-run.
- `official`: maintainer-run `hidden_eval` report. This should be reserved for scores accepted as official benchmark entries.
- `baseline`: deterministic reference runs included to make regressions obvious.

## Recommended Metadata

Use stable labels and include enough information to distinguish model revisions:

- provider
- model family/name
- model version or checkpoint date
- prompt template notes when relevant
- benchmark version and split are already embedded in `report.json`

## Governance

Recommended operating model:

1. accept public `eval` reports as `community`
2. reserve `official` for maintainer-run `hidden_eval` scoring
3. regenerate `docs/leaderboard.md` whenever `leaderboard/results.json` changes
4. require schema-valid reports and benchmark version metadata for every accepted row

## Hidden Eval

`hidden_eval` is packaged locally in this repo format, but the intended workflow is maintainer-controlled scoring. Public prompt export should never expose scorer-only fields from `scoring_instance_files`.
