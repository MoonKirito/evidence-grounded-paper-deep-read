#!/usr/bin/env python3
"""Extract page-level text from a paper PDF into Markdown and JSON.

Preferred backend: PyMuPDF. Fallback backend: pdfplumber.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def load_backend():
    try:
        import fitz  # type: ignore
        return "fitz", fitz
    except ImportError:
        pass

    try:
        import pdfplumber  # type: ignore
        return "pdfplumber", pdfplumber
    except ImportError as exc:
        raise SystemExit(
            "PDF text extraction requires PyMuPDF or pdfplumber. "
            "Install with: python -m pip install pymupdf pdfplumber"
        ) from exc


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_paragraphs(text: str) -> list[str]:
    parts = re.split(r"\n\s*\n", text)
    return [p.strip() for p in parts if p.strip()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    if not args.pdf.exists():
        raise SystemExit(f"PDF not found: {args.pdf}")

    backend_name, backend = load_backend()
    args.out.mkdir(parents=True, exist_ok=True)

    pages = []
    md_lines = [f"# Extracted Text: {args.pdf.name}", ""]

    paragraph_id = 1

    if backend_name == "fitz":
        doc = backend.open(args.pdf)
        page_iter = ((page_index, page.get_text("text")) for page_index, page in enumerate(doc, start=1))
    else:
        pdf = backend.open(args.pdf)
        page_iter = (
            (page_index, page.extract_text(x_tolerance=1, y_tolerance=3) or "")
            for page_index, page in enumerate(pdf.pages, start=1)
        )

    for page_index, raw_text in page_iter:
        text = normalize_text(raw_text)
        paragraphs = []
        md_lines.extend([f"## Page {page_index}", ""])
        for para in split_paragraphs(text):
            pid = f"P{paragraph_id:04d}"
            paragraphs.append({"id": pid, "text": para})
            md_lines.extend([f"### {pid}", para, ""])
            paragraph_id += 1
        pages.append({"page": page_index, "paragraphs": paragraphs})

    (args.out / "full_text.md").write_text("\n".join(md_lines), encoding="utf-8")
    (args.out / "sections.json").write_text(
        json.dumps(
            {"pdf": str(args.pdf), "backend": backend_name, "pages": pages},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"Backend: {backend_name}")
    print(f"Wrote {args.out / 'full_text.md'}")
    print(f"Wrote {args.out / 'sections.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
