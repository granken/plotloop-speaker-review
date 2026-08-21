import json
import unittest
from unittest.mock import patch

from automation.config import LarkConfig
from automation.lark import LarkClient


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


if __name__ == "__main__":
    unittest.main()
