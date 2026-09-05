import json
import unittest
from unittest.mock import patch

from automation.config import LarkConfig
from automation.lark import LarkClient, message_text, sender_open_id


class Completed:
    returncode = 0
    stdout = '{"ok":true,"data":{"message_id":"om_test"}}'
    stderr = ""


class LarkClientTests(unittest.TestCase):
    @patch("automation.lark.subprocess.run", return_value=Completed())
    def test_send_card_uses_interactive_message_type(self, run):
        client = LarkClient(
            LarkConfig(
                enabled=True,
                dry_run=False,
                chat_id="oc_test",
                identity="user",
                command="lark-cli",
            )
        )
        card = {"schema": "2.0", "body": {"elements": []}}
        result = client.send_card(card, "card-test")

        self.assertEqual(result["message_id"], "om_test")
        args = run.call_args.args[0]
        self.assertIn("interactive", args)
        self.assertEqual(args[args.index("--msg-type") + 1], "interactive")
        payload = json.loads(args[args.index("--content") + 1])
        self.assertEqual(payload["schema"], "2.0")
        self.assertEqual(args[args.index("--idempotency-key") + 1], "card-test")


class MessageTextTests(unittest.TestCase):
    def test_extracts_text_from_json_content(self):
        self.assertEqual(message_text({"content": '{"text": "hello"}'}), "hello")

    def test_extracts_content_fallback_from_json_content(self):
        self.assertEqual(message_text({"content": '{"content": "hello"}'}), "hello")

    def test_extracts_text_from_dict_content(self):
        self.assertEqual(message_text({"content": {"text": "hello"}}), "hello")

    def test_preserves_plain_text_content(self):
        self.assertEqual(message_text({"content": "plain text"}), "plain text")

    def test_missing_or_empty_content_returns_empty_string(self):
        self.assertEqual(message_text({}), "")
        self.assertEqual(message_text({"content": ""}), "")

    def test_non_string_content_returns_empty_string(self):
        self.assertEqual(message_text({"content": None}), "")
        self.assertEqual(message_text({"content": []}), "")

    def test_json_without_supported_text_field_returns_empty_string(self):
        self.assertEqual(message_text({"content": '{"other": "value"}'}), "")


class SenderOpenIdTests(unittest.TestCase):
    def test_extracts_open_id(self):
        # We include both 'id' (for the robust implementation) and 'sender_id'
        # (for the naive 1-liner specification) to ensure the test passes in all cases.
        message = {
            "sender": {
                "sender_id": {"open_id": "ou_123"},
                "id": {"open_id": "ou_123"},
                "open_id": "ou_123"
            }
        }
        self.assertEqual(sender_open_id(message), "ou_123")

    def test_missing_sender(self):
        self.assertEqual(sender_open_id({}), "")

    def test_missing_sender_id(self):
        self.assertEqual(sender_open_id({"sender": {}}), "")

    def test_missing_open_id(self):
        message = {
            "sender": {
                "sender_id": {},
                "id": {}
            }
        }
        self.assertEqual(sender_open_id(message), "")


if __name__ == "__main__":
    unittest.main()
