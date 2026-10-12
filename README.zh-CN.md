# Evidence-Grounded Paper Deep Read

[English](README.md) | 中文

将一篇或多篇论文 PDF 转换为证据驱动的 Markdown 精读报告。每篇论文独立输出，按 **What → Why → How → Experiment → Question** 串起贡献、动机、技术路线、实验证明链和独立评价。

- 写作前使用 **pdffigures2** 提取图表，再结合实际图片、图注和正文逐项分析。
- 全局选图计划保留互补方法图、去除重复信息；实验图按核心贡献精选。
- How 详细解释模块输入输出、内部步骤、设计理由，以及训练与推理的区别。
- 行内公式使用 `$...$`，行间公式使用 `$$`；图表在对应段落展示讲解。
- 支持多 provider、独立看图模型、断点续写及格式/图表覆盖验证。

中文正文建议 2800–4200 字，How 建议 1200–2000 字；复杂方法按实际需要扩展。

## 快速开始

需要 Python 3.10+、Java 和已构建的 pdffigures2 jar，以及具有相应文本/视觉能力的模型 API key。

```powershell
git clone https://github.com/MoonKirito/evidence-grounded-paper-deep-read.git
cd evidence-grounded-paper-deep-read
python -m pip install -e .
python -m paperdeepread init-config --provider openai --model gpt-4.1
$env:OPENAI_API_KEY="your-key"
```

Linux/macOS 用 `export OPENAI_API_KEY="your-key"` 设置环境变量。模型 ID 可替换为平台实际支持的模型；默认接口可在配置中覆盖。MiMo 用户可直接运行 `init-config` 使用原有默认值。

将 PDF 放入 `paper/`，并提供 jar 路径：

```powershell
python -m paperdeepread run --input paper --output reports --pdffigures2-jar /path/to/pdffigures2.jar
```

也可在 `.paperdeepread.toml` 的 `[pdffigures2]` 中设置 `jar_path` 和 `java_path`。准备 jar 的方式见 [pdffigures2](docs/pdffigures2.md)。

## 配置与输出

[Provider 配置](docs/providers.md) 包含 OpenAI、Claude、Gemini、DeepSeek、Qwen、Kimi、GLM、豆包、MiniMax、Grok、MiMo、OpenRouter、SiliconFlow 和自定义兼容网关的说明。使用 `list-providers` 查看默认地址与 key 环境变量；可通过 `[vision]` 单独设置看图模型。

```text
reports/<paper-name>/
  report.md                    # 最终五节报告
  source.pdf                   # 原始论文
  paper_index.json             # 章节与证据索引
  extracted/
    full_text.md
    sections.json
    figure_manifest.json       # pdffigures2 图表清单
    visual_analysis.json       # 全量图表预读
    visual_plan.json           # 选择、去重和贡献覆盖理由
    figures/
  stages/                      # 正文断点缓存
```

`sectioned` 为默认模式，逐节生成；`one_shot` 同样先完成图表分析和全局计划。重要事实有页码/章节/图表等证据定位，推断与作者结论分开。pdffigures2 可能漏提取，工作文件会记录可能的遗漏；不自行截图补图。程序验证不能代替原文事实核对。

## 独立 Skill 与开发

可复用 skill 位于 [skills/evidence-grounded-paper-deep-read](skills/evidence-grounded-paper-deep-read/SKILL.md)，包含阅读规范、报告模板和独立脚本。也可导出组合提示词：

```powershell
python -m paperdeepread export-skill-prompt --out skill_prompt.md
python -m unittest discover -s tests -v
```

开发、验证与发布检查见 [开发说明](docs/development.md)。依赖仅在 `pyproject.toml` 维护；如需备用文本提取后端，可安装 `python -m pip install -e ".[fallback]"`。

## 仓库结构

```text
paperdeepread/    CLI、provider、证据选择及报告生成
skills/          可独立使用的论文精读 skill
docs/           provider、pdffigures2 和开发说明
tests/          协议、工作流及图表覆盖测试
```

本地论文、报告、key 配置、下载依赖与临时文件均由 `.gitignore` 排除。MIT 许可证见 [LICENSE](LICENSE)。
