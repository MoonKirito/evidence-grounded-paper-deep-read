from __future__ import annotations

import unittest

from paperdeepread.evidence_pack import build_stage_text_pack, estimate_char_budget


class EvidencePackTests(unittest.TestCase):
    def test_stage_pack_prioritizes_matching_sections_within_budget(self) -> None:
        sections = {
            "pages": [
                {
                    "page": 1,
                    "paragraphs": [
                        {"id": "P0001", "text": "Abstract. This paper proposes a detector."},
                        {"id": "P0002", "text": "Related work. Prior systems are reviewed."},
                    ],
                },
                {
                    "page": 2,
                    "paragraphs": [
                        {"id": "P0003", "text": "Method. The network uses temporal segmentation and contrastive learning."},
                        {"id": "P0004", "text": "Training details include optimizer, augmentations, and loss terms."},
                    ],
                },
                {
                    "page": 3,
                    "paragraphs": [
                        {"id": "P0005", "text": "Experiments compare baselines and report F1 scores."},
                    ],
                },
            ]
        }

        packed = build_stage_text_pack(
            sections=sections,
            stage_keywords=["method", "training", "loss", "network"],
            always_keywords=["abstract"],
            budget_chars=180,
        )

        self.assertIn("P0001", packed)
        self.assertIn("P0003", packed)
        self.assertIn("temporal segmentation", packed)
        self.assertNotIn("P0005", packed)
        self.assertLessEqual(len(packed), 260)

    def test_budget_scales_down_for_many_figures_without_going_tiny(self) -> None:
        small = estimate_char_budget(max_input_chars=80000, figure_count=2)
        large = estimate_char_budget(max_input_chars=80000, figure_count=30)

        self.assertGreater(small, large)
        self.assertGreaterEqual(large, 24000)
        self.assertLessEqual(small, 48000)

    def test_late_high_score_evidence_wins_over_early_low_score(self):
        sections = {"pages": [{"page": 1, "paragraphs": [
            {"id": "EARLY", "text": "method " + "x" * 45},
            {"id": "LATE", "text": "method loss training network"}]}]}
        packed = build_stage_text_pack(sections=sections, stage_keywords=["method", "loss", "training", "network"], always_keywords=[], budget_chars=70)
        self.assertIn("LATE", packed)
        self.assertNotIn("EARLY", packed)
        self.assertLessEqual(len(packed), 70)

    def test_oversized_paragraph_never_exceeds_budget(self):
        sections = {"pages": [{"page": 1, "paragraphs": [{"text": "abstract " + "x" * 200}]}]}
        packed = build_stage_text_pack(sections=sections, stage_keywords=[], always_keywords=["abstract"], budget_chars=30)
        self.assertLessEqual(len(packed), 30)
        self.assertLessEqual(estimate_char_budget(1000, 20), 1000)

    def test_small_paper_keeps_non_keyword_definitions(self):
        sections = {"pages": [{"page": 1, "paragraphs": [{"text": "Let z denote the latent state."}]}]}
        packed = build_stage_text_pack(sections=sections, stage_keywords=["method"], always_keywords=[], budget_chars=1000)
        self.assertIn("latent state", packed)


if __name__ == "__main__":
    unittest.main()
