import unittest

from automation.hotwords import HotwordCorrector


class HotwordTests(unittest.TestCase):
    def test_protects_urls_inline_code_and_fenced_code(self):
        text = (
            "云端work 正文\n"
            "https://example.com/云端work\n"
            "`云端work`\n"
            "```text\n云端work\n```\n"
        )
        corrected, report = HotwordCorrector.apply(text, {"云端work": "云端Work"})
        self.assertIn("云端Work 正文", corrected)
        self.assertIn("https://example.com/云端work", corrected)
        self.assertIn("`云端work`", corrected)
        self.assertIn("```text\n云端work\n```", corrected)
        self.assertEqual(report[0].count, 1)

    def test_longer_alias_runs_first(self):
        corrected, _ = HotwordCorrector.apply(
            "安全助手Boss", {"助手": "盒子", "安全助手Boss": "企业平台"}
        )
        self.assertEqual(corrected, "企业平台")


if __name__ == "__main__":
    unittest.main()
