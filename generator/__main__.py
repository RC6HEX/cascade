"""CLI entry point.

Usage:
    python -m generator --task task_a
    python -m generator --task task_b --output ./output_b
    python -m generator --input ./input/task_c --output ./output_c --no-tests
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from .config import Config
from .pipeline import run_pipeline


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="generator",
        description="Autonomous code generator: БТ+БП → docs + src + tests + README",
    )
    parser.add_argument(
        "--task",
        help="Shortcut: load input from input/<task>/ and write to output/<task>/. "
             "Examples: task_a, task_b, task_c",
    )
    parser.add_argument(
        "--input",
        type=Path,
        help="Custom input directory (must contain business_requirements.md and business_process.md)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Custom output directory (default: output/<task> or output/)",
    )
    parser.add_argument(
        "--no-use-cases",
        action="store_true",
        help="Skip use cases generation (faster, cheaper)",
    )
    parser.add_argument(
        "--no-tests",
        action="store_true",
        help="Skip tests generation",
    )
    parser.add_argument(
        "--provider",
        choices=("gemini", "openrouter"),
        help="Override LLM provider (otherwise from .env)",
    )
    parser.add_argument(
        "--model-fast",
        help="Override fast-tier model (use_cases / nfr / tests / readme)",
    )
    parser.add_argument(
        "--model-smart",
        help="Override smart-tier model (fr / code)",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    _setup_logging(args.verbose)
    log = logging.getLogger("generator.main")

    cfg = Config.load()
    if args.provider:
        # ad-hoc override: rebuild frozen dataclass
        from dataclasses import replace
        cfg = replace(cfg, provider=args.provider)

    # Resolve input
    if args.input:
        input_dir = args.input.resolve()
    elif args.task:
        input_dir = (cfg.project_root / "input" / args.task).resolve()
    else:
        log.error("Specify either --task or --input")
        return 2

    # Resolve output
    if args.output:
        output_dir = args.output.resolve()
    elif args.task:
        output_dir = (cfg.project_root / "output" / args.task).resolve()
    else:
        output_dir = (cfg.project_root / "output").resolve()

    log.info("Provider: %s | fast=%s smart=%s", cfg.provider, cfg.model_fast, cfg.model_smart)
    log.info("Input  : %s", input_dir)
    log.info("Output : %s", output_dir)

    overrides: dict[str, str] = {}
    if args.model_fast:
        overrides["fast"] = args.model_fast
    if args.model_smart:
        overrides["smart"] = args.model_smart

    started = time.time()
    try:
        report = run_pipeline(
            cfg=cfg,
            input_dir=input_dir,
            output_dir=output_dir,
            skip_use_cases=args.no_use_cases,
            skip_tests=args.no_tests,
            model_overrides=overrides or None,
        )
    except Exception as e:
        log.exception("Pipeline failed: %s", e)
        return 1

    elapsed = time.time() - started
    log.info("DONE in %.1fs. Files generated: %d", elapsed, report["files_generated"])
    log.info("Usage:\n%s", report["usage"].summary())
    return 0


if __name__ == "__main__":
    sys.exit(main())
