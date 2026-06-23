from __future__ import annotations

import unittest

from paperdeepread.sectioned import REPORT_STAGES, assemble_sectioned_report


class SectionedGenerationTests(unittest.TestCase):
    def test_assemble_sectioned_report_keeps_chinese_heading_order(self) -> None:
        sections = {stage.key: f"{stage.heading}\n\n内容 {stage.key}" for stage in REPORT_STAGES}

        report = assemble_sectioned_report("Demo Paper", sections)

        self.assertTrue(report.startswith("# 论文精读报告：Demo Paper"))
        self.assertIn("## 2. 作者做了什么", report)
        self.assertIn("## 5. 作者如何验证", report)
        self.assertNotIn("## 2. WHAT", report)
        self.assertLess(report.index("## 2. 作者做了什么"), report.index("## 5. 作者如何验证"))


if __name__ == "__main__":
    unittest.main()
