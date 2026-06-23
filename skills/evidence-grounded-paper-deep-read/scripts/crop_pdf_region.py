#!/usr/bin/env python3
"""Crop a precise figure/table region from a PDF page.

Coordinates are PDF points in pdfplumber/PDF coordinate space:
left top right bottom, with origin at the top-left of the page.
Use page previews to inspect the page and choose the bounding box.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def require_pdfplumber():
    try:
        import pdfplumber  # type: ignore
    except ImportError as exc:
        raise SystemExit(
            "pdfplumber is required for region cropping. Install with: python -m pip install pdfplumber"
        ) from exc
    return pdfplumber


def parse_bbox(value: str) -> tuple[float, float, float, float]:
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError("bbox must be 'left,top,right,bottom'")
    try:
        left, top, right, bottom = [float(part) for part in parts]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("bbox values must be numbers") from exc
    if right <= left or bottom <= top:
        raise argparse.ArgumentTypeError("bbox must satisfy right > left and bottom > top")
    return left, top, right, bottom


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--page", type=int, required=True, help="1-based page number")
    parser.add_argument("--bbox", type=parse_bbox, required=True, help="left,top,right,bottom")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--dpi", type=int, default=220)
    parser.add_argument("--label", default="")
    parser.add_argument("--manifest", type=Path, default=None)
    args = parser.parse_args()

    if not args.pdf.exists():
        raise SystemExit(f"PDF not found: {args.pdf}")
    if args.page < 1:
        raise SystemExit("--page must be 1 or greater")

    pdfplumber = require_pdfplumber()
    args.out.parent.mkdir(parents=True, exist_ok=True)

    with pdfplumber.open(args.pdf) as pdf:
        if args.page > len(pdf.pages):
            raise SystemExit(f"Page {args.page} out of range; PDF has {len(pdf.pages)} pages")
        page = pdf.pages[args.page - 1]
        cropped = page.crop(args.bbox, strict=False)
        cropped.to_image(resolution=args.dpi).save(args.out, format="PNG")

    record = {
        "kind": "cropped_region",
        "label": args.label,
        "page": args.page,
        "bbox": list(args.bbox),
        "path": str(args.out),
        "dpi": args.dpi,
    }

    if args.manifest:
        manifest = []
        if args.manifest.exists():
            try:
                existing = json.loads(args.manifest.read_text(encoding="utf-8"))
                manifest = existing if isinstance(existing, list) else existing.get("items", [])
            except json.JSONDecodeError:
                manifest = []
        manifest.append(record)
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
