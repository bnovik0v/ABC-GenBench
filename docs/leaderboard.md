# Leaderboard

Maintainer policy:
- `official` rows should come from maintainer-run `hidden_eval` scoring.
- `community` rows should use validated public `eval` reports plus metadata.
- `baseline` rows are deterministic smoke-test references.

## eval

| Rank | Label | Model | Provider | Version | Type | Composite | Validity | Control | Editing | Date |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | gpt-5-eval-2026-04-02 | gpt-5 | openai | 2026-04-02 | community | 0.9442 | 0.9900 | 0.9500 | 0.8926 | 2026-04-01 |
| 2 | gpt-5-mini-eval-2026-04-02 | gpt-5-mini | openai | 2026-04-02 | community | 0.9075 | 0.8918 | 0.9175 | 0.9133 | 2026-04-01 |
| 3 | gpt-5-nano-eval-2026-04-02 | gpt-5-nano | openai | 2026-04-02 | community | 0.7900 | 0.7019 | 0.8800 | 0.7880 | 2026-04-01 |
| 4 | eval-baseline-0.2.0 | baseline-deterministic | local | 0.2.0 | baseline | 0.9797 | 1.0000 | 0.9475 | 0.9917 | 2026-04-01 |

