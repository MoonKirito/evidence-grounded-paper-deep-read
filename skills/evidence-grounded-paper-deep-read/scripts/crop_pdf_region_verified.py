#!/usr/bin/env python3
"""Crop a PDF figure/table with margin and edge-tightness verification."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

from crop_pdf_region import parse_bbox, require_pdfplumber


def expand_bbox(
    bbox: tuple[float, float, float, float],
    margin: float,
    page_width: float,
    page_height: float,
) -> tuple[float, float, float, float]:
    left, top, right, bottom = bbox
    return (
        max(0.0, left - margin),
        max(0.0, top - margin),
        min(page_width, right + margin),
        min(page_height, bottom + margin),
    )


def edge_dark_fraction(image_path: Path, edge_px: int = 8, threshold: int = 245) -> dict:
    image = Image.open(image_path).convert("L")
    width, height = image.size
    edge_px = max(1, min(edge_px, width // 4, height // 4))
    boxes = {
        "left": (0, 0, edge_px, height),
        "right": (width - edge_px, 0, width, height),
        "top": (0, 0, width, edge_px),
        "bottom": (0, height - edge_px, width, height),
    }
    result = {}
    for name, box in boxes.items():
        crop = image.crop(box)
        dark = crop.point(lambda p: 255 if p < threshold else 0)
        stat = ImageStat.Stat(dark)
        result[name] = round(stat.mean[0] / 255.0, 4)
    return result


def crop_page(pdf_path: Path, page_number: int, bbox: tuple[float, float, float, float], out: Path, dpi: int) -> None:
    pdfplumber = require_pdfplumber()
    out.parent.mkdir(parents=True, exist_ok=True)
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[page_number - 1]
        page.crop(bbox, strict=False).to_image(resolution=dpi).save(out, format="PNG")


def page_size(pdf_path: Path, page_number: int) -> tuple[float, float]:
    pdfplumber = require_pdfplumber()
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[page_number - 1]
        return float(page.width), float(page.height)


def quality_status(edges: dict, tight_threshold: float) -> tuple[str, list[str]]:
    warnings = [
        f"{edge} edge has high non-white density ({value})"
        for edge, value in edges.items()
        if value >= tight_threshold
    ]
    return ("needs_review" if warnings else "verified", warnings)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--page", type=int, required=True)
    parser.add_argument("--bbox", type=parse_bbox, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--dpi", type=int, default=240)
    parser.add_argument("--margin", type=float, default=12.0, help="PDF-point margin added around bbox")
    parser.add_argument("--edge-px", type=int, default=10)
    parser.add_argument("--tight-threshold", type=float, default=0.03)
    parser.add_argument("--label", default="")
    parser.add_argument("--manifest", type=Path, default=None)
    args = parser.parse_args()

    if not args.pdf.exists():
        raise SystemExit(f"PDF not found: {args.pdf}")

    width, height = page_size(args.pdf, args.page)
    expanded = expand_bbox(args.bbox, args.margin, width, height)
    crop_page(args.pdf, args.page, expanded, args.out, args.dpi)

    edges = edge_dark_fraction(args.out, edge_px=args.edge_px)
    status, warnings = quality_status(edges, args.tight_threshold)
    record = {
        "kind": "verified_crop",
        "label": args.label,
        "page": args.page,
        "original_bbox": list(args.bbox),
        "expanded_bbox": list(expanded),
        "margin": args.margin,
        "path": str(args.out),
        "dpi": args.dpi,
        "verification": {
            "status": status,
            "edge_dark_fraction": edges,
            "warnings": warnings,
            "note": "Edge check detects likely tight crops; visual review is still required.",
        },
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
    print(f"Status: {status}")
    if warnings:
        print("Warnings:")
        for warning in warnings:
            print(f"- {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
