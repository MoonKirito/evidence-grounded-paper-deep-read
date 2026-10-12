# Evidence-Grounded Paper Deep Read

English | [中文](README.zh-CN.md)

Turn one or more research PDFs into evidence-grounded Markdown reports, one report per paper. The narrative follows **What → Why → How → Experiment → Question**: contributions, motivation, technical pipeline, experimental proof and independent assessment.

- Extract figures/tables with **pdffigures2**, then analyze every actual image with its caption and paper context before writing.
- Plan visual coverage globally: retain complementary method diagrams, remove redundant information, and select representative experimental evidence.
- Explain module inputs, operations, outputs and design rationale in How, including training versus inference.
- Use `$...$` for inline math and standalone `$$` lines for display math; explain visuals where they support the argument.
- Support multiple providers, a separate vision model, resumable stages and report/visual-coverage validation.

Chinese reports aim for 2800–4200 characters, including 1200–2000 in How. Complex methods may need more detail.

## Quick start

Requirements: Python 3.10+, Java, a built pdffigures2 jar and an API key for a suitable text/vision model.

```powershell
git clone https://github.com/MoonKirito/evidence-grounded-paper-deep-read.git
cd evidence-grounded-paper-deep-read
python -m pip install -e .
python -m paperdeepread init-config --provider openai --model gpt-4.1
$env:OPENAI_API_KEY="your-key"
```

On Linux/macOS, use `export OPENAI_API_KEY="your-key"`. Choose an actual model ID available to your account. Override the endpoint in the config when needed. Running `init-config` without arguments retains the original MiMo defaults.

Place PDFs in `paper/`, then supply your jar:

```powershell
python -m paperdeepread run --input paper --output reports --pdffigures2-jar /path/to/pdffigures2.jar
```

Alternatively set `jar_path` and `java_path` under `[pdffigures2]` in `.paperdeepread.toml`. See [pdffigures2 setup](docs/pdffigures2.md).

## Configuration and output

[Provider configuration](docs/providers.md) covers OpenAI, Claude, Gemini, DeepSeek, Qwen, Kimi, GLM, Doubao, MiniMax, Grok, MiMo, OpenRouter, SiliconFlow and custom compatible gateways. `list-providers` lists endpoint/key defaults. An optional `[vision]` section selects a separate image-reading model.

```text
reports/<paper-name>/
  report.md                    # Final five-part report
  source.pdf
  paper_index.json
  extracted/
    full_text.md
    sections.json
    figure_manifest.json       # pdffigures2 inventory
    visual_analysis.json       # All-visual pre-reading
    visual_plan.json           # Selection, deduplication, claim coverage
    figures/
  stages/                      # Resumable report stages
```

The default `sectioned` mode writes one section at a time. `one_shot` also requires visual pre-reading and a global plan. Important facts cite paper anchors; inferences are distinguished from author claims. Extraction can miss visuals, so possible misses are recorded rather than recovered through custom screenshots. Validation cannot replace scientific fact-checking.

## Standalone skill and development

The reusable [paper-reading skill](skills/evidence-grounded-paper-deep-read/SKILL.md) contains instructions, a report template and standalone helpers.

```powershell
python -m paperdeepread export-skill-prompt --out skill_prompt.md
python -m unittest discover -s tests -v
```

See [development and release checks](docs/development.md). Dependencies have one source of truth in `pyproject.toml`; install `python -m pip install -e ".[fallback]"` if you need the optional pdfplumber extraction backend.

## Layout

```text
paperdeepread/    CLI, providers, evidence selection and report generation
skills/          Standalone paper-reading skill
docs/           Provider, pdffigures2 and development guides
tests/          Protocol, workflow and visual-coverage tests
```

Local papers, reports, key configs, downloaded dependencies and temporary files are excluded by `.gitignore`. Licensed under [MIT](LICENSE).
