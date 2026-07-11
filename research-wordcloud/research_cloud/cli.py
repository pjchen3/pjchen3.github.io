from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .config import load_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="research-cloud", description="Build a semantic, paper-traceable research topic cloud from PDFs.")
    subparsers = parser.add_subparsers(dest="command")
    analyze = subparsers.add_parser("analyze", help="Analyze a directory of publication PDFs")
    analyze.add_argument("positional_input", nargs="?", type=Path, help="PDF directory (short form)")
    analyze.add_argument("--input", dest="input_directory", type=Path, help="PDF directory")
    analyze.add_argument("--output", type=Path, default=Path("./output"), help="Output directory")
    analyze.add_argument("--config", type=Path, help="YAML configuration file")
    analyze.add_argument("--overrides", type=Path, help="Editable topic overrides YAML")
    analyze.add_argument("--author-name", help="Author name used for role weighting")
    analyze.add_argument("--language", default=None, help="Topic language (currently en)")
    analyze.add_argument("--max-words", type=int, help="Maximum final topic count")
    analyze.add_argument("--min-paper-count", type=int, help="Minimum distinct supporting papers")
    analyze.add_argument("--use-recency", action=argparse.BooleanOptionalAction, default=None)
    analyze.add_argument("--force", action="store_true", help="Ignore cached paper analyses")
    analyze.add_argument("--verbose", action="store_true")
    analyze.add_argument("--llm-provider", choices=["none", "openai-compatible", "local"])
    analyze.add_argument("--llm-model")
    analyze.add_argument("--api-base")
    return parser


def _cli_overrides(args: argparse.Namespace) -> dict[str, object]:
    result: dict[str, object] = {}
    if args.author_name:
        result.setdefault("author", {})["name"] = args.author_name
    if args.language:
        result.setdefault("topics", {})["language"] = args.language
    if args.max_words is not None:
        result.setdefault("topics", {})["final_max_words"] = args.max_words
    if args.min_paper_count is not None:
        result.setdefault("topics", {})["min_paper_count"] = args.min_paper_count
    if args.use_recency is not None:
        result.setdefault("weighting", {})["use_recency"] = args.use_recency
    if args.llm_provider:
        llm = result.setdefault("llm", {})
        llm["provider"] = args.llm_provider
        llm["enabled"] = args.llm_provider != "none"
    if args.llm_model:
        result.setdefault("llm", {})["model"] = args.llm_model
    if args.api_base:
        result.setdefault("llm", {})["api_base"] = args.api_base
    return result


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    raw = list(sys.argv[1:] if argv is None else argv)
    if raw and raw[0] not in {"analyze", "-h", "--help"}:
        raw.insert(0, "analyze")
    args = parser.parse_args(raw)
    if args.command != "analyze":
        parser.print_help()
        return 0
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s: %(message)s")
    # Verbose mode should expose this tool's decisions, not dependency font-discovery internals.
    logging.getLogger("matplotlib").setLevel(logging.WARNING)
    logging.getLogger("PIL").setLevel(logging.WARNING)
    from .pipeline import run_analysis

    config = load_config(args.config, _cli_overrides(args))
    input_directory = args.input_directory or args.positional_input or Path(config.input.pdf_directory)
    try:
        result = run_analysis(input_directory, args.output, config, force=args.force, overrides_path=args.overrides)
    except Exception as exc:
        logging.getLogger("research_cloud").error("%s", exc)
        return 1
    print(f"{result.found} PDFs found")
    print(f"{result.cached} loaded from cache")
    print(f"{result.analyzed} newly analyzed")
    print(f"{result.failed} failed")
    print(f"Outputs written to {args.output.resolve()}")
    return 0 if result.failed == 0 else 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
