# 证据驱动论文精读报告工具

[English](README.md) | [中文](README.zh-CN.md)

Evidence-Grounded Paper Deep Read 是一个 **Codex skill + CLI 工作流**，用于把研究论文 PDF 转换成详细、证据驱动的 Markdown 精读报告。

这个项目不是为了生成宽泛摘要，而是让模型围绕“作者做了什么、为什么做、具体怎么做、如何验证”进行细粒度讲解，并把公式、图表、实验指标、专业术语和创新点放回论文证据中解释。

## 效果预览

生成结果是 Markdown 文件，可以直接用 Markdown 编辑器阅读，也可以进入飞书 CLI 等文档工作流。

![报告预览 1](images/report1.1.png)

![报告预览 2](images/report1.2.png)

![报告预览 3](images/report1.3.png)

## 功能特点

- 每篇 PDF 生成一份 Markdown 精读报告。
- 内置可复用 Codex skill：`skills/evidence-grounded-paper-deep-read/`。
- 自动抽取正文、段落锚点、图表元数据。
- 基于 [allenai/pdffigures2](https://github.com/allenai/pdffigures2) 从 PDF 中抽取精确裁剪的 figure/table。
- 使用 `sectioned` 多阶段生成策略，而不是一次性把整篇论文塞给模型。
- 把图表融入“作者做了什么、为什么做、具体怎么做、如何验证”等对应段落，而不是单独开图表附录。
- 提供报告验证器，检查章节、图片引用、证据标记、语言混用和泛化表述。
- 可以导出 skill prompt 给其他模型或智能体单独使用。

## 工作流

```text
PDF 文件夹
  -> 文本抽取
  -> pdffigures2 图表抽取
  -> 论文索引和图表 manifest
  -> 分阶段 evidence pack
  -> MiMo OpenAI-compatible Chat API
  -> Markdown 精读报告
  -> 本地验证器
```

默认 `sectioned` 生成模式会分阶段生成：

1. 论文基本信息和一句话总览。
2. 作者做了什么、为什么做。
3. 方法、公式和关键技术细节。
4. 实验、baseline、指标和结果。
5. 创新点、局限性、初学者背景、复现建议。
6. 完整性自检。

这种方式比固定截断整篇论文更适合不同长度、不同结构的论文。

## 项目结构

```text
.
├─ paperdeepread/                         # Python CLI 包
│  ├─ cli.py                              # CLI 命令
│  ├─ pipeline.py                         # PDF 到报告的主流程
│  ├─ evidence_pack.py                    # 分阶段证据选择
│  ├─ sectioned.py                        # 多阶段报告组装
│  └─ providers/mimo.py                   # 小米 MiMo provider
├─ skills/
│  └─ evidence-grounded-paper-deep-read/  # 可复用 Codex skill
│     ├─ SKILL.md
│     ├─ agents/openai.yaml
│     ├─ references/
│     ├─ scripts/
│     └─ assets/report_template.md
├─ scripts/
│  └─ run_pdffigures2.ps1                 # pdffigures2 辅助脚本
├─ workflows/
│  └─ pdffigures2.md                      # pdffigures2 构建与验证说明
├─ images/                                # README 示例图
├─ tests/                                 # 单元测试
├─ .paperdeepread.example.toml            # 示例配置
├─ requirements.txt
└─ pyproject.toml
```

## 环境要求

- Python 3.10+
- Java runtime，用于运行 `pdffigures2`
- 已构建好的 `pdffigures2.jar`
- 小米 MiMo API key

本项目使用 AllenAI 的 [pdffigures2](https://github.com/allenai/pdffigures2) 进行论文 figure/table 抽取。构建和验证说明见 [workflows/pdffigures2.md](workflows/pdffigures2.md)。

## 安装

```bash
git clone <your-repo-url>
cd evidence-grounded-paper-deep-read
python -m venv .venv
python -m pip install -r requirements.txt
python -m pip install -e .
```

激活虚拟环境：

macOS/Linux:

```bash
source .venv/bin/activate
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

安装后可以使用：

```bash
python -m paperdeepread --help
paperdeepread --help
```

## 准备 pdffigures2

克隆或下载 [allenai/pdffigures2](https://github.com/allenai/pdffigures2)，构建 jar，并在运行 CLI 时传入 jar 路径。

常见本地布局：

```text
evidence-grounded-paper-deep-read/
  pdffigures2/
    pdffigures2.jar
```

本地测试经验：

- JDK 17 可稳定构建和运行。
- 很新的 JDK 可能和旧版 Scala/SBT 栈不兼容。
- CLI 通过 `--pdffigures2-jar` 接收任意 jar 路径。

## 配置大模型

生成配置文件：

```bash
python -m paperdeepread init-config
```

默认 provider 是小米 MiMo：

```toml
[llm]
provider = "mimo"
base_url = "https://token-plan-cn.xiaomimimo.com/v1"
model = "mimo-v2.5-pro"
api_key_env = "MIMO_API_KEY"
temperature = 0.2
max_tokens = 24000
timeout_seconds = 900
stream = true
```

在 shell 中配置 API key。

macOS/Linux:

```bash
export MIMO_API_KEY="your_key"
```

Windows PowerShell:

```powershell
$env:MIMO_API_KEY="your_key"
```

## 生成精读报告

把论文 PDF 放到输入目录：

```text
paper/
  paper-1.pdf
  paper-2.pdf
```

运行：

```powershell
python -m paperdeepread run `
  --input paper `
  --output reports `
  --config .paperdeepread.toml `
  --pdffigures2-jar .\pdffigures2\pdffigures2.jar `
  --java-path java
```

如果使用本地 JDK 17：

```powershell
python -m paperdeepread run `
  --input paper `
  --output reports `
  --config .paperdeepread.toml `
  --pdffigures2-jar .\pdffigures2\pdffigures2.jar `
  --java-path .\.tmp\tools\jdk17\jdk-17.0.19+10\bin\java.exe
```

输出结构：

```text
reports/
  paper-slug/
    source.pdf
    report.md
    paper_index.json
    stages/
      overview_metadata.md
      what_why.md
      how_formula.md
      experiment.md
      innovation_limits_background.md
      checklist.md
    extracted/
      full_text.md
      sections.json
      figure_manifest.json
      figures/
        source-Figure1-1.png
```

## 配合飞书 CLI

最终精读报告是标准 Markdown。你可以把 `report.md` 接入自己的飞书 CLI Markdown 导入/同步流程，用来生成飞书文档、知识库页面或团队阅读笔记。

常见流程是：

```text
论文 PDF -> paperdeepread report.md -> 飞书 CLI Markdown 导入/同步 -> 飞书协作文档
```

## 单独复用 Skill

可复用 skill 位于：

```text
skills/evidence-grounded-paper-deep-read/
```

你可以让 Codex 或其他兼容智能体直接读取这个目录，使用其中的 `SKILL.md`、`references/`、`scripts/` 和模板资源。

也可以导出组合 prompt：

```bash
python -m paperdeepread export-skill-prompt --out skill_prompt.md
```

## 验证报告

```bash
python skills/evidence-grounded-paper-deep-read/scripts/validate_report.py reports/paper-slug/report.md
```

验证器会检查章节完整性、Markdown 图片引用、证据标记、结构标题语言混用、整页 preview 引用和泛化表述。

## 运行测试

```bash
python -m unittest discover -s tests -v
```

## 许可证

MIT License. See [LICENSE](LICENSE).
