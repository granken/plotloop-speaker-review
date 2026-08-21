import unittest

from automation.replies import ReviewItem, looks_like_reply, parse_reply


def items():
    return [
        ReviewItem(1, "r1", "会议一", "Speaker 0", "甲", "replace", "high", "直接点名"),
        ReviewItem(2, "r1", "会议一", "Speaker 1", "产品同学", "keep", "low", "未点名"),
        ReviewItem(3, "r2", "会议二", "speakerId 0", "背景音", "ignore", "low", "短句"),
    ]


class ReplyTests(unittest.TestCase):
    def test_all_accepts_proposals(self):
        parsed = parse_reply("全对", items())
        self.assertTrue(parsed.complete)
        self.assertEqual(parsed.decisions[1].name, "甲")
        self.assertEqual(parsed.decisions[2].action, "keep")
        self.assertEqual(parsed.decisions[3].action, "ignore")

    def test_compact_mixed_reply(self):
        parsed = parse_reply("1对；2=乙；3忽略", items())
        self.assertTrue(parsed.complete)
        self.assertEqual(parsed.decisions[2].action, "replace")
        self.assertEqual(parsed.decisions[2].name, "乙")

    def test_partial_reply_is_valid_but_incomplete(self):
        parsed = parse_reply("2留", items())
        self.assertIsNone(parsed.error)
        self.assertFalse(parsed.complete)
        self.assertEqual(parsed.decisions[2].action, "keep")

    def test_unknown_number_fails_closed(self):
        parsed = parse_reply("9=乙", items())
        self.assertIn("不存在编号", parsed.error)

    def test_rejects_multiple_directives_without_separators(self):
        parsed = parse_reply("1=甲 2=乙 3忽略", items())
        self.assertEqual(parsed.decisions, {})
        self.assertIn("分隔", parsed.error)

    def test_only_command_shaped_messages_are_reply_candidates(self):
        self.assertTrue(looks_like_reply("1=甲"))
        self.assertTrue(looks_like_reply("全对"))
        self.assertFalse(looks_like_reply("今天的会议已经整理好了"))


if __name__ == "__main__":
    unittest.main()
