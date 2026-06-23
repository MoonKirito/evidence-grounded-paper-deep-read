#!/usr/bin/env python3
"""Extract embedded images and render page previews from a paper PDF.

Preferred backend: PyMuPDF.
Fallbacks: pypdf embedded-image extraction and pdfplumber page previews.
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
            "Figure/page extraction requires PyMuPDF or pdfplumber. "
            "Install with: python -m pip install pymupdf pdfplumber"
        ) from exc
    return None


def sanitize_name(value: str) -> str:
    value = value.strip().replace("\\", "/").split("/")[-1]
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", value)
    return value or "image.png"


def extract_with_pypdf(pdf_path: Path, figures_dir: Path, out_root: Path) -> tuple[list[dict], int]:
    try:
        from pypdf import PdfReader  # type: ignore
    except ImportError:
        return [], 0

    reader = PdfReader(str(pdf_path))
    manifest = []
    image_count = 0

    for page_index, page in enumerate(reader.pages, start=1):
        images = getattr(page, "images", [])
        for image_index, image in enumerate(images, start=1):
            data = getattr(image, "data", None)
            if not data:
                continue
            original_name = sanitize_name(getattr(image, "name", "") or f"image-{image_index}.png")
            suffix = Path(original_name).suffix or ".png"
            name = f"page-{page_index:03d}-xobject-{image_index:02d}{suffix}"
            path = figures_dir / name
            path.write_bytes(data)
            image_count += 1
            manifest.append(
                {
                    "kind": "embedded_image_pypdf",
                    "page": page_index,
                    "index_on_page": image_index,
                    "path": str(path.relative_to(out_root)),
                    "original_name": original_name,
                    "bytes": len(data),
                    "note": "PDF image object; may be a full figure, subpanel, bitmap layer, or logo.",
                }
            )

    return manifest, image_count


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--render-pages", action="store_true")
    parser.add_argument("--dpi", type=int, default=180)
    args = parser.parse_args()

    if not args.pdf.exists():
        raise SystemExit(f"PDF not found: {args.pdf}")

    backend_name, backend = load_backend()
    figures_dir = args.out / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    manifest = []
    image_count = 0

    if backend_name == "fitz":
        doc = backend.open(args.pdf)
        for page_index, page in enumerate(doc, start=1):
            for image_index, image in enumerate(page.get_images(full=True), start=1):
                xref = image[0]
                extracted = doc.extract_image(xref)
                ext = extracted.get("ext", "png")
                image_count += 1
                name = f"page-{page_index:03d}-image-{image_index:02d}.{ext}"
                path = figures_dir / name
                path.write_bytes(extracted["image"])
                manifest.append(
                    {
                        "kind": "embedded_image",
                        "page": page_index,
                        "index_on_page": image_index,
                        "path": str(path.relative_to(args.out)),
                        "xref": xref,
                    }
                )

            if args.render_pages:
                zoom = args.dpi / 72
                matrix = backend.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=matrix, alpha=False)
                name = f"page-{page_index:03d}-preview.png"
                path = figures_dir / name
                pix.save(path)
                manifest.append(
                    {
                        "kind": "page_preview",
                        "page": page_index,
                        "path": str(path.relative_to(args.out)),
                        "dpi": args.dpi,
                    }
                )
    else:
        pypdf_manifest, pypdf_image_count = extract_with_pypdf(args.pdf, figures_dir, args.out)
        manifest.extend(pypdf_manifest)
        image_count += pypdf_image_count

        if not args.render_pages:
            if pypdf_image_count == 0:
                print("PyMuPDF unavailable and pypdf found no embedded images.")
                print("Re-run with --render-pages to produce page previews for manual crop selection.")
            else:
                print("PyMuPDF unavailable; extracted embedded image objects with pypdf.")
                print("Use page previews to verify whether each object is a complete figure or only a subcomponent.")
        with backend.open(args.pdf) as pdf:
            for page_index, page in enumerate(pdf.pages, start=1):
                if not args.render_pages:
                    continue
                name = f"page-{page_index:03d}-preview.png"
                path = figures_dir / name
                page.to_image(resolution=args.dpi).save(path, format="PNG")
                manifest.append(
                    {
                        "kind": "page_preview_fallback",
                        "page": page_index,
                        "path": str(path.relative_to(args.out)),
                        "dpi": args.dpi,
                    }
                )

    (args.out / "figure_manifest.json").write_text(
        json.dumps(
            {"pdf": str(args.pdf), "backend": backend_name, "items": manifest},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"Backend: {backend_name}")
    print(f"Extracted {image_count} embedded images")
    print(f"Wrote {args.out / 'figure_manifest.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
