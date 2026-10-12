from __future__ import annotations

import json
import hashlib
import os
import shutil
import subprocess
from dataclasses import dataclass, replace
from pathlib import Path

try:
    from tqdm import tqdm
except ImportError:  # pragma: no cover
    tqdm = None  # type: ignore

from paperdeepread.config import AppConfig
from paperdeepread.prompts import build_report_messages
from paperdeepread.providers import create_client
from paperdeepread.providers.base import ModelClient
from paperdeepread.sectioned import REPORT_STAGES, assemble_sectioned_report, build_stage_messages
from paperdeepread.sectioned import strip_markdown_fence
from paperdeepread.utils import REPO_ROOT, SKILL_DIR, require_success, run_python_script, slugify
from paperdeepread.visuals import analyze_visuals
from paperdeepread.visual_plan import build_visual_plan


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
    # These dedicated folders contain only generated extraction artifacts.
    # Otherwise an earlier extraction can silently contaminate the new manifest.
    for artifact_dir in (data_dir, figures_dir):
        for artifact in artifact_dir.iterdir():
            if artifact.is_file():
                artifact.unlink()

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
    if not report_path.exists() or "TODO" in report_path.read_text(encoding="utf-8", errors="replace"):
        scaffold = run_python_script(
            SKILL_DIR / "scripts" / "make_report_scaffold.py",
            [str(pdf), "--title", pdf.stem, "--language", language, "--out-root", str(output_dir)],
        )
        require_success(scaffold, "workspace scaffold")
    return work_dir


def process_pdf(pdf: Path, options: RunOptions, client: ModelClient) -> Path:
    work_dir = prepare_workspace(pdf, options.output_dir, options.config.pipeline.language)
    report_path = work_dir / "report.md"
    fingerprint = generation_fingerprint(pdf, options)
    state_path = work_dir / "generation_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    cache_matches = state.get("fingerprint") == fingerprint
    if (options.config.pipeline.skip_existing and cache_matches and state.get("complete")
            and report_path.exists() and state.get("report_sha256") == hashlib.sha256(report_path.read_bytes()).hexdigest()):
        stage(f"[skip] {pdf.name}: existing report")
        return report_path

    if not cache_matches:
        for cached in (work_dir / "stages").glob("*.md"):
            cached.unlink()
    state_path.write_text(json.dumps({"fingerprint": fingerprint, "complete": False}), encoding="utf-8")

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
        raise RuntimeError("pdffigures2 jar is required; configure jar_path or pass --pdffigures2-jar.")

    paper_index = work_dir / "paper_index.json"
    stage(f"[index] {pdf.name}")
    index_result = run_python_script(
        SKILL_DIR / "scripts" / "build_paper_index.py",
        ["--extracted", str(extracted_dir), "--out", str(paper_index)],
    )
    require_success(index_result, "paper index build")

    stage(f"[visual analysis] {pdf.name}: inspect all extracted figures/tables before writing")
    vision_client = create_client(options.config.vision) if options.config.vision else client
    analyze_visuals(extracted_dir, vision_client, options.config.pipeline.language, on_progress=stage)
    stage(f"[visual plan] {pdf.name}: method deduplication and core-claim coverage")
    build_visual_plan(extracted_dir, client, options.config.pipeline.language)

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
        report = strip_markdown_fence(client.complete(messages)) + "\n"
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
            # Preserve report/log for inspection, but don't endlessly reuse bad
            # stage prose on the next run. Successful visual analyses stay cached.
            for cached in (work_dir / "stages").glob("*.md"):
                cached.unlink()
            raise RuntimeError(f"Report validation failed for {pdf.name}; see {work_dir / 'validation.log'}")
        else:
            validation_log = work_dir / "validation.log"
            if validation_log.exists():
                validation_log.unlink()

    state_path.write_text(json.dumps({"fingerprint": fingerprint, "complete": True,
                                     "report_sha256": hashlib.sha256(report_path.read_bytes()).hexdigest()}), encoding="utf-8")
    return report_path


def generation_fingerprint(pdf: Path, options: RunOptions) -> str:
    """Invalidate old reports/stages when source, instructions or configuration change."""
    digest = hashlib.sha256(pdf.read_bytes())
    digest.update(repr(options.config).encode("utf-8"))
    digest.update(str(options.pdffigures2_jar).encode("utf-8"))
    if options.pdffigures2_jar and options.pdffigures2_jar.is_file():
        stat = options.pdffigures2_jar.stat()
        digest.update(f"{stat.st_size}:{stat.st_mtime_ns}".encode("utf-8"))
    digest.update(str(options.java_path).encode("utf-8"))
    for label, root in (("code", Path(__file__).resolve().parent), ("skill", SKILL_DIR)):
        for path in sorted(root.rglob("*")):
            if path.is_file() and path.suffix in {".py", ".md", ".yaml"}:
                digest.update(f"{label}/{path.relative_to(root).as_posix()}".encode("utf-8"))
                digest.update(path.read_bytes())
    return digest.hexdigest()


def generate_sectioned_report(
    *,
    pdf: Path,
    source_pdf: Path,
    work_dir: Path,
    extracted_dir: Path,
    paper_index: Path,
    options: RunOptions,
    client: ModelClient,
) -> str:
    stages_dir = work_dir / "stages"
    stages_dir.mkdir(parents=True, exist_ok=True)
    context_hash = hashlib.sha256()
    for path in (extracted_dir / "sections.json", extracted_dir / "visual_analysis.json", extracted_dir / "visual_plan.json", paper_index):
        context_hash.update(path.read_bytes())
    context_path = stages_dir / "context.sha256"
    current_context = context_hash.hexdigest()
    if not context_path.exists() or context_path.read_text(encoding="utf-8") != current_context:
        for cached in stages_dir.glob("*.md"):
            cached.unlink()
    context_path.write_text(current_context, encoding="utf-8")
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
    options = replace(options, input_dir=options.input_dir.resolve(), output_dir=options.output_dir.resolve(),
                      pdffigures2_jar=options.pdffigures2_jar.resolve() if options.pdffigures2_jar else None)
    pdfs = discover_pdfs(options.input_dir, options.limit)
    if not pdfs:
        raise RuntimeError(f"No PDF files found in {options.input_dir}")

    for llm_config in (options.config.llm, options.config.vision):
        if llm_config and llm_config.require_api_key and not llm_config.api_key:
            raise RuntimeError(f"Missing {llm_config.provider} API key. Set environment variable {llm_config.api_key_env} or configure api_key.")

    jar_path = options.pdffigures2_jar
    if jar_path is None:
        raise RuntimeError("pdffigures2 jar is required; configure jar_path or pass --pdffigures2-jar.")
    if jar_path and not jar_path.exists():
        raise FileNotFoundError(f"pdffigures2 jar not found: {jar_path}")

    options.output_dir.mkdir(parents=True, exist_ok=True)
    slugs = [slugify(pdf.stem).casefold() for pdf in pdfs]
    if len(slugs) != len(set(slugs)):
        raise RuntimeError("PDF filenames map to the same report directory; rename conflicting PDFs first.")
    client = create_client(options.config.llm)
    reports = []
    for pdf in progress(pdfs):
        reports.append(process_pdf(pdf, options, client))
    return reports
