import json
import unittest

from automation.cards import build_review_cards
from automation.replies import ReviewItem


def review(recording_id, meeting, mappings, date="2026-08-06", time="10:00:00"):
    return {
        "recording_id": recording_id,
        "review": {
            "current": {
                "meeting": meeting,
                "date": date,
                "time": time,
                "note": f"{meeting}的一句话总结。",
                "mappings": mappings,
            }
        },
    }


class CardTests(unittest.TestCase):
    def test_focus_meetings_are_first_and_numbers_stay_global(self):
        reviews = [
            review(
                "r1",
                "低疑惑会议",
                [
                    {
                        "label": "Speaker 0",
                        "name": "陈晨",
                        "action": "replace",
                        "confidence": "high",
                        "note": "直接点名",
                    }
                ],
            ),
            review(
                "r2",
                "高疑惑会议",
                [
                    {
                        "label": "Speaker 1",
                        "name": "产品同学",
                        "action": "keep",
                        "confidence": "low",
                        "note": "没有姓名证据",
                    }
                ],
            ),
        ]
        items = [
            ReviewItem(1, "r1", "低疑惑会议", "Speaker 0", "陈晨", "replace", "high", ""),
            ReviewItem(2, "r2", "高疑惑会议", "Speaker 1", "产品同学", "keep", "low", ""),
        ]
        cards = build_review_cards("SR-TEST", reviews, items)
        self.assertEqual(len(cards), 1)
        card = cards[0]
        self.assertEqual(card["schema"], "2.0")
        panels = card["body"]["elements"][1:]
        self.assertIn("高疑惑会议", panels[0]["header"]["title"]["content"])
        self.assertTrue(panels[0]["expanded"])
        self.assertIn("<number_tag>2</number_tag>", panels[0]["elements"][0]["content"])
        self.assertIn("<number_tag>1</number_tag>", panels[1]["elements"][0]["content"])
        self.assertNotIn("behaviors", json.dumps(card, ensure_ascii=False))

    def test_large_batches_split_into_mobile_sized_cards(self):
        reviews = []
        items = []
        for number in range(1, 7):
            recording_id = f"r{number}"
            mapping = {
                "label": "Speaker 0",
                "name": f"候选人{number}",
                "action": "replace",
                "confidence": "high",
                "note": "证据",
            }
            reviews.append(review(recording_id, f"会议{number}", [mapping]))
            items.append(
                ReviewItem(
                    number,
                    recording_id,
                    f"会议{number}",
                    "Speaker 0",
                    f"候选人{number}",
                    "replace",
                    "high",
                    "证据",
                )
            )
        cards = build_review_cards("SR-LARGE", reviews, items, max_meetings_per_card=4)
        self.assertEqual(len(cards), 2)
        self.assertEqual(len(cards[0]["body"]["elements"]), 5)
        self.assertEqual(len(cards[1]["body"]["elements"]), 3)
        self.assertEqual(cards[0]["header"]["title"]["content"], "说话人确认 · 1/2")
        self.assertEqual(cards[1]["header"]["title"]["content"], "说话人确认 · 2/2")


if __name__ == "__main__":
    unittest.main()
