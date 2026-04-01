from __future__ import annotations

import argparse
import sys

from .baseline import write_baseline_submission
from .dataset import summarize_dataset, validate_dataset
from .io import read_json, write_json
from .leaderboard import (
    ingest_report,
    load_leaderboard,
    render_leaderboard_markdown,
    write_leaderboard_markdown,
)
from .openai_runner import DEFAULT_BASE_URL, DEFAULT_MODEL, run_openai_benchmark
from .prompts import build_submission_from_responses, export_prompt_pack
from .reporting import render_report, render_report_comparison, write_report_comparison_csv
from .scoring import score_submission
from .submission import validate_submission
from .validation import validate_document


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="abcgenbench")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_dataset_parser = subparsers.add_parser("validate-dataset")
    validate_dataset_parser.add_argument("dataset_dir")
    validate_dataset_parser.set_defaults(func=cmd_validate_dataset)

    describe_dataset_parser = subparsers.add_parser("describe-dataset")
    describe_dataset_parser.add_argument("dataset_dir")
    describe_dataset_parser.set_defaults(func=cmd_describe_dataset)

    validate_submission_parser = subparsers.add_parser("validate-submission")
    validate_submission_parser.add_argument("dataset_dir")
    validate_submission_parser.add_argument("submission_path")
    validate_submission_parser.set_defaults(func=cmd_validate_submission)

    score_parser = subparsers.add_parser("score")
    score_parser.add_argument("dataset_dir")
    score_parser.add_argument("submission_path")
    score_parser.add_argument("--output")
    score_parser.set_defaults(func=cmd_score)

    report_parser = subparsers.add_parser("report")
    report_parser.add_argument("report_path")
    report_parser.set_defaults(func=cmd_report)

    compare_reports_parser = subparsers.add_parser("compare-reports")
    compare_reports_parser.add_argument("report_paths", nargs="+")
    compare_reports_parser.add_argument("--csv-output")
    compare_reports_parser.set_defaults(func=cmd_compare_reports)

    ingest_report_parser = subparsers.add_parser("ingest-report")
    ingest_report_parser.add_argument("report_path")
    ingest_report_parser.add_argument("leaderboard_path")
    ingest_report_parser.add_argument("--label", required=True)
    ingest_report_parser.add_argument("--provider", required=True)
    ingest_report_parser.add_argument("--model-version", required=True)
    ingest_report_parser.add_argument(
        "--run-type",
        required=True,
        choices=["official", "community", "baseline"],
    )
    ingest_report_parser.add_argument("--submission-date")
    ingest_report_parser.add_argument("--notes", default="")
    ingest_report_parser.add_argument("--markdown-output")
    ingest_report_parser.set_defaults(func=cmd_ingest_report)

    render_leaderboard_parser = subparsers.add_parser("render-leaderboard")
    render_leaderboard_parser.add_argument("leaderboard_path")
    render_leaderboard_parser.add_argument("--output")
    render_leaderboard_parser.set_defaults(func=cmd_render_leaderboard)

    baseline_parser = subparsers.add_parser("make-baseline")
    baseline_parser.add_argument("dataset_dir")
    baseline_parser.add_argument("output_path")
    baseline_parser.set_defaults(func=cmd_make_baseline)

    export_prompts_parser = subparsers.add_parser("export-prompts")
    export_prompts_parser.add_argument("dataset_dir")
    export_prompts_parser.add_argument("output_path")
    export_prompts_parser.set_defaults(func=cmd_export_prompts)

    build_submission_parser = subparsers.add_parser("build-submission")
    build_submission_parser.add_argument("dataset_dir")
    build_submission_parser.add_argument("responses_path")
    build_submission_parser.add_argument("output_path")
    build_submission_parser.add_argument("--model-name", required=True)
    build_submission_parser.set_defaults(func=cmd_build_submission)

    run_openai_parser = subparsers.add_parser("run-openai")
    run_openai_parser.add_argument("dataset_dir")
    run_openai_parser.add_argument("output_dir")
    run_openai_parser.add_argument("--model", default=DEFAULT_MODEL)
    run_openai_parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    run_openai_parser.add_argument("--api-key-env", default="OPENAI_API_KEY")
    run_openai_parser.add_argument("--reasoning-effort", default="low")
    run_openai_parser.add_argument("--verbosity", default="low")
    run_openai_parser.add_argument("--limit", type=int)
    run_openai_parser.add_argument("--delay-seconds", type=float, default=0.0)
    run_openai_parser.add_argument("--max-retries", type=int, default=3)
    run_openai_parser.add_argument("--retry-backoff-seconds", type=float, default=2.0)
    run_openai_parser.add_argument("--timeout-seconds", type=float, default=120.0)
    run_openai_parser.add_argument("--no-resume", action="store_true")
    run_openai_parser.set_defaults(func=cmd_run_openai)
    return parser


def cmd_validate_dataset(args: argparse.Namespace) -> None:
    errors = validate_dataset(args.dataset_dir)
    if errors:
        for error in errors:
            print(error)
        raise SystemExit(1)
    print("dataset valid")


def cmd_describe_dataset(args: argparse.Namespace) -> None:
    summary = summarize_dataset(args.dataset_dir)
    print(f"Dataset: {summary['name']} {summary['version']}")
    print(f"Split: {summary['split']}")
    print(f"Instances: {summary['instance_count']}")
    print(f"Has hidden scoring: {summary['has_hidden_scoring']}")
    print("Tracks:")
    for key, value in sorted(summary["tracks"].items()):
        print(f"- {key}: {value}")
    print("Task types:")
    for key, value in sorted(summary["task_types"].items()):
        print(f"- {key}: {value}")
    print(f"Reference-backed instances: {summary['reference_backed_instances']}")
    print("Coverage:")
    for key, values in sorted(summary["coverage"].items()):
        print(f"- {key}: {', '.join(values) if values else '<none>'}")
    print(
        f"Visible prompt fields: {', '.join(summary['prompt_policy'].get('model_visible_fields', []))}"
    )
    print(
        f"Hidden scoring fields: {', '.join(summary['prompt_policy'].get('scorer_hidden_fields', []))}"
    )


def cmd_validate_submission(args: argparse.Namespace) -> None:
    errors = validate_submission(args.dataset_dir, args.submission_path)
    if errors:
        for error in errors:
            print(error)
        raise SystemExit(1)
    print("submission valid")


def cmd_score(args: argparse.Namespace) -> None:
    report = score_submission(args.dataset_dir, args.submission_path)
    schema_errors = validate_document(report, "score_report.schema.json")
    if schema_errors:
        for error in schema_errors:
            print(error, file=sys.stderr)
        raise SystemExit(1)
    if args.output:
        write_json(args.output, report)
    print(render_report(report))


def cmd_report(args: argparse.Namespace) -> None:
    report = read_json(args.report_path)
    print(render_report(report))


def cmd_compare_reports(args: argparse.Namespace) -> None:
    reports = [read_json(path) for path in args.report_paths]
    if args.csv_output:
        write_report_comparison_csv(reports, args.csv_output)
        print(f"wrote CSV comparison to {args.csv_output}")
    print(render_report_comparison(reports))


def cmd_ingest_report(args: argparse.Namespace) -> None:
    payload = ingest_report(
        args.report_path,
        args.leaderboard_path,
        label=args.label,
        provider=args.provider,
        model_version=args.model_version,
        run_type=args.run_type,
        submission_date=args.submission_date,
        notes=args.notes,
    )
    if args.markdown_output:
        write_leaderboard_markdown(payload, args.markdown_output)
        print(f"wrote leaderboard markdown to {args.markdown_output}")
    print(f"ingested report into {args.leaderboard_path}")
    print(render_leaderboard_markdown(payload))


def cmd_render_leaderboard(args: argparse.Namespace) -> None:
    payload = load_leaderboard(args.leaderboard_path)
    if args.output:
        write_leaderboard_markdown(payload, args.output)
        print(f"wrote leaderboard markdown to {args.output}")
    print(render_leaderboard_markdown(payload))


def cmd_make_baseline(args: argparse.Namespace) -> None:
    write_baseline_submission(args.dataset_dir, args.output_path)
    print(f"wrote baseline submission to {args.output_path}")


def cmd_export_prompts(args: argparse.Namespace) -> None:
    export_prompt_pack(args.dataset_dir, args.output_path)
    print(f"wrote prompt pack to {args.output_path}")


def cmd_build_submission(args: argparse.Namespace) -> None:
    build_submission_from_responses(
        args.dataset_dir,
        args.responses_path,
        args.output_path,
        args.model_name,
    )
    print(f"wrote submission to {args.output_path}")


def cmd_run_openai(args: argparse.Namespace) -> None:
    paths = run_openai_benchmark(
        args.dataset_dir,
        args.output_dir,
        model=args.model,
        base_url=args.base_url,
        api_key_env=args.api_key_env,
        reasoning_effort=args.reasoning_effort,
        verbosity=args.verbosity,
        limit=args.limit,
        delay_seconds=args.delay_seconds,
        max_retries=args.max_retries,
        retry_backoff_seconds=args.retry_backoff_seconds,
        timeout_seconds=args.timeout_seconds,
        resume=not args.no_resume,
        progress_callback=print,
    )
    submission_path = f"{paths['run_dir']}/submission.json"
    report_path = f"{paths['run_dir']}/report.json"

    build_submission_from_responses(
        args.dataset_dir,
        paths["responses_path"],
        submission_path,
        args.model,
    )
    submission_errors = validate_submission(args.dataset_dir, submission_path)
    if submission_errors:
        for error in submission_errors:
            print(error, file=sys.stderr)
        raise SystemExit(1)

    report = score_submission(args.dataset_dir, submission_path)
    schema_errors = validate_document(report, "score_report.schema.json")
    if schema_errors:
        for error in schema_errors:
            print(error, file=sys.stderr)
        raise SystemExit(1)
    write_json(report_path, report)
    print(f"run directory: {paths['run_dir']}")
    print(f"wrote config to {paths['config_path']}")
    print(f"wrote status to {paths['status_path']}")
    print(f"wrote prompts to {paths['prompts_path']}")
    print(f"wrote raw responses to {paths['raw_responses_path']}")
    print(f"wrote responses to {paths['responses_path']}")
    print(f"wrote failures to {paths['failures_path']}")
    print(f"wrote submission to {submission_path}")
    print(f"wrote report to {report_path}")
    print(render_report(report))


if __name__ == "__main__":
    main()
