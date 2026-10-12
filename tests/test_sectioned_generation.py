from __future__ import annotations

import unittest

from paperdeepread.sectioned import REPORT_STAGES, assemble_sectioned_report


class SectionedGenerationTests(unittest.TestCase):
    def test_assemble_sectioned_report_keeps_narrative_order(self) -> None:
        sections = {stage.key: f"{stage.heading}\n\n内容 {stage.key}" for stage in REPORT_STAGES}

        report = assemble_sectioned_report("Demo Paper", sections)

        self.assertTrue(report.startswith("# 论文精读报告：Demo Paper"))
        self.assertIn("## 1. What：做了什么", report)
        self.assertIn("## 4. Experiment：如何证明有效", report)
        self.assertEqual(report.count("\n## "), 5)
        self.assertIn("## 5. Question：评价与疑问", report)
        self.assertLess(report.index("## 1. What：做了什么"), report.index("## 4. Experiment：如何证明有效"))

    def test_missing_stage_is_not_published_as_a_complete_report(self):
        with self.assertRaises(RuntimeError):
            assemble_sectioned_report("Demo", {})


if __name__ == "__main__":
    unittest.main()
