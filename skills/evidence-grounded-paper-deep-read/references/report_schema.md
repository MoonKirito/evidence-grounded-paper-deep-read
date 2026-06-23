# Report Schema

Use this schema for the final Markdown report. Keep the user's requested language for all structural text. For Chinese reports, do not use English headings such as `WHAT`, `WHY`, `HOW`, `EXPERIMENT`, `Paper Metadata`, or `Figure And Table Deep Reading`.

```markdown
# 论文精读报告：<title>

## 0. 一句话总览

## 1. 论文基本信息

| 项目 | 内容 |
|---|---|
| 标题 |  |
| 作者 |  |
| 发表信息 |  |
| PDF 文件 |  |
| 主题 |  |
| 报告语言 |  |

## 2. 作者做了什么
### 2.1 核心任务
### 2.2 主要贡献
### 2.3 相比已有工作的不同

## 3. 作者为什么要做这件事
### 3.1 背景问题
### 3.2 现有方法的不足
### 3.3 作者的动机
### 3.4 这个问题为什么重要

## 4. 作者具体怎么做
### 4.1 方法总览
### 4.2 流程逐步拆解
### 4.3 模块级细读
### 4.4 训练、优化或参数设置
### 4.5 推理或使用流程
### 4.6 实现细节

## 5. 作者如何验证
### 5.1 实验要回答的问题
### 5.2 数据集
### 5.3 评价指标
### 5.4 对比方法
### 5.5 主要结果
### 5.6 消融实验
### 5.7 额外分析
### 5.8 实验证明了什么
### 5.9 实验没有证明什么

## 6. 公式与关键技术细节

## 7. 创新点逐条拆解

## 8. 局限性与开放问题

## 9. 初学者背景补充

## 10. 复现与进一步阅读建议

## 11. 完整性自检
```

## Detail Requirements

Avoid short generic paragraphs in sections 2-7. Use subsections liberally when the paper has multiple modules, experiments, or claims.

Do not create a standalone figure/table section. Embed cropped figures and tables directly into the relevant subsection about the task, motivation, method, or experiment, and explain them as part of the argument.

Use tables only when they improve clarity. For method explanations, prefer prose plus numbered steps.

Every method module should include:

- Purpose.
- Input.
- Output.
- Internal procedure.
- Related formula or cropped figure/table.
- Design rationale.
- Evidence location.

Every experiment should include:

- Hypothesis.
- Setup.
- Result.
- Interpretation.
- Evidence location.

## Evidence Markers

Use compact evidence markers inside prose:

```markdown
(Evidence: Sec. 3.2, Fig. 2)
(Evidence: p. 7, Table 1)
(Inference from Sec. 4.1 and Table 3)
```

If page or section information is unavailable, cite the nearest reliable anchor, such as figure number, table number, equation number, or extracted paragraph number.
