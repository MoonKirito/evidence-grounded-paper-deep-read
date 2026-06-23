from __future__ import annotations

import argparse
import sys
from pathlib import Path

from paperdeepread.config import load_config, write_default_config
from paperdeepread.pipeline import RunOptions, run_pipeline
from paperdeepread.prompts import build_skill_prompt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="paperdeepread",
        description="Generate evidence-grounded paper deep-reading reports from PDF folders.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_config = subparsers.add_parser("init-config", help="Write a default CLI config file.")
    init_config.add_argument("--path", type=Path, default=Path(".paperdeepread.toml"))
    init_config.add_argument("--force", action="store_true")

    run = subparsers.add_parser("run", help="Generate reports for all PDFs in a folder.")
    run.add_argument("--input", type=Path, required=True, help="Folder containing PDF files.")
    run.add_argument("--output", type=Path, default=Path("reports"), help="Output reports folder.")
    run.add_argument("--config", type=Path, default=Path(".paperdeepread.toml"))
    run.add_argument("--pdffigures2-jar", type=Path, default=None)
    run.add_argument("--java-path", default=None)
    run.add_argument("--limit", type=int, default=None, help="Process only the first N PDFs.")

    export_prompt = subparsers.add_parser(
        "export-skill-prompt",
        help="Export the reusable skill prompt for use in another model or agent.",
    )
    export_prompt.add_argument("--out", type=Path, default=Path("skill_prompt.md"))

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "init-config":
            write_default_config(args.path, force=args.force)
            print(f"Wrote config: {args.path}")
            print("Set your key before running:")
            print("$env:MIMO_API_KEY=\"your_key\"")
            return 0

        if args.command == "export-skill-prompt":
            args.out.write_text(build_skill_prompt(), encoding="utf-8")
            print(f"Wrote skill prompt: {args.out}")
            return 0

        if args.command == "run":
            config = load_config(args.config)
            jar = args.pdffigures2_jar
            if jar is None and config.pdffigures2.jar_path:
                jar = Path(config.pdffigures2.jar_path)
            java_path = args.java_path or config.pdffigures2.java_path
            reports = run_pipeline(
                RunOptions(
                    input_dir=args.input,
                    output_dir=args.output,
                    config=config,
                    pdffigures2_jar=jar,
                    java_path=java_path,
                    limit=args.limit,
                )
            )
            print("Generated reports:")
            for report in reports:
                print(f"- {report}")
            return 0
    except (FileExistsError, FileNotFoundError, RuntimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    parser.error(f"Unknown command: {args.command}")
    return 2
