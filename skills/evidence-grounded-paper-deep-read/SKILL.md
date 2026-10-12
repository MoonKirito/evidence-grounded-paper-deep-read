---
name: evidence-grounded-paper-deep-read
description: Generate concise, evidence-grounded Markdown reports for one or more research PDFs, using a what/why/how/experiment/question narrative and analyzing all pdffigures2 figures and tables before writing.
---

# Evidence-Grounded Paper Deep Read

每篇 PDF 输出一份独立的 `report.md`，用 What → Why → How → Experiment → Question 将论文串成一条论证路线。默认使用用户语言，中文正文建议 2800–4200 字，How 建议 1200–2000 字；复杂方法可适度超出，优先保留理解主张所必需的技术内容。

## 工作流

1. 为每篇论文建立独立目录，保留 `source.pdf`，提取带页码和段落 ID 的正文。
2. **先使用 pdffigures2 提取全部图和表**，保留原始元数据及 `figure_manifest.json`。不得自行截图、使用其他工具裁剪，或把整页预览作为报告插图。未提取成功的图表记录为不可用；可据图注与正文作有限分析，但不能假装已经看过图片。
3. 建立论文索引，通读主张、动机、方法、实验与局限。核对全文中的图表引用和提取清单，记录可能漏提取的图表；无法确认的引用不能当成已提取图表。
4. **写报告之前分析所有图和表**：查看图片，结合图注及引用正文，理解结构/坐标/行列/指标、关键观察、支持的主张和证明边界。保存 `extracted/visual_analysis.json`，逐项记录分析、证据、可读性，以及建议放入哪一节或不插入的理由。无法看图时明确说明能力限制，不能用图注冒充视觉分析。
5. 完成全局 `extracted/visual_plan.json`：How 中技术路线与机制图去重后尽量全部展示，互补总览/局部图不视为重复；实验图按核心贡献证明链选择。逐项保存选择或省略理由、重复代表和信息覆盖，核心贡献另记录图表/文字呈现理由。然后依据 `references/report_schema.md` 和 `references/reading_protocol.md` 写五节正文。以核心贡献及其证明链为主线，图表、公式、术语在相关技术或实验处解释，不设单独的公式、创新点、背景补充或自检章节。
6. 执行全局计划，在指定章节展示并讲解所有 include=true 图表，不因压缩篇幅再次删除；不插入 include=false 图表。How 详细解释图中的技术步骤、输入输出和设计理由；实验图阐明支持的主张与证明边界。图表不凑数量。
7. 按 `references/quality_checklist.md` 复核，运行 `scripts/validate_report.py`；检查过程留在工作文件，不追加到报告正文。

## 输出约定

```text
paper-output/
  source.pdf
  report.md
  paper_index.json
  extracted/
    full_text.md
    sections.json
    figure_manifest.json
    visual_analysis.json
    visual_plan.json
    figures/
  stages/                     # CLI 断点续写五个正文阶段
```

重要事实须有真实页码、章节、图表号、公式号或段落锚点，例如 `(Evidence: Sec. 3.2, Fig. 2)`。区分作者结论、实验观察与自己的推断；评价写明依据及可补充验证的方向。

行内公式用 `$...$`，行间公式用独占行的 `$$` 包裹。不能用其他数学定界符、代码块或反引号代替。无法可靠提取的公式应说明限制，不凭空补写。

## 工具与参考

- CLI `python -m paperdeepread run` 完成批量处理，必须配置 pdffigures2 jar；支持多 provider（详见项目 `docs/providers.md`），可用 `[vision]` 独立设置看图模型。图表预读需要多模态能力，兼容接口使用 `image_url`，Claude/Gemini 使用原生图像格式；不支持看图时应停止并报告。
- `scripts/extract_pdf_text.py`：正文及页码/段落锚点。
- `scripts/build_paper_index.py`：论文索引脚手架，需要阅读后核实，不能当成自动理解结果。
- `scripts/make_report_scaffold.py`：从 `assets/report_template.md` 建立报告目录。
- `scripts/validate_report.py`：结构、数学定界符、图片来源/路径、方法去重与全局选图章节覆盖等本地检查。
- 图表预读细则见 `references/figure_analysis_protocol.md`；必要术语及公式的就地解释见 `references/terminology_explanation.md`。

图表提取只使用 pdffigures2；不使用 embedded-image、page-preview 或自行裁剪补图。
