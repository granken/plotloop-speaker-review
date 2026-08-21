import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SERVE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "serve.py"
SPEC = importlib.util.spec_from_file_location("plotloop_serve", SERVE_PATH)
serve = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(serve)


class ServeTests(unittest.TestCase):
    def test_explicit_confirmed_directory_wins(self):
        with tempfile.TemporaryDirectory() as value:
            target = Path(value) / "confirmed"
            actual = serve.resolve_confirmed_dir(
                {
                    "PLOTLOOP_CONFIRMED_DIR": str(target),
                    "PLOTLOOP_CONFIG": str(Path(value) / "missing.json"),
                }
            )
            self.assertEqual(actual, target.resolve())

    def test_work_target_from_local_config_is_used(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            config = root / "config.json"
            config.write_text(
                json.dumps({"work_target": str(root / "work")}), encoding="utf-8"
            )
            actual = serve.resolve_confirmed_dir({"PLOTLOOP_CONFIG": str(config)})
            self.assertEqual(actual, (root / "work" / "confirmed").resolve())

    def test_default_directory_stays_inside_the_project(self):
        with tempfile.TemporaryDirectory() as value:
            root = Path(value)
            actual = serve.resolve_confirmed_dir(
                {"PLOTLOOP_CONFIG": str(root / "missing.json")}, project_root=root
            )
            self.assertEqual(actual, root.resolve() / ".local" / "confirmed")

    def test_payload_requires_version_two_and_a_nonempty_batch(self):
        valid = {"type": "speaker-review", "version": 2, "batch": [{}]}
        self.assertTrue(serve.NoCacheHandler._valid_payload(valid))
        self.assertFalse(
            serve.NoCacheHandler._valid_payload(
                {"type": "speaker-review", "version": 1, "batch": [{}]}
            )
        )
        self.assertFalse(
            serve.NoCacheHandler._valid_payload(
                {"type": "speaker-review", "version": 2, "batch": []}
            )
        )


if __name__ == "__main__":
    unittest.main()
