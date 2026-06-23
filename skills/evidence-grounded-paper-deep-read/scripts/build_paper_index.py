#!/usr/bin/env python3
"""Build a paper index scaffold from extracted text and figure metadata."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


SECTION_PATTERNS = [
    "abstract",
    "introduction",
    "related work",
    "background",
    "method",
    "methodology",
    "approach",
    "experiment",
    "experiments",
    "results",
    "analysis",
    "discussion",
    "limitation",
    "limitations",
    "conclusion",
    "references",
]


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def looks_like_heading(text: str) -> bool:
    compact = re.sub(r"^\d+(\.\d+)*\s*", "", text.strip()).lower()
    if len(compact) > 80:
        return False
    return any(compact.startswith(pattern) for pattern in SECTION_PATTERNS)


def collect_section_candidates(sections: dict) -> list[dict]:
    candidates = []
    for page in sections.get("pages", []):
        for para in page.get("paragraphs", []):
            text = para.get("text", "")
            first_line = text.splitlines()[0] if text else ""
            if looks_like_heading(first_line):
                candidates.append(
                    {
                        "heading": first_line.strip(),
                        "page": page.get("page"),
                        "paragraph_id": para.get("id"),
                    }
                )
    return candidates


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--extracted", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    sections = load_json(args.extracted / "sections.json")
    figures = load_json(args.extracted / "figure_manifest.json")
    index = {
        "metadata": {
            "title": "",
            "authors": "",
            "venue_year": "",
            "source_pdf": sections.get("pdf") or figures.get("pdf") or "",
        },
        "section_candidates": collect_section_candidates(sections),
        "claims_to_verify": [],
        "contributions": [],
        "method_modules": [],
        "formulas": [],
        "figures_and_tables": figures.get("items", []),
        "experiments": [],
        "limitations": [],
        "notes": [
            "This scaffold must be completed by reading the extracted text and original PDF.",
            "Do not treat section candidates as authoritative without checking the PDF.",
        ],
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
