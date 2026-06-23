# Quality Checklist

Run this checklist before final delivery.

## Required Sections

- Title and metadata are filled.
- Structural language is consistent: headings, table headers, image captions, and checklist labels match the report language.
- The task section explains the exact work, not only the topic.
- The motivation section explains background, gap, and motivation.
- The method section explains pipeline, modules, formulas, and implementation.
- The experiment section explains setup, baselines, metrics, and results.
- Major visuals are precise crops, not full-page previews.
- Crop manifests record bbox, margin, and verification status; visuals marked `needs_review` are not used until visually checked or recropped.
- Figures and tables are integrated into the task, motivation, method, or experiment sections where they support the argument.
- Formula section explains important equations and symbols.
- Innovation section decomposes every contribution.
- Limitations are distinguished from agent speculation.
- Beginner notes define specialized terms.
- Reproduction notes identify code/data/config requirements if available.

## Weak Writing Patterns To Remove

Replace these with concrete detail:

- "The method improves performance."
- "The authors propose a novel framework."
- "The experiment proves effectiveness."
- "This module extracts useful features."
- "The results are significant."
- "The figure shows the overall architecture."
- "图中展示了整体框架。"
- "该图说明了方法有效。"

For every such sentence, add what, how, where, compared with what, and supported by which evidence.

## Evidence Audit

For each major claim, verify:

- There is an evidence marker.
- The evidence marker points to a real paper location.
- The claim does not exceed what the evidence supports.
- Inferences are labeled as inferences.

## Completeness Table

End the report with a table like:

```markdown
| Check Item | Status | Notes |
|---|---|---|
| Task section is detailed | Complete/Partial/Missing |  |
| Motivation section is detailed | Complete/Partial/Missing |  |
| Method section is module-level | Complete/Partial/Missing |  |
| Experiments are fully analyzed | Complete/Partial/Missing |  |
| Major figures/tables are explained | Complete/Partial/Missing |  |
| Key formulas are explained | Complete/Partial/Missing |  |
| Beginner terminology is covered | Complete/Partial/Missing |  |
| Evidence markers are present | Complete/Partial/Missing |  |
| Report language is consistent | Complete/Partial/Missing |  |
| Figures are cropped and integrated into logic | Complete/Partial/Missing |  |
```

For Chinese reports, localize the completeness table:

```markdown
| 检查项 | 状态 | 说明 |
|---|---|---|
| 作者做了什么是否具体 | 完成/部分/缺失 |  |
| 为什么做是否具体 | 完成/部分/缺失 |  |
| 方法是否到模块级 | 完成/部分/缺失 |  |
| 实验是否完整分析 | 完成/部分/缺失 |  |
| 主要图表是否精确裁剪并融入正文 | 完成/部分/缺失 |  |
| 关键公式是否解释 | 完成/部分/缺失 |  |
| 初学者术语是否补充 | 完成/部分/缺失 |  |
| 关键结论是否有证据标记 | 完成/部分/缺失 |  |
| 结构语言是否一致 | 完成/部分/缺失 |  |
```
