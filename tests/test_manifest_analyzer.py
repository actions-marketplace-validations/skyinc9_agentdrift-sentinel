"""Tests for ManifestAnalyzer."""

import json
import tempfile
import unittest
from pathlib import Path
from src.agentdrift.manifest_analyzer import ManifestAnalyzer


class TestManifestAnalyzer(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name).resolve()
        self.analyzer = ManifestAnalyzer(self.root)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_extract_package_json_scripts(self):
        pkg = self.root / "package.json"
        pkg.write_text(
            json.dumps({"name": "test", "scripts": {"build": "tsc", "test:ci": "jest", "lint": "eslint ."}}),
            encoding="utf-8"
        )

        self.analyzer.analyze()
        self.assertIn("build", self.analyzer.npm_scripts)
        self.assertIn("test:ci", self.analyzer.npm_scripts)
        self.assertIn("lint", self.analyzer.npm_scripts)

    def test_extract_makefile_targets(self):
        makefile = self.root / "Makefile"
        makefile.write_text(
            "all: build test\n\nbuild:\n\t@go build\n\ntest-unit:\n\t@go test\n",
            encoding="utf-8"
        )

        self.analyzer.analyze()
        self.assertIn("all", self.analyzer.make_targets)
        self.assertIn("build", self.analyzer.make_targets)
        self.assertIn("test-unit", self.analyzer.make_targets)

    def test_extract_env_example_vars(self):
        env_ex = self.root / ".env.example"
        env_ex.write_text(
            "PORT=3000\nDATABASE_URL=postgres://localhost/db\nAPI_KEY=secret_key\n",
            encoding="utf-8"
        )

        self.analyzer.analyze()
        self.assertIn("PORT", self.analyzer.env_vars)
        self.assertIn("DATABASE_URL", self.analyzer.env_vars)
        self.assertIn("API_KEY", self.analyzer.env_vars)


if __name__ == "__main__":
    unittest.main()
