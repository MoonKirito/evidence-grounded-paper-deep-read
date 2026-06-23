from __future__ import annotations

import json
from pathlib import Path

from paperdeepread.providers.mimo import ChatMessage
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
    required_count = min(6, len(lines))
    return (
        f"下面是 pdffigures2 抽取出的精确图表。报告必须至少嵌入 {required_count} 张/个相关图表，"
        "优先覆盖方法结构图、核心结果表、消融表和关键可视化结果；不要使用整页 preview。\n"
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
    skill_prompt = build_skill_prompt(max_chars=50000)

    system = (
        "你是一名严谨的论文精读助手，必须使用用户提供的 skill 规范生成 Markdown 报告。"
        "报告正文语言必须保持一致；当报告语言为中文时，结构标题也必须是中文，不能使用 WHAT/WHY/HOW/EXPERIMENT 作为标题。"
        "不要编造论文中没有的信息；无法确认时明确说明证据不足。"
        "请直接输出最终 Markdown 报告，不要输出思考过程；内部推理尽量简短，把输出预算留给报告正文。"
    )

    user = f"""
请根据下面材料生成一篇完整、细致、证据驱动的论文精读报告。

输出要求：
- 输出格式只能是 Markdown。
- 报告语言：{language}。
- 论文标题或文件名：{title}
- PDF 文件名：{pdf_name}
- 需要把图和表融入“作者做了什么、为什么做、具体怎么做、如何验证”等对应正文段落，不要单独开“图表精读”章节。
- 引用图片时使用 figure_manifest 中的相对路径，Markdown 写法必须是 `![Figure 1](extracted/figures/xxx.png)`。
- 如果下面“Required Visual Inventory”列出了可用图表，报告正文必须实际插入这些相对路径对应的 Markdown 图片；不能只在文字中提到图号。
- 不要引用 `page-001-preview.png` 这类整页预览图，除非明确标记为未解决的抽图限制。
- 对每个关键创新点都要解释作者思路、具体做法、相关公式或技术细节、证据位置。
- 对公式、术语和实验指标要面向初学者解释。
- 每个重要结论都要给出 evidence marker，例如 `(Evidence: Sec. 3, Fig. 2)`。

{skill_prompt}

# Required Visual Inventory
{visual_inventory}

# Paper Index
```json
{paper_index}
```

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
