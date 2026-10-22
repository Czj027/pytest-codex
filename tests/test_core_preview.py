"""Smoke tests for the public functionality shipped in the initial release."""

import importlib
import tempfile
import unittest
from pathlib import Path


class CorePreviewTests(unittest.TestCase):
    def test_package_import_and_event_trace(self):
        package = importlib.import_module("pytest_codex")
        self.assertEqual(package.__version__, "0.1.0")
        events = importlib.import_module("pytest_codex.events")
        trace = events.parse_jsonl(
            '{"type":"item.completed","item":{"id":"1",'
            '"type":"command_execution","command":"uv add requests",'
            '"exit_code":0}}\n'
            '{"type":"turn.completed","usage":{"input_tokens":10,"output_tokens":3}}'
        )
        commands = events.build_items(trace)
        self.assertEqual(commands[0].command, "uv add requests")
        self.assertTrue(commands[0].ok)
        self.assertEqual(events.total_usage(trace).total, 13)

    def test_snapshot_detects_shell_style_file_changes(self):
        snapshots = importlib.import_module("pytest_codex.snapshot")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "config.txt").write_text("old", encoding="utf-8")
            (root / "removed.txt").write_text("delete", encoding="utf-8")
            before = snapshots.snapshot(root)
            (root / "config.txt").write_text("new", encoding="utf-8")
            (root / "removed.txt").unlink()
            (root / "added.txt").write_text("added", encoding="utf-8")
            change = snapshots.diff(before, snapshots.snapshot(root))
            self.assertEqual(
                change.to_dict(),
                {
                    "added": ["added.txt"],
                    "modified": ["config.txt"],
                    "deleted": ["removed.txt"],
                },
            )


if __name__ == "__main__":
    unittest.main()
