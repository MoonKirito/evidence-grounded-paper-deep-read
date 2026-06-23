#!/usr/bin/env python3
"""Create a per-paper report workspace from the bundled Markdown template."""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path


def slugify(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = value.strip("-")
    return value or "paper"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--title", default="")
    parser.add_argument("--language", default="same as user request")
    parser.add_argument("--out-root", type=Path, default=Path("reports"))
    parser.add_argument("--template", type=Path, default=None)
    args = parser.parse_args()

    if not args.pdf.exists():
        raise SystemExit(f"PDF not found: {args.pdf}")

    skill_dir = Path(__file__).resolve().parents[1]
    template = args.template or skill_dir / "assets" / "report_template.md"
    if not template.exists():
        raise SystemExit(f"Template not found: {template}")

    title = args.title or args.pdf.stem
    out_dir = args.out_root / slugify(title)
    extracted_dir = out_dir / "extracted"
    figures_dir = extracted_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    source_pdf = out_dir / "source.pdf"
    if args.pdf.resolve() != source_pdf.resolve():
        shutil.copy2(args.pdf, source_pdf)

    report = template.read_text(encoding="utf-8")
    report = report.replace("{{TITLE}}", title)
    report = report.replace("{{PDF_FILE}}", source_pdf.name)
    report = report.replace("{{LANGUAGE}}", args.language)
    (out_dir / "report.md").write_text(report, encoding="utf-8")
    (out_dir / "evidence_cards.md").write_text("# Evidence Cards\n\n", encoding="utf-8")

    print(f"Wrote {out_dir / 'report.md'}")
    print(f"Wrote {out_dir / 'evidence_cards.md'}")
    print(f"Workspace: {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
