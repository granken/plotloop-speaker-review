import subprocess
import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class ManageLaunchdTests(unittest.TestCase):
    def test_script_can_be_run_directly(self):
        result = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "scripts" / "manage_launchd.py"), "--help"],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("render", result.stdout)


if __name__ == "__main__":
    unittest.main()
