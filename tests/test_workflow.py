from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from paperdeepread.config import AppConfig, LlmConfig, PipelineConfig, Pdffigures2Config
from paperdeepread.pipeline import RunOptions, process_pdf, generation_fingerprint, generate_sectioned_report
from paperdeepread.providers.openai_compatible import OpenAICompatibleClient
from paperdeepread.sectioned import REPORT_STAGES
from paperdeepread.utils import SKILL_DIR, slugify
from paperdeepread.visuals import analyze_visuals
from paperdeepread.visual_plan import build_visual_plan

spec = importlib.util.spec_from_file_location("report_validator", SKILL_DIR / "scripts" / "validate_report.py")
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


def report_text() -> str:
    return "# Demo\n\n" + "\n\n".join(
        f"{stage.heading}\n\n具体分析。(Evidence: p. 1)" for stage in REPORT_STAGES
    ) + "\n"


def setup_extracted(root: Path, count: int = 2) -> Path:
    extracted = root / "extracted"
    (extracted / "figures").mkdir(parents=True, exist_ok=True)
    items = []
    for n in range(count):
        name = f"source-Figure{n + 1}-1.png"
        # Mock model only: no real visual/model evaluation is claimed by this test.
        (extracted / "figures" / name).write_bytes(b"mock-png")
        items.append({"name": str(n + 1), "figType": "Figure", "page": n,
                      "caption": f"Figure {n + 1}. Framework", "image": f"extracted/figures/{name}"})
    (extracted / "figure_manifest.json").write_text(json.dumps({"source": "pdffigures2", "items": items}), encoding="utf-8")
    (extracted / "sections.json").write_text(json.dumps({"pages": [
        {"page": 1, "paragraphs": [{"id": "P0001", "text": "Abstract. Method. Figure 1 and Fig. 9 show the approach. Experiments test it."}]}]}), encoding="utf-8")
    (extracted / "full_text.md").write_text("Abstract. Method. Experiments.", encoding="utf-8")
    return extracted


class FakeClient:
    config = SimpleNamespace(model="mock-model", base_url="mock://endpoint")

    def __init__(self):
        self.events = []

    def complete(self, messages):
        content = messages[-1].content
        if isinstance(content, list):
            self.events.append("visual")
            assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")
            return json.dumps({"summary": "框架图", "observation": "输入进入模块", "supports": "设计路线",
                               "limitation": "不能证明性能", "reason": "帮助理解", "section": "how",
                               "selected": True, "readable": True, "evidence": ["Fig. 1"]}, ensure_ascii=False)
        if "先形成全局选图" in messages[0].content:
            self.events.append("plan")
            analysis = json.loads(content.split("# All Visual Analyses\n", 1)[1])
            items = [{"id": f"{v['figType']} {v['name']}", "image": v.get("image", ""), "section": "how" if v.get("status") == "analyzed" else "none",
                      "include": v.get("status") == "analyzed", "duplicate_of": "", "covers": ["method"], "reason": "independent method visual"} for v in analysis["items"]]
            selected = [v["id"] for v in items if v["include"]]
            return json.dumps({"items": items, "claims": [{"claim": "method contribution", "evidence": ["p. 1"], "visuals": selected,
                               "presentation": "image" if selected else "text", "reason": "method diagram or disclosed missing visual"}]})
        self.events.append("report")
        if "当前阶段：" in content:
            for stage in REPORT_STAGES:
                if stage.description in content:
                    images = ""
                    if stage.key == "how":
                        plan = json.loads(content.split("# Global Visual Plan\n", 1)[1].split("\n#", 1)[0])
                        images = "\n".join(f"![method]({v['image']})" for v in plan["items"] if v["include"] and v["section"] == "how")
                    return f"{stage.heading}\n\n具体分析。(Evidence: p. 1)\n{images}\n"
        if "# Global Visual Plan\n" in content:
            plan = json.loads(content.split("# Global Visual Plan\n", 1)[1].split("\n#", 1)[0])
            images = "\n".join(f"![method]({v['image']})" for v in plan["items"] if v["include"])
            return report_text().replace("## 4.", images + "\n\n## 4.")
        return report_text()


class VisualAnalysisTests(unittest.TestCase):
    def test_all_images_are_analyzed_and_cached_before_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            extracted = setup_extracted(Path(tmp))
            client = FakeClient()
            output = analyze_visuals(extracted, client, "中文")
            data = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(client.events, ["visual", "visual"])
            self.assertTrue(data["complete"])
            self.assertEqual([v["pdf_page"] for v in data["items"]], [1, 2])
            self.assertIn("figure 9", data["unmatched_text_references"])
            analyze_visuals(extracted, client, "中文")
            self.assertEqual(client.events, ["visual", "visual"])
            (extracted / "figures" / "source-Figure1-1.png").write_bytes(b"changed-image")
            analyze_visuals(extracted, client, "中文")
            self.assertEqual(len(client.events), 3)

    def test_missing_image_is_disclosed_without_fallback_cropping(self):
        with tempfile.TemporaryDirectory() as tmp:
            extracted = setup_extracted(Path(tmp), 1)
            (extracted / "figures" / "source-Figure1-1.png").unlink()
            client = FakeClient()
            data = json.loads(analyze_visuals(extracted, client, "中文").read_text(encoding="utf-8"))
            self.assertEqual(data["items"][0]["status"], "unavailable")
            self.assertFalse(data["items"][0]["selected"])
            self.assertEqual(client.events, [])

    def test_invalid_analysis_blocks_report_preparation(self):
        with tempfile.TemporaryDirectory() as tmp:
            extracted = setup_extracted(Path(tmp), 1)
            client = FakeClient()
            client.complete = lambda _: '{"summary": "not enough"}'
            with self.assertRaises(RuntimeError):
                analyze_visuals(extracted, client, "中文")
            self.assertFalse((extracted / "visual_analysis.json").exists())

    def test_unreadable_image_is_not_eligible_for_embedding(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            extracted = setup_extracted(root, 1)
            client = FakeClient()
            original = client.complete
            def unreadable(messages):
                data = json.loads(original(messages))
                data.update(readable=False, selected=False)
                return json.dumps(data)
            client.complete = unreadable
            result = json.loads(analyze_visuals(extracted, client, "中文").read_text(encoding="utf-8"))
            self.assertEqual(result["items"][0]["status"], "unreadable")
            report = root / "report.md"
            report.write_text(report_text() + "![图](extracted/figures/source-Figure1-1.png)", encoding="utf-8")
            self.assertTrue(any("not analyzed" in p for p in validator.validate_report(report)))


class WorkflowTests(unittest.TestCase):
    def test_interrupted_sections_resume_and_changed_evidence_invalidates_them(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            extracted = setup_extracted(root, 1)
            client = FakeClient()
            analysis_path = analyze_visuals(extracted, client, "中文")
            build_visual_plan(extracted, client, "中文")
            index = root / "paper_index.json"
            index.write_text("{}", encoding="utf-8")
            config = AppConfig(LlmConfig("mimo", "mock", "mock", "KEY", .2, 1000, 10, False),
                               PipelineConfig("中文", "sectioned", 120000, True, False), Pdffigures2Config("mock", "java"))
            options = RunOptions(root, root, config, root / "mock.jar", "java")
            args = dict(pdf=root / "paper.pdf", source_pdf=root / "source.pdf", work_dir=root,
                        extracted_dir=extracted, paper_index=index, options=options, client=client)
            complete = client.complete
            def interrupt(messages):
                if REPORT_STAGES[1].description in messages[-1].content:
                    raise RuntimeError("simulated network interruption")
                return complete(messages)
            client.complete = interrupt
            with self.assertRaises(RuntimeError):
                generate_sectioned_report(**args)
            self.assertTrue((root / "stages" / "what.md").exists())
            self.assertFalse((root / "stages" / "why.md").exists())
            client.complete = complete
            previous = len(client.events)
            generate_sectioned_report(**args)
            self.assertEqual(len(client.events) - previous, 4)
            analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
            analysis["items"][0]["observation"] = "revised observation"
            analysis_path.write_text(json.dumps(analysis), encoding="utf-8")
            previous = len(client.events)
            generate_sectioned_report(**args)
            self.assertEqual(len(client.events) - previous, 5)

    def test_both_generation_modes_analyze_all_visuals_first(self):
        for mode in ("sectioned", "one_shot"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                pdf = root / "论文一.pdf"
                pdf.write_bytes(b"mock-pdf")
                jar = root / "pdffigures2.jar"
                jar.write_bytes(b"mock-jar")
                config = AppConfig(LlmConfig("mimo", "mock://endpoint", "mock", "TEST_KEY", .2, 1000, 10, False),
                                   PipelineConfig("中文", mode, 120000, True, True), Pdffigures2Config(str(jar), "java"),
                                   vision=LlmConfig("gemini", "mock://vision", "vision-model", "VISION_KEY", None, 1000, 10, False) if mode == "one_shot" else None)
                options = RunOptions(root, root / "reports", config, jar, "java")
                client = FakeClient()
                visual_client = FakeClient() if config.vision else client
                work = options.output_dir / slugify(pdf.stem)
                work.mkdir(parents=True)
                (work / "report.md").write_text("TODO", encoding="utf-8")
                # Include a legacy stage to verify workflow cache invalidation.
                (work / "stages").mkdir()
                (work / "stages" / "overview_metadata.md").write_text("old report", encoding="utf-8")
                def fake_script(script, args):
                    if script.name == "extract_pdf_text.py":
                        setup_extracted(work)
                    elif script.name == "build_paper_index.py":
                        (work / "paper_index.json").write_text("{}", encoding="utf-8")
                    elif script.name == "validate_report.py":
                        problems = validator.validate_report(Path(args[0]))
                        return subprocess.CompletedProcess([], int(bool(problems)), str(problems))
                    return subprocess.CompletedProcess([], 0, "")
                with patch("paperdeepread.pipeline.run_python_script", side_effect=fake_script), patch("paperdeepread.pipeline.run_pdffigures2"), patch("paperdeepread.pipeline.create_client", return_value=visual_client) as factory:
                    report = process_pdf(pdf, options, client)
                    self.assertEqual(visual_client.events[:2], ["visual", "visual"])
                    report_events = client.events if config.vision else client.events[2:]
                    self.assertEqual(report_events, ["plan"] + ["report"] * (5 if mode == "sectioned" else 1))
                    if config.vision:
                        factory.assert_called_once_with(config.vision)
                    else:
                        factory.assert_not_called()
                    self.assertEqual(validator.validate_report(report), [])
                    self.assertFalse((work / "stages" / "overview_metadata.md").exists())
                    before = list(client.events)
                    process_pdf(pdf, options, client)
                    self.assertEqual(client.events, before)
                    old_fingerprint = generation_fingerprint(pdf, options)
                    pdf.write_bytes(b"changed-pdf")
                    self.assertNotEqual(old_fingerprint, generation_fingerprint(pdf, options))


class ReportValidationTests(unittest.TestCase):
    def validate_text(self, text):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "report.md"
            path.write_text(text, encoding="utf-8")
            return validator.validate_report(path)

    def test_no_images_is_valid_and_math_is_checked(self):
        text = report_text().replace("具体分析。", "使用 $x$。\n\n$$\nx = y + 1\n$$\n")
        self.assertEqual(self.validate_text(text), [])
        for bad in ("使用 \\(x\\)。", "$$x=y$$", "$x", "$$\nx=y", "```latex\n$x$\n```"):
            with self.subTest(bad=bad):
                self.assertTrue(self.validate_text(report_text() + bad))

    def test_reordered_sections_and_missing_evidence_fail(self):
        text = report_text().replace("## 1. What", "## 1. Why")
        self.assertTrue(self.validate_text(text))
        self.assertTrue(self.validate_text(report_text().replace("(Evidence: p. 1)", "")))

    def test_image_requires_extraction_provenance_and_analysis(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            extracted = setup_extracted(root, 1)
            report = root / "report.md"
            image = "extracted/figures/source-Figure1-1.png"
            report.write_text(report_text().replace("## 4.", f"![图 1]({image})\n\n## 4."), encoding="utf-8")
            self.assertTrue(validator.validate_report(report))
            analyze_visuals(extracted, FakeClient(), "中文")
            build_visual_plan(extracted, FakeClient(), "中文")
            self.assertEqual(validator.validate_report(report), [])
            report.write_text(report.read_text(encoding="utf-8") + f"![重复]({image})\n", encoding="utf-8")
            self.assertTrue(any("Duplicate" in p for p in validator.validate_report(report)))

    def test_external_or_missing_images_fail(self):
        self.assertTrue(self.validate_text(report_text() + "![remote](https://example.com/plot.png)"))
        self.assertTrue(self.validate_text(report_text() + "![preview](extracted/figures/page-001-preview.png)"))


class ProviderTests(unittest.TestCase):
    def test_truncated_stream_is_not_accepted_as_finished_report(self):
        config = LlmConfig("mimo", "mock", "mock", "KEY", .2, 10, 10, True)
        events = [b'data: {"choices":[{"delta":{"content":"partial"},"finish_reason":"length"}]}\n']
        with self.assertRaises(RuntimeError):
            OpenAICompatibleClient(config)._read_stream(events)


if __name__ == "__main__":
    unittest.main()
