from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from paperdeepread.evidence_pack import build_stage_text_pack, estimate_char_budget
from paperdeepread.prompts import build_skill_prompt, load_json_for_prompt
from paperdeepread.providers.mimo import ChatMessage


@dataclass(frozen=True)
class ReportStage:
    key: str
    heading: str
    description: str
    keywords: list[str]
    always_keywords: list[str]


REPORT_STAGES = [
    ReportStage(
        key="overview_metadata",
        heading="## 0. 一句话总览",
        description="写第 0 节和第 1 节：一句话总览、论文基本信息表。",
        keywords=["abstract", "title", "author", "introduction", "contribution"],
        always_keywords=["abstract"],
    ),
    ReportStage(
        key="what_why",
        heading="## 2. 作者做了什么",
        description="写第 2 节和第 3 节：作者做了什么、为什么做这件事。",
        keywords=[
            "abstract",
            "introduction",
            "motivation",
            "challenge",
            "contribution",
            "problem",
            "related work",
        ],
        always_keywords=["abstract", "introduction"],
    ),
    ReportStage(
        key="how_formula",
        heading="## 4. 作者具体怎么做",
        description="写第 4 节和第 6 节：方法流程、模块细节、公式与关键技术细节。",
        keywords=[
            "method",
            "methods",
            "methodology",
            "approach",
            "model",
            "algorithm",
            "training",
            "loss",
            "equation",
            "feature",
            "network",
        ],
        always_keywords=["abstract"],
    ),
    ReportStage(
        key="experiment",
        heading="## 5. 作者如何验证",
        description="写第 5 节：实验问题、数据集、指标、baseline、主结果、消融和实验边界。",
        keywords=[
            "experiment",
            "experiments",
            "results",
            "dataset",
            "baseline",
            "evaluation",
            "metric",
            "ablation",
            "table",
            "performance",
        ],
        always_keywords=["abstract"],
    ),
    ReportStage(
        key="innovation_limits_background",
        heading="## 7. 创新点逐条拆解",
        description="写第 7-10 节：创新点、局限性、初学者背景、复现与进一步阅读建议。",
        keywords=[
            "discussion",
            "conclusion",
            "limitation",
            "future",
            "implementation",
            "code",
            "parameter",
            "clinical",
            "application",
        ],
        always_keywords=["abstract", "conclusion"],
    ),
    ReportStage(
        key="checklist",
        heading="## 11. 完整性自检",
        description="写第 11 节：完整性自检表。根据已经生成的报告内容如实填写。",
        keywords=["abstract", "method", "experiment", "results", "conclusion"],
        always_keywords=["abstract"],
    ),
]


def strip_markdown_fence(text: str) -> str:
    text = text.strip()
    match = re.fullmatch(r"```(?:markdown)?\s*(.*?)```", text, flags=re.DOTALL)
    if match:
        return match.group(1).strip()
    return text


def assemble_sectioned_report(title: str, sections: dict[str, str]) -> str:
    parts = [f"# 论文精读报告：{title}"]
    for stage in REPORT_STAGES:
        content = strip_markdown_fence(sections.get(stage.key, "")).strip()
        if not content:
            content = f"{stage.heading}\n\n生成失败：该阶段没有返回内容。"
        content = re.sub(r"^# .+?\n+", "", content)
        parts.append(content)
    return "\n\n".join(parts).strip() + "\n"


def load_sections_json(extracted_dir: Path) -> dict[str, Any]:
    path = extracted_dir / "sections.json"
    if not path.exists():
        return {"pages": []}
    return json.loads(path.read_text(encoding="utf-8", errors="replace"))


def build_stage_messages(
    *,
    stage: ReportStage,
    title: str,
    pdf_name: str,
    extracted_dir: Path,
    paper_index_path: Path,
    language: str,
    max_input_chars: int,
    previous_sections: dict[str, str],
) -> list[ChatMessage]:
    sections_json = load_sections_json(extracted_dir)
    figure_manifest = load_json_for_prompt(extracted_dir / "figure_manifest.json")
    figure_count = len(json.loads(figure_manifest).get("items", []))
    text_budget = estimate_char_budget(max_input_chars=max_input_chars, figure_count=figure_count)
    evidence_pack = build_stage_text_pack(
        sections=sections_json,
        stage_keywords=stage.keywords,
        always_keywords=stage.always_keywords,
        budget_chars=text_budget,
    )
    paper_index = paper_index_path.read_text(encoding="utf-8", errors="replace") if paper_index_path.exists() else "{}"
    prior = "\n\n".join(previous_sections.values())

    system = (
        "你是一名严谨的论文精读助手。只输出最终 Markdown，不输出思考过程。"
        "报告语言必须统一为中文；除必要术语外，不要使用英文结构标题。"
        "图表必须自然融入对应正文段落，不要单开图表精读章节。"
    )

    user = f"""
请为论文精读报告生成一个局部阶段。

论文标题：{title}
PDF 文件名：{pdf_name}
报告语言：{language}
当前阶段：{stage.description}

硬性要求：
- 只输出本阶段要求的 Markdown 章节，不要输出完整报告标题。
- 必须使用中文标题，例如 `{stage.heading}`；禁止使用 WHAT/WHY/HOW/EXPERIMENT 作为标题。
- 重要判断必须带 evidence marker，例如 `(Evidence: Page 3, Fig. 2)`。
- 如果使用图片，必须引用 Figure And Table Manifest 中的 `image` 路径，例如 `![Figure 2](extracted/figures/source-Figure2-1.png)`。
- 不要编造没有证据的作者、年份、实验结果或公式。

# Skill Excerpt
{build_skill_prompt(max_chars=22000)}

# Previous Generated Sections
```markdown
{prior}
```

# Paper Index
```json
{paper_index[:20000]}
```

# Figure And Table Manifest
```json
{figure_manifest}
```

# Stage Evidence Pack
```markdown
{evidence_pack}
```
""".strip()

    return [ChatMessage(role="system", content=system), ChatMessage(role="user", content=user)]
