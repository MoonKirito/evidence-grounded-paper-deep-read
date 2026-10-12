from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from paperdeepread.visual_plan import build_visual_plan, contract
from test_workflow import FakeClient, setup_extracted
from paperdeepread.visuals import analyze_visuals


def fixtures():
    analysis = {"complete": True, "items": [
        {"figType": "Figure", "name": "1", "image": "extracted/figures/1.png", "status": "analyzed", "section": "how"},
        {"figType": "Figure", "name": "2", "image": "extracted/figures/2.png", "status": "analyzed", "section": "how"},
        {"figType": "Figure", "name": "7", "image": "extracted/figures/7.png", "status": "analyzed", "section": "how"},
        {"figType": "Figure", "name": "4", "image": "extracted/figures/4.png", "status": "analyzed", "section": "experiment"}]}
    plan = {"complete": True, "items": [
        {"id": "Figure 1", "image": "extracted/figures/1.png", "section": "how", "include": True, "covers": ["pipeline"], "duplicate_of": "", "reason": "overview"},
        {"id": "Figure 2", "image": "extracted/figures/2.png", "section": "how", "include": True, "covers": ["representation", "masking"], "duplicate_of": "", "reason": "local mechanism adds detail"},
        {"id": "Figure 7", "image": "extracted/figures/7.png", "section": "how", "include": False, "covers": ["masking"], "duplicate_of": "Figure 2", "reason": "same masking information"},
        {"id": "Figure 4", "image": "extracted/figures/4.png", "section": "experiment", "include": True, "covers": ["transfer"], "duplicate_of": "", "reason": "independent transfer evidence"}],
        "claims": [{"claim": "transfer", "evidence": ["Fig. 4"], "visuals": ["Figure 4"], "presentation": "image", "reason": "new contribution beyond accuracy"}]}
    text = "## 1. What\nEvidence: p. 1\n## 2. Why\nEvidence: p. 1\n## 3. How\nOverview and mechanisms\n![overview](extracted/figures/1.png)\n![mechanism](extracted/figures/2.png)\n## 4. Experiment\n![transfer](extracted/figures/4.png)\n## 5. Question\nEvidence: p. 1"
    return analysis, plan, text


class VisualPlanTests(unittest.TestCase):
    def test_overview_and_local_mechanism_both_survive_global_deduplication(self):
        analysis, plan, text = fixtures()
        self.assertEqual(contract.plan_problems(plan, analysis), [])
        self.assertEqual(contract.coverage_problems(text, plan), [])

    def test_independent_method_visual_cannot_be_dropped_for_brevity(self):
        analysis, plan, _ = fixtures()
        plan["items"][0].update(include=False, reason="brevity")
        self.assertTrue(any("omitted" in error for error in contract.plan_problems(plan, analysis)))

    def test_deduplication_cannot_lose_unique_technical_information(self):
        analysis, plan, _ = fixtures()
        plan["items"][0].update(include=False, duplicate_of="Figure 2")
        self.assertTrue(any("all declared technical topics" in error for error in contract.plan_problems(plan, analysis)))

    def test_duplicate_chain_and_unavailable_selected_visuals_are_rejected(self):
        analysis, plan, _ = fixtures()
        plan["items"][2]["duplicate_of"] = "Figure 7"
        self.assertTrue(contract.plan_problems(plan, analysis))
        analysis, plan, _ = fixtures()
        analysis["items"][0]["status"] = "unreadable"
        self.assertTrue(contract.plan_problems(plan, analysis))

    def test_claim_can_use_text_with_reason_but_image_choice_must_have_evidence(self):
        analysis, plan, _ = fixtures()
        plan["items"][3]["include"] = False
        self.assertTrue(any("no selected supporting visual" in error for error in contract.plan_problems(plan, analysis)))
        plan["claims"][0].update(presentation="text", reason="one numerical comparison is sufficient for this secondary claim")
        self.assertEqual(contract.plan_problems(plan, analysis), [])

    def test_wrong_section_or_silent_omission_fails_coverage(self):
        _, plan, text = fixtures()
        text = text.replace("![mechanism](extracted/figures/2.png)", "")
        self.assertTrue(any("missing from how" in error for error in contract.coverage_problems(text, plan)))
        _, plan, text = fixtures()
        text = text.replace("![transfer](extracted/figures/4.png)", "") + "\n![transfer](extracted/figures/4.png)"
        self.assertTrue(any("missing from experiment" in error for error in contract.coverage_problems(text, plan)))

    def test_unplanned_duplicate_illustration_is_rejected(self):
        _, plan, text = fixtures()
        self.assertTrue(contract.coverage_problems(text + "\n![duplicate](extracted/figures/7.png)", plan))

    def test_plan_is_cached_and_changes_in_analysis_invalidate_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            extracted = setup_extracted(Path(tmp), 1)
            client = FakeClient()
            analysis_path = analyze_visuals(extracted, client, "中文")
            build_visual_plan(extracted, client, "中文")
            self.assertEqual(client.events.count("plan"), 1)
            build_visual_plan(extracted, client, "中文")
            self.assertEqual(client.events.count("plan"), 1)
            analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
            analysis["items"][0]["observation"] = "a newly verified mechanism"
            analysis_path.write_text(json.dumps(analysis), encoding="utf-8")
            build_visual_plan(extracted, client, "中文")
            self.assertEqual(client.events.count("plan"), 2)

    def test_invalid_plan_gets_one_bounded_repair_before_report_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            extracted = setup_extracted(Path(tmp), 1)
            client = FakeClient()
            analyze_visuals(extracted, client, "中文")
            calls = []
            correct = client.complete
            def complete(messages):
                calls.append(1)
                if len(calls) == 1:
                    return '{"items": [], "claims": []}'
                return correct(messages[:2])
            client.complete = complete
            build_visual_plan(extracted, client, "中文")
            self.assertEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main()
