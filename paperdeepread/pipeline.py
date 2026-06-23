from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

try:
    from tqdm import tqdm
except ImportError:  # pragma: no cover
    tqdm = None  # type: ignore

from paperdeepread.config import AppConfig
from paperdeepread.prompts import build_report_messages
from paperdeepread.providers.mimo import MimoClient
from paperdeepread.sectioned import REPORT_STAGES, assemble_sectioned_report, build_stage_messages
from paperdeepread.utils import REPO_ROOT, SKILL_DIR, require_success, run_python_script, slugify


@dataclass(frozen=True)
class RunOptions:
    input_dir: Path
    output_dir: Path
    config: AppConfig
    pdffigures2_jar: Path | None
    java_path: str | None
    limit: int | None = None


def discover_pdfs(input_dir: Path, limit: int | None = None) -> list[Path]:
    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")
    pdfs = sorted(path for path in input_dir.iterdir() if path.is_file() and path.suffix.lower() == ".pdf")
    return pdfs[:limit] if limit else pdfs


def progress(iterable: list[Path]):
    if tqdm is None:
        return iterable
    return tqdm(iterable, desc="papers", unit="paper")


def stage(message: str) -> None:
    if tqdm is not None:
        tqdm.write(message)
    else:
        print(message)


def run_pdffigures2(pdf: Path, work_dir: Path, jar_path: Path, java_path: str) -> None:
    extracted_dir = work_dir / "extracted"
    figures_dir = extracted_dir / "figures"
    data_dir = extracted_dir / "pdffigures2-data"
    input_dir = work_dir / ".pdffigures2-input"
    input_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    pdffig_pdf = input_dir / f"{slugify(pdf.stem)}.pdf"
    if pdf.resolve() != pdffig_pdf.resolve():
        shutil.copy2(pdf, pdffig_pdf)

    stats_path = extracted_dir / "pdffigures2-stats.json"
    command = [
        java_path,
        "-Dsun.java2d.cmm=sun.java2d.cmm.kcms.KcmsServiceProvider",
        "-jar",
        str(jar_path),
        str(input_dir),
        "-s",
        str(stats_path),
        "-m",
        str(figures_dir) + os.sep,
        "-d",
        str(data_dir) + os.sep,
    ]
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    require_success(result, "pdffigures2 extraction")
    write_figure_manifest(extracted_dir, data_dir, figures_dir)


def write_figure_manifest(extracted_dir: Path, data_dir: Path, figures_dir: Path) -> None:
    items = []
    for json_path in sorted(data_dir.glob("*.json")):
        data = json.loads(json_path.read_text(encoding="utf-8", errors="replace"))
        for item in data:
            render_url = item.get("renderURL") or item.get("renderUrl") or ""
            image_name = Path(str(render_url)).name if render_url else ""
            image_path = figures_dir / image_name if image_name else None
            rel_path = image_path.relative_to(extracted_dir.parent).as_posix() if image_path and image_path.exists() else ""
            items.append(
                {
                    "name": item.get("name", ""),
                    "figType": item.get("figType", ""),
                    "page": item.get("page", None),
                    "caption": item.get("caption", ""),
                    "image": rel_path,
                    "regionBoundary": item.get("regionBoundary", {}),
                    "captionBoundary": item.get("captionBoundary", {}),
                }
            )
    def sort_key(item: dict) -> tuple[int, str]:
        name = str(item.get("name", ""))
        digits = "".join(ch for ch in name if ch.isdigit())
        numeric = int(digits) if digits else 10_000
        return numeric, name

    manifest = {"source": "pdffigures2", "items": sorted(items, key=sort_key)}
    (extracted_dir / "figure_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def prepare_workspace(pdf: Path, output_dir: Path, language: str) -> Path:
    work_dir = output_dir / slugify(pdf.stem)
    extracted_dir = work_dir / "extracted"
    extracted_dir.mkdir(parents=True, exist_ok=True)
    source_pdf = work_dir / "source.pdf"
    if pdf.resolve() != source_pdf.resolve():
        shutil.copy2(pdf, source_pdf)

    report_path = work_dir / "report.md"
    evidence_path = work_dir / "evidence_cards.md"
    if not report_path.exists() or "TODO" in report_path.read_text(encoding="utf-8", errors="replace"):
        scaffold = run_python_script(
            SKILL_DIR / "scripts" / "make_report_scaffold.py",
            [str(pdf), "--title", pdf.stem, "--language", language, "--out-root", str(output_dir)],
        )
        require_success(scaffold, "workspace scaffold")
    if not evidence_path.exists():
        evidence_path.write_text("# Evidence Cards\n\n", encoding="utf-8")
    return work_dir


def process_pdf(pdf: Path, options: RunOptions, client: MimoClient) -> Path:
    work_dir = prepare_workspace(pdf, options.output_dir, options.config.pipeline.language)
    report_path = work_dir / "report.md"
    if options.config.pipeline.skip_existing and report_path.exists() and "TODO" not in report_path.read_text(encoding="utf-8", errors="replace"):
        stage(f"[skip] {pdf.name}: existing report")
        return report_path

    source_pdf = work_dir / "source.pdf"
    extracted_dir = work_dir / "extracted"

    stage(f"[text] {pdf.name}")
    text_result = run_python_script(
        SKILL_DIR / "scripts" / "extract_pdf_text.py",
        [str(source_pdf), "--out", str(extracted_dir)],
    )
    require_success(text_result, "text extraction")

    jar_path = options.pdffigures2_jar
    if jar_path:
        stage(f"[figures] {pdf.name}")
        run_pdffigures2(source_pdf, work_dir, jar_path, options.java_path or options.config.pdffigures2.java_path)
    else:
        stage(f"[figures skipped] {pdf.name}: no pdffigures2 jar configured")
        (extracted_dir / "figure_manifest.json").write_text(
            json.dumps({"source": "none", "items": []}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    paper_index = work_dir / "paper_index.json"
    stage(f"[index] {pdf.name}")
    index_result = run_python_script(
        SKILL_DIR / "scripts" / "build_paper_index.py",
        ["--extracted", str(extracted_dir), "--out", str(paper_index)],
    )
    require_success(index_result, "paper index build")

    stage(f"[llm] {pdf.name}")
    if options.config.pipeline.generation_mode == "sectioned":
        report = generate_sectioned_report(
            pdf=pdf,
            source_pdf=source_pdf,
            work_dir=work_dir,
            extracted_dir=extracted_dir,
            paper_index=paper_index,
            options=options,
            client=client,
        )
    elif options.config.pipeline.generation_mode == "one_shot":
        messages = build_report_messages(
            title=pdf.stem,
            pdf_name=source_pdf.name,
            extracted_dir=extracted_dir,
            paper_index_path=paper_index,
            language=options.config.pipeline.language,
            max_input_chars=options.config.pipeline.max_input_chars,
        )
        report = client.complete(messages)
    else:
        raise RuntimeError(f"Unsupported generation_mode: {options.config.pipeline.generation_mode}")
    report_path.write_text(report, encoding="utf-8")

    if options.config.pipeline.validate_report:
        stage(f"[validate] {pdf.name}")
        validate = run_python_script(
            SKILL_DIR / "scripts" / "validate_report.py",
            [str(report_path)],
        )
        if validate.returncode != 0:
            (work_dir / "validation.log").write_text(validate.stdout, encoding="utf-8")
            stage(f"[validation warning] {pdf.name}: see {work_dir / 'validation.log'}")
        else:
            validation_log = work_dir / "validation.log"
            if validation_log.exists():
                validation_log.unlink()

    return report_path


def generate_sectioned_report(
    *,
    pdf: Path,
    source_pdf: Path,
    work_dir: Path,
    extracted_dir: Path,
    paper_index: Path,
    options: RunOptions,
    client: MimoClient,
) -> str:
    stages_dir = work_dir / "stages"
    stages_dir.mkdir(parents=True, exist_ok=True)
    generated: dict[str, str] = {}

    for report_stage in REPORT_STAGES:
        stage_path = stages_dir / f"{report_stage.key}.md"
        if stage_path.exists() and stage_path.read_text(encoding="utf-8", errors="replace").strip():
            generated[report_stage.key] = stage_path.read_text(encoding="utf-8", errors="replace")
            stage(f"[llm skip stage] {pdf.name}: {report_stage.key}")
            continue

        stage(f"[llm stage] {pdf.name}: {report_stage.key}")
        messages = build_stage_messages(
            stage=report_stage,
            title=pdf.stem,
            pdf_name=source_pdf.name,
            extracted_dir=extracted_dir,
            paper_index_path=paper_index,
            language=options.config.pipeline.language,
            max_input_chars=options.config.pipeline.max_input_chars,
            previous_sections=generated,
        )
        content = client.complete(messages)
        stage_path.write_text(content, encoding="utf-8")
        generated[report_stage.key] = content

    return assemble_sectioned_report(pdf.stem, generated)


def run_pipeline(options: RunOptions) -> list[Path]:
    pdfs = discover_pdfs(options.input_dir, options.limit)
    if not pdfs:
        raise RuntimeError(f"No PDF files found in {options.input_dir}")

    if options.config.llm.provider != "mimo":
        raise RuntimeError(f"Unsupported provider: {options.config.llm.provider}")
    if not options.config.llm.api_key:
        raise RuntimeError(
            f"Missing MiMo API key. Set environment variable {options.config.llm.api_key_env}."
        )

    jar_path = options.pdffigures2_jar
    if jar_path and not jar_path.exists():
        raise FileNotFoundError(f"pdffigures2 jar not found: {jar_path}")

    options.output_dir.mkdir(parents=True, exist_ok=True)
    client = MimoClient(options.config.llm)
    reports = []
    for pdf in progress(pdfs):
        reports.append(process_pdf(pdf, options, client))
    return reports
