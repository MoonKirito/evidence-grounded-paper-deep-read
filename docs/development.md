# Development and release checks

## Install and test

```sh
python -m pip install -e .
python -m unittest discover -s tests -v
python -m paperdeepread --help
python -m paperdeepread list-providers
```

The tests use mocked model responses; they do not require API keys or paid calls. Java/pdffigures2 and a vision-capable endpoint are needed for a real PDF run. Preserve the generated workspace if a request fails; successful visual analyses and stages can be resumed.

## Validate a report

From a source checkout:

```sh
python skills/evidence-grounded-paper-deep-read/scripts/validate_report.py reports/<paper-name>/report.md
```

The validator checks five-section order, evidence markers, math delimiters, image provenance, global-plan coverage and method deduplication. It cannot decide whether a scientific claim, explanation or selection rationale is correct; review these against the source paper.

## Build

```sh
python -m pip install build
python -m build
```

Both source archives and wheels include the required skill instructions, references, template and scripts. A normal wheel installation finds these under `share/paperdeepread/skill` in the Python environment. The public repository keeps a single editable skill source under `skills/`.

## Before pushing

```sh
git status --short
git diff --check
python -m unittest discover -s tests -v
```

Inspect the files you intend to commit. `.gitignore` excludes local PDFs, reports, `.paperdeepread.toml`, `.paperdeepread.*.toml` (except the example), `.env` files, jars, tool caches and `.local/` archives. Ignoring does not remove an already tracked file or clean Git history.

Keep API keys in environment variables. The public example uses only environment-variable names and placeholders. Do not include generated private reports, local service credentials or downloaded dependency trees in a release. No workflow calls a real model automatically during tests.

Historical local scripts and screenshots may be retained under `.local/archive/`; they are outside the maintained/public workflow.
