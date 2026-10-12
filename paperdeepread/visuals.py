"""Analyze every pdffigures2 visual before drafting report prose."""
from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import re
from pathlib import Path
from typing import Callable

from paperdeepread.providers.base import ChatMessage, ModelClient


def parse_json_response(content: str) -> dict:
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content).strip()
    try:
        value = json.loads(content)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Visual analysis must return valid JSON.") from exc
    if not isinstance(value, dict):
        raise RuntimeError("Visual analysis must return a JSON object.")
    return value


def image_part(path: Path) -> dict:
    mime = mimetypes.guess_type(path.name)[0]
    if mime not in {"image/png", "image/jpeg", "image/webp"}:
        raise RuntimeError(f"Unsupported extracted image format: {path.name}")
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{encoded}", "detail": "high"}}


def analyze_visuals(extracted_dir: Path, client: ModelClient, language: str,
                    on_progress: Callable[[str], None] | None = None) -> Path:
    manifest = json.loads((extracted_dir / "figure_manifest.json").read_text(encoding="utf-8-sig"))
    if manifest.get("source") != "pdffigures2":
        raise RuntimeError("Figure/table extraction must use pdffigures2 before report generation.")
    sections = json.loads((extracted_dir / "sections.json").read_text(encoding="utf-8-sig"))
    output = extracted_dir / "visual_analysis.json"
    if output.exists():
        output.unlink()  # A failed refresh must not leave a stale "complete" inventory.
    records = []
    cache_dir = extracted_dir / "visual-analysis-cache"
    cache_dir.mkdir(exist_ok=True)
    for number, item in enumerate(manifest.get("items", [])):
        if on_progress:
            on_progress(f"[visual] {item.get('figType', '')} {item.get('name', '')}: {number + 1}/{len(manifest.get('items', []))}")
        record = dict(item)
        image = item.get("image", "")
        path = (extracted_dir.parent / image).resolve() if image else None
        if path and not path.is_relative_to((extracted_dir / "figures").resolve()):
            raise RuntimeError(f"Extracted image is outside pdffigures2 directory: {image}")
        if not path or not path.is_file():
            record.update(status="unavailable", selected=False, section="none",
                          reason="pdffigures2 did not produce an image; caption-only evidence.")
            records.append(record)
            continue
        # pdffigures2 pages are zero based; text extraction is one based.
        page = int(item.get("page") or 0) + 1
        nearby = []
        kind_pattern = "Tables?" if str(item.get("figType", "")).lower() == "table" else r"Fig(?:ure)?s?\.?"
        reference = re.compile(rf"\b{kind_pattern}\s+{re.escape(str(item.get('name', '')))}\b", re.I)
        for entry in sections.get("pages", []):
            if (int(entry.get("page") or 0) == 1
                    or abs(int(entry.get("page") or 0) - page) <= 1
                    or any(reference.search(str(p.get("text", ""))) for p in entry.get("paragraphs", []))):
                for paragraph in entry.get("paragraphs", []):
                    nearby.append(f"[Page {entry['page']}, {paragraph.get('id', '')}] {paragraph.get('text', '')}")
        prompt = f"""先分析这一张论文图/表，暂时不要写报告。分析语言：{language}。
元数据：{json.dumps(item, ensure_ascii=False)}
实际 PDF 页码（从 1 开始）：{page}
结合图片、图注和上下文解释内容；看不清的数字不能从图注猜出。
识别模块/箭头或行列/指标方向，记录关键观察、支持的作者主张、证明边界。
判断是否值得放入简洁的 what → why → how → experiment → question 报告；
不凑图数，重复或次要图表 selected=false。
只输出 JSON 对象，包含非空字符串 summary、observation、supports、limitation、reason、
section（what/why/how/experiment/question/none），布尔值 selected，
布尔值 readable（关键图像内容是否可读），以及非空字符串列表 evidence（真实页码/图号/表号/段落）。
readable=false 时 selected=false，并说明读图限制。
上下文：
{chr(10).join(nearby)[:24000]}
"""
        fingerprint = hashlib.sha256(
            (prompt + repr(client.config)).encode("utf-8") + path.read_bytes()
        ).hexdigest()
        cached = cache_dir / f"{number:04d}-{fingerprint}.json"
        if cached.exists():
            analysis = json.loads(cached.read_text(encoding="utf-8"))
        else:
            messages = [ChatMessage(role="system", content="实际看图并核对正文，不能编造看不清的内容。"),
                        ChatMessage(role="user", content=[{"type": "text", "text": prompt}, image_part(path)])]
            analysis = parse_json_response(client.complete(messages))
        for field in ("summary", "observation", "supports", "limitation", "reason"):
            if not isinstance(analysis.get(field), str) or not analysis[field].strip():
                raise RuntimeError(f"Visual analysis missing {field}: {image}")
        if type(analysis.get("selected")) is not bool or analysis.get("section") not in {
            "what", "why", "how", "experiment", "question", "none"
        } or (analysis["selected"] and analysis["section"] == "none"):
            raise RuntimeError(f"Invalid visual selection: {image}")
        if type(analysis.get("readable")) is not bool or (not analysis["readable"] and analysis["selected"]):
            raise RuntimeError(f"Invalid visual readability assessment: {image}")
        if not isinstance(analysis.get("evidence"), list) or not analysis["evidence"] or not all(
            isinstance(anchor, str) and anchor.strip() for anchor in analysis["evidence"]
        ):
            raise RuntimeError(f"Visual analysis missing evidence anchors: {image}")
        cached.write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")
        record.update(analysis)
        record.update(status="analyzed" if analysis["readable"] else "unreadable", pdf_page=page)
        records.append(record)

    # Text references flag possible extraction misses, not certified local visuals.
    text = "\n".join(str(p.get("text", "")) for entry in sections.get("pages", []) for p in entry.get("paragraphs", []))
    mentioned = set(re.findall(r"\b(Fig(?:ure)?s?\.?|Tables?)\s+([0-9]+|[IVX]+)\b", text, re.I))
    def identity(kind: str, name: str) -> tuple[str, str]:
        return ("table" if kind.lower().startswith("table") else "figure", name.upper())
    extracted = {identity(str(r.get("figType", "")), str(r.get("name", ""))) for r in records}
    unmatched = sorted({identity(kind, name) for kind, name in mentioned} - extracted)
    result = {"source": "pdffigures2", "complete": True, "items": records,
              "unmatched_text_references": [f"{kind} {name}" for kind, name in unmatched],
              "coverage_note": "Text references are possible misses. Missing visuals are never cropped with another tool."}
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return output
