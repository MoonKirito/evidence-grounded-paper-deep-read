from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from paperdeepread.evidence_pack import build_stage_text_pack, estimate_char_budget
from paperdeepread.prompts import build_skill_prompt, load_json_for_prompt
from paperdeepread.providers.base import ChatMessage


@dataclass(frozen=True)
class ReportStage:
    key: str
    heading: str
    description: str
    keywords: list[str]
    always_keywords: list[str]


REPORT_STAGES = [
    ReportStage("what", "## 1. What：做了什么", "说明具体任务、输入输出、核心做法与贡献。建议 200–350 字，不提前展开方法和实验。", ["abstract", "contribution", "propose", "task"], ["abstract"]),
    ReportStage("why", "## 2. Why：为什么做", "已有方法→具体不足→作者观察或启发→设计目标；区分作者陈述与推断。建议 300–500 字。", ["introduction", "related work", "motivation", "challenge", "problem", "limitation"], ["abstract"]),
    ReportStage("how", "## 3. How：如何实现", "详细展开输入→表征构造→关键模块→训练/优化→推理输出，每个核心模块讲清输入输出、内部操作、设计理由和与前后步骤的关系，关键公式就地定义符号。技术路线图按照全局计划去重后尽量全部展示，先交代如何读图，再结合模块、箭头和流程讲解；总览图与局部机制图通常互补。区分训练和推理，不能仅概述模块名称或省略核心技术细节。建议 1200–2000 字，复杂方法按需要扩展。", ["method", "approach", "model", "algorithm", "training", "loss", "equation", "feature", "network", "inference"], ["abstract"]),
    ReportStage("experiment", "## 4. Experiment：如何证明有效", "按作者目标选择实验：待验证主张→设置/基线/指标→关键结果→结论及边界。不要罗列全部实验。建议 500–800 字。", ["experiment", "results", "dataset", "baseline", "evaluation", "metric", "ablation", "table", "performance", "efficiency"], ["abstract"]),
    ReportStage("question", "## 5. Question：评价与疑问", "给出独立评价，区分作者局限与自己的推断；讨论影响主张的 2–4 个问题并提出可验证的补充实验。建议 300–500 字。", ["discussion", "conclusion", "limitation", "future", "failure", "baseline", "cost", "assumption"], ["abstract", "conclusion"]),
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
            raise RuntimeError(f"Report stage returned no content: {stage.key}")
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
    visual_analysis = load_json_for_prompt(extracted_dir / "visual_analysis.json")
    if not json.loads(visual_analysis).get("complete"):
        raise RuntimeError("Complete visual analysis is required before drafting report sections.")
    visual_plan = load_json_for_prompt(extracted_dir / "visual_plan.json")
    if not json.loads(visual_plan).get("complete"):
        raise RuntimeError("A complete global visual plan is required before drafting report sections.")
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
        f"报告语言：{language}。保留 What/Why/How/Experiment/Question 叙述路线。"
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
- 使用标题 `{stage.heading}`；其他报告语言保留序号及 What/Why/How/Experiment/Question 并翻译说明。
- 只输出一个二级章节；可少量使用三级标题，不重复前文。
- 行内公式使用 $...$，行间公式使用独占行的 $$ 包裹，禁止其他数学定界符。
- 执行全局选图计划，本阶段所有 include=true 图表必须在指定章节展示并讲解，不能因压缩篇幅再次删除；include=false 图表不插入。
- How 按去重后的技术路线图组织讲解：总流程→局部机制→训练与推理，图前指明阅读重点，图后解释关键部件和设计理由。互补图不当成冗余。
- Experiment 按计划中核心贡献的证明链自主组织图表和文字，明确比较条件、结果与边界；不凑图数，不重复同一图表。
- 抽取遗漏或图像不可读时明确证据限制；不能自行截图或裁剪，不能编造数值。
- 独立评价需标注“我的判断”或 `(Inference from ...)`，不可冒充作者结论。
- 重要判断必须带 evidence marker，例如 `(Evidence: Page 3, Fig. 2)`。
- 如果使用图片，必须引用 Figure And Table Manifest 中的 `image` 路径，例如 `![Figure 2](extracted/figures/source-Figure2-1.png)`。
- 不要编造没有证据的作者、年份、实验结果或公式。

# Skill Excerpt
{build_skill_prompt()}

# Previous Generated Sections
```markdown
{prior}
```

# Paper Index
```json
{paper_index[:20000]}
```

# All Visual Analyses (completed before writing)
{visual_analysis}

# Global Visual Plan
{visual_plan}

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
