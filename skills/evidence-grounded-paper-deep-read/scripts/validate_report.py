#!/usr/bin/env python3
"""Validate the five-part report, math delimiters and pdffigures2 image provenance."""
from __future__ import annotations

import argparse
import json
import importlib.util
import re
import sys
from pathlib import Path

CONCEPTS = ["what", "why", "how", "experiment", "question"]
EVIDENCE = r"Evidence:|Inference from|证据[：:]|推断依据[：:]"

_spec = importlib.util.spec_from_file_location("visual_contract", Path(__file__).with_name("visual_contract.py"))
_contract = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_contract)


def math_problems(text: str) -> list[str]:
    problems = []
    if re.search(r"\\[\[\]()]", text):
        problems.append("Use $...$ / $$ instead of LaTeX parenthesis or bracket delimiters")
    for code in re.findall(r"```.*?```", text, re.S):
        if re.search(r"(?<!\\)\$", code):
            problems.append("Math must not be placed inside fenced code blocks")
    for code in re.findall(r"(?<!`)`([^`\n]+)`(?!`)", text):
        if re.search(r"(?<!\\)\$", code):
            problems.append("Math must not be wrapped in inline code")
    text = re.sub(r"```.*?```|`[^`\n]*`", "", text, flags=re.S)
    in_display = False
    inline_open = False
    for line in text.splitlines():
        if line.strip() == "$$":
            if inline_open:
                problems.append("Inline math crosses a display boundary")
                inline_open = False
            in_display = not in_display
            continue
        if re.search(r"(?<!\\)\$\$", line):
            problems.append("Display $$ delimiters must each occupy their own line")
        if not in_display:
            inline_open = bool((int(inline_open) + len(re.findall(r"(?<!\\)\$", line))) % 2)
            if not line.strip() and inline_open:
                problems.append("Unclosed inline math before paragraph boundary")
                inline_open = False
    if in_display:
        problems.append("Unclosed display math delimiter")
    if inline_open:
        problems.append("Unclosed inline math delimiter")
    return problems


def validate_report(report: Path) -> list[str]:
    text = report.read_text(encoding="utf-8-sig")
    problems = []
    prose = re.sub(r"```.*?```", "", text, flags=re.S)
    headings = list(re.finditer(r"^##\s+(.+)$", prose, re.M))
    if len(headings) != 5:
        problems.append("Expected exactly five level-2 sections: What, Why, How, Experiment, Question")
    for index, concept in enumerate(CONCEPTS):
        if index >= len(headings):
            break
        heading = headings[index]
        if not re.match(rf"{index + 1}\.\s+{concept}\b", heading.group(1), re.I):
            problems.append(f"Section {index + 1} must be {concept.title()} in narrative order")
        end = headings[index + 1].start() if index + 1 < len(headings) else len(prose)
        body = prose[heading.end():end].strip()
        if not body:
            problems.append(f"Empty section: {concept}")
        if not re.search(EVIDENCE, body, re.I):
            problems.append(f"Section lacks an evidence or inference anchor: {concept}")
    if not re.search(r"^#\s+.+", prose, re.M):
        problems.append("Missing report title")
    if re.search(r"\bTODO\b|生成失败", text):
        problems.append("Report contains unfinished placeholders")
    problems.extend(math_problems(text))
    # Images follow the global plan; all embedded paths must come from pdffigures2.
    images = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", prose)
    manifest_path = report.parent / "extracted" / "figure_manifest.json"
    analysis_path = report.parent / "extracted" / "visual_analysis.json"
    plan_path = report.parent / "extracted" / "visual_plan.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig")) if manifest_path.exists() else {}
    analysis = json.loads(analysis_path.read_text(encoding="utf-8-sig")) if analysis_path.exists() else {}
    allowed = {item.get("image") for item in manifest.get("items", []) if item.get("image")}
    analyzed = {item.get("image") for item in analysis.get("items", []) if item.get("status") == "analyzed"}
    if manifest_path.exists():
        if manifest.get("source") != "pdffigures2":
            problems.append("Figure manifest must come from pdffigures2")
        if not analysis.get("complete"):
            problems.append("All-visual analysis must be complete before report writing")
        entries = analysis.get("items", [])
        manifest_keys = {(item.get("figType"), str(item.get("name"))) for item in manifest.get("items", [])}
        analysis_keys = {(item.get("figType"), str(item.get("name"))) for item in entries}
        if manifest_keys != analysis_keys:
            problems.append("Visual analysis does not cover every manifest item")
        if any(item.get("status") not in {"analyzed", "unreadable", "unavailable"} for item in entries):
            problems.append("Visual analysis contains unfinished entries")
        if not plan_path.exists():
            problems.append("Missing global visual plan; method/claim coverage was not checked")
        else:
            plan = json.loads(plan_path.read_text(encoding="utf-8-sig"))
            if not plan.get("complete"):
                problems.append("Global visual plan is incomplete")
            problems.extend(_contract.plan_problems(plan, analysis))
            problems.extend(_contract.coverage_problems(prose, plan))
    seen = set()
    for image in images:
        image = image.strip().strip("<>")
        path = (report.parent / image).resolve()
        if image in seen:
            problems.append(f"Duplicate report image: {image}")
        seen.add(image)
        if "preview" in image.lower():
            problems.append(f"Page previews are not allowed: {image}")
        if not path.is_relative_to((report.parent / "extracted" / "figures").resolve()):
            problems.append(f"Image must be inside extracted/figures: {image}")
        if not path.is_file():
            problems.append(f"Image file does not exist: {image}")
        if manifest.get("source") != "pdffigures2" or image not in allowed:
            problems.append(f"Image is not in the pdffigures2 manifest: {image}")
        if image not in analyzed:
            problems.append(f"Image was not analyzed before drafting: {image}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    try:
        problems = validate_report(args.report)
    except (OSError, ValueError, TypeError) as exc:
        problems = [f"Cannot validate report artifacts: {exc}"]
    if problems:
        print("Validation failed:")
        for problem in problems:
            print(f"- {problem}")
        return 1
    print("Validation passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
