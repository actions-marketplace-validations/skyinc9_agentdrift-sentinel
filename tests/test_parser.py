"""Tests for RuleParser."""

import tempfile
import unittest
from pathlib import Path
from src.agentdrift.parser import RuleParser


class TestRuleParser(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name).resolve()
        self.parser = RuleParser(self.root)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_parse_file_paths(self):
        rule_file = self.root / "CLAUDE.md"
        rule_file.write_text(
            "# Guidelines\n"
            "Main code lives in `src/index.ts` and config is at [Default Config](config/settings.json).\n"
            "Always consult `docs/architecture.md`.\n",
            encoding="utf-8"
        )

        refs = self.parser.parse_file(rule_file)
        path_refs = [r.target_value for r in refs if r.ref_type == "path"]

        self.assertIn("src/index.ts", path_refs)
        self.assertIn("config/settings.json", path_refs)
        self.assertIn("docs/architecture.md", path_refs)

    def test_parse_commands_and_scripts(self):
        rule_file = self.root / ".cursorrules"
        rule_file.write_text(
            "Before pushing, run `npm run lint:fix`.\n"
            "For tests, use `pnpm test:unit` and `make build`.\n",
            encoding="utf-8"
        )

        refs = self.parser.parse_file(rule_file)
        cmd_refs = [r.target_value for r in refs if r.ref_type == "command"]
        make_refs = [r.target_value for r in refs if r.ref_type == "make_target"]

        self.assertIn("lint:fix", cmd_refs)
        self.assertIn("test:unit", cmd_refs)
        self.assertIn("build", make_refs)

    def test_parse_env_vars(self):
        rule_file = self.root / "AGENTS.md"
        rule_file.write_text(
            "Authentication requires process.env.AUTH_SECRET and os.environ['DATABASE_URL'].\n",
            encoding="utf-8"
        )

        refs = self.parser.parse_file(rule_file)
        env_refs = [r.target_value for r in refs if r.ref_type == "env_var"]

        self.assertIn("AUTH_SECRET", env_refs)
        self.assertIn("DATABASE_URL", env_refs)


if __name__ == "__main__":
    unittest.main()
