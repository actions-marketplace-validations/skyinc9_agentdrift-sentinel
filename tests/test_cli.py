"""Tests for CLI entrypoint."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class TestCLI(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name).resolve()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_cli_clean_repo(self):
        # Create valid file and rule pointing to it
        src_dir = self.root / "src"
        src_dir.mkdir(parents=True, exist_ok=True)
        (src_dir / "app.py").write_text("print('hello')", encoding="utf-8")
        (self.root / "CLAUDE.md").write_text("Entrypoint is `src/app.py`", encoding="utf-8")

        res = subprocess.run(
            [sys.executable, "-m", "src.agentdrift.cli", "--repo-root", str(self.root)],
            cwd=str(Path(__file__).parent.parent),
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("Zero Desync Found", res.stdout)

    def test_cli_failure_on_error(self):
        # Create rule pointing to missing file and flag fail-on-drift
        (self.root / "CLAUDE.md").write_text("Code is in `src/missing.ts`", encoding="utf-8")

        res = subprocess.run(
            [
                sys.executable, "-m", "src.agentdrift.cli",
                "--repo-root", str(self.root),
                "--fail-on-drift", "true",
                "--fail-severity", "warning"
            ],
            cwd=str(Path(__file__).parent.parent),
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(res.returncode, 1)
        self.assertIn("AgentDrift Sentinel failed", res.stdout)

    def test_cli_json_format(self):
        import json
        src_dir = self.root / "src"
        src_dir.mkdir(parents=True, exist_ok=True)
        (src_dir / "index.ts").write_text("export const x = 1;", encoding="utf-8")
        (self.root / "CLAUDE.md").write_text("See `src/index.ts` and `src/ghost.ts`", encoding="utf-8")

        res = subprocess.run(
            [
                sys.executable, "-m", "src.agentdrift.cli",
                "--repo-root", str(self.root),
                "--json"
            ],
            cwd=str(Path(__file__).parent.parent),
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(res.returncode, 0)
        data = json.loads(res.stdout)
        self.assertTrue(data["drift_detected"])
        self.assertEqual(data["drift_count"], 1)
        self.assertEqual(data["issues"][0]["current_reference"], "src/ghost.ts")

    def test_cli_direct_script_execution(self):
        # Verify cli.py can be directly executed as a script (action.yml runner behavior)
        cli_script = Path(__file__).parent.parent / "src" / "agentdrift" / "cli.py"
        res = subprocess.run(
            [sys.executable, str(cli_script), "--repo-root", str(self.root), "--format", "json"],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn('"drift_detected": false', res.stdout)


if __name__ == "__main__":
    unittest.main()
