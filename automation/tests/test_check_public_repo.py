import importlib.util
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "check_public_repo.py"
SPEC = importlib.util.spec_from_file_location("check_public_repo", SCRIPT_PATH)
check_public_repo = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check_public_repo)


class CheckPublicRepoTests(unittest.TestCase):
    def setUp(self):
        self.dummy_path = Path("dummy.txt")

    def test_content_issues_no_issues(self):
        text = "This is a clean text file.\nNothing to see here."
        issues = check_public_repo.content_issues(self.dummy_path, text)
        self.assertEqual(issues, [])

    def test_content_issues_mac_home(self):
        text = "My home dir is /" + "Users/jules/Documents"
        issues = check_public_repo.content_issues(self.dummy_path, text)
        self.assertEqual(issues, ["contains an absolute macOS home path"])

    def test_content_issues_internal_recording(self):
        text = "Path: 360/" + "录音/meeting.wav"
        issues = check_public_repo.content_issues(self.dummy_path, text)
        self.assertEqual(issues, ["contains an internal recording directory"])

    def test_content_issues_non_placeholder_chat_id(self):
        # Empty should pass
        text1 = '{"chat_id": ""}'
        self.assertEqual(check_public_repo.content_issues(self.dummy_path, text1), [])

        # Placeholder should pass
        text2 = '{"chat_id": "YOUR_CHAT_ID"}'
        self.assertEqual(check_public_repo.content_issues(self.dummy_path, text2), [])

        # Non-placeholder should fail
        text3 = '{"chat_id":' + ' "12345"}'
        self.assertEqual(
            check_public_repo.content_issues(self.dummy_path, text3),
            ["contains a non-placeholder chat_id"]
        )

    def test_content_issues_non_placeholder_sender_open_id(self):
        # Empty should pass
        text1 = '{"sender_open_id": ""}'
        self.assertEqual(check_public_repo.content_issues(self.dummy_path, text1), [])

        # Placeholder should pass
        text2 = '{"sender_open_id": "YOUR_OPEN_ID"}'
        self.assertEqual(check_public_repo.content_issues(self.dummy_path, text2), [])

        # Non-placeholder should fail
        text3 = '{"sender_open_id":' + ' "user123"}'
        self.assertEqual(
            check_public_repo.content_issues(self.dummy_path, text3),
            ["contains a non-placeholder sender_open_id"]
        )

    def test_content_issues_multiple_issues(self):
        text = (
            "My path is /User" + "s/jules/test\n"
            "Also 360/" + "录音\n"
            '"chat_id":' + ' "12345"\n'
            '"sender_open_id":' + ' "user123"\n'
        )
        issues = check_public_repo.content_issues(self.dummy_path, text)
        self.assertEqual(len(issues), 4)
        self.assertIn("contains an absolute macOS home path", issues)
        self.assertIn("contains an internal recording directory", issues)
        self.assertIn("contains a non-placeholder chat_id", issues)
        self.assertIn("contains a non-placeholder sender_open_id", issues)


if __name__ == "__main__":
    unittest.main()
