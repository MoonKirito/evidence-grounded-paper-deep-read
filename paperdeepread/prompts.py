from __future__ import annotations

import json
from pathlib import Path

from paperdeepread.providers.base import ChatMessage
from paperdeepread.utils import SKILL_DIR, read_text


def build_skill_prompt(max_chars: int | None = None) -> str:
    parts = [
        "# Skill Instructions",
        read_text(SKILL_DIR / "SKILL.md"),
        "# Report Schema",
        read_text(SKILL_DIR / "references" / "report_schema.md"),
        "# Reading Protocol",
        read_text(SKILL_DIR / "references" / "reading_protocol.md"),
        "# Figure Analysis Protocol",
        read_text(SKILL_DIR / "references" / "figure_analysis_protocol.md"),
        "# Quality Checklist",
        read_text(SKILL_DIR / "references" / "quality_checklist.md"),
        "# Terminology Explanation Protocol",
        read_text(SKILL_DIR / "references" / "terminology_explanation.md"),
    ]
    prompt = "\n\n".join(parts)
    if max_chars is not None and len(prompt) > max_chars:
        return prompt[:max_chars] + "\n\n[TRUNCATED SKILL PROMPT]\n"
    return prompt


def load_json_for_prompt(path: Path) -> str:
    if not path.exists():
        return "{}"
    data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    return json.dumps(data, ensure_ascii=False, indent=2)


def build_visual_inventory(extracted_dir: Path) -> str:
    manifest_path = extracted_dir / "figure_manifest.json"
    if not manifest_path.exists():
        return "未找到可用图表。"
    data = json.loads(manifest_path.read_text(encoding="utf-8-sig", errors="replace"))
    items = data.get("items", [])
    lines = []
    for item in items:
        image = item.get("image") or ""
        if not image:
            continue
        caption = " ".join(str(item.get("caption", "")).split())
        if len(caption) > 280:
            caption = caption[:280] + "..."
        lines.append(
            f"- {item.get('figType', 'Figure')} {item.get('name', '')}: "
            f"`{image}`; page={item.get('page', '')}; caption={caption}"
        )
    if not lines:
        return "figure_manifest 中没有可引用的精确图表路径。"
    return (
        "下面是 pdffigures2 提取的图表。How 去重后覆盖技术路线图；Experiment 按核心贡献证明链选择，最终执行全局选图计划。\n"
        + "\n".join(lines)
    )


def build_report_messages(
    *,
    title: str,
    pdf_name: str,
    extracted_dir: Path,
    paper_index_path: Path,
    language: str,
    max_input_chars: int,
) -> list[ChatMessage]:
    full_text = read_text(extracted_dir / "full_text.md", limit=max_input_chars)
    paper_index = read_text(paper_index_path, limit=30000) if paper_index_path.exists() else "{}"
    figure_manifest = load_json_for_prompt(extracted_dir / "figure_manifest.json")
    visual_inventory = build_visual_inventory(extracted_dir)
    visual_analysis = load_json_for_prompt(extracted_dir / "visual_analysis.json")
    if not json.loads(visual_analysis).get("complete"):
        raise RuntimeError("Complete visual analysis is required before drafting the report.")
    visual_plan = load_json_for_prompt(extracted_dir / "visual_plan.json")
    if not json.loads(visual_plan).get("complete"):
        raise RuntimeError("A complete global visual plan is required before drafting the report.")
    skill_prompt = build_skill_prompt()

    system = (
        "你是一名严谨的论文精读助手，必须使用用户提供的 skill 规范生成 Markdown 报告。"
        "报告正文语言必须保持一致；使用 What/Why/How/Experiment/Question 五节叙述路线。"
        "不要编造论文中没有的信息；无法确认时明确说明证据不足。"
        "请直接输出最终 Markdown 报告，不要输出思考过程；内部推理尽量简短，把输出预算留给报告正文。"
    )

    user = f"""
请根据下面材料生成一篇证据驱动的五节论文精读报告，正文建议 2800–4200 中文字，How 建议 1200–2000 字，复杂方法可扩展。

输出要求：
- 输出格式只能是 Markdown。
- 报告语言：{language}。
- 论文标题或文件名：{title}
- PDF 文件名：{pdf_name}
- 需要把图和表融入“作者做了什么、为什么做、具体怎么做、如何验证”等对应正文段落，不要单独开“图表精读”章节。
- 引用图片时使用 figure_manifest 中的相对路径，Markdown 写法必须是 `![Figure 1](extracted/figures/xxx.png)`。
- 执行全局选图计划，所有 include=true 图表必须在指定章节展示讲解，不能再次以简洁为由删除；include=false 图表不插入。
- How 去重后尽量展示全部技术路线图，结合总览和局部机制，详细说明各模块的输入、内部操作、输出、设计理由与衔接；图前说明阅读重点，图后解释关键技术。
- Experiment 按核心贡献组织证明链，自主选择和讲解实验图表，不凑数量。
- 不能引用整页预览，也不能自行截图或裁剪。提取遗漏时明确说明证据限制。
- 行内公式使用 $...$，行间公式使用独占行的 $$ 包裹。
- 对每个关键创新点都要解释作者思路、具体做法、相关公式或技术细节、证据位置。
- 对公式、术语和实验指标要面向初学者解释。
- 每个重要结论都要给出 evidence marker，例如 `(Evidence: Sec. 3, Fig. 2)`。

{skill_prompt}

# Candidate Visual Inventory
{visual_inventory}

# Paper Index
```json
{paper_index}
```

# All Visual Analyses
{visual_analysis}

# Global Visual Plan
{visual_plan}

# Figure And Table Manifest
```json
{figure_manifest}
```

# Extracted Paper Text
```markdown
{full_text}
```
""".strip()

    return [ChatMessage(role="system", content=system), ChatMessage(role="user", content=user)]
