"""Tests for RuleDetector."""

import tempfile
import unittest
from pathlib import Path
from src.agentdrift.detector import RuleDetector


class TestRuleDetector(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name).resolve()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_discover_standard_claude_and_cursorrules(self):
        (self.root / "CLAUDE.md").write_text("# Claude instructions", encoding="utf-8")
        (self.root / ".cursorrules").write_text("# Cursor rules", encoding="utf-8")
        (self.root / "README.md").write_text("# Readme", encoding="utf-8")

        detector = RuleDetector(str(self.root))
        discovered = detector.discover()
        discovered_names = [p.name for p in discovered]

        self.assertIn("CLAUDE.md", discovered_names)
        self.assertIn(".cursorrules", discovered_names)
        self.assertNotIn("README.md", discovered_names)

    def test_discover_agents_md_and_nested_rules(self):
        (self.root / "AGENTS.md").write_text("# Agents standard", encoding="utf-8")
        rules_dir = self.root / ".cursor" / "rules"
        rules_dir.mkdir(parents=True, exist_ok=True)
        (rules_dir / "frontend.mdc").write_text("# Frontend rules", encoding="utf-8")

        detector = RuleDetector(str(self.root))
        discovered = detector.discover()
        discovered_names = [p.name for p in discovered]

        self.assertIn("AGENTS.md", discovered_names)
        self.assertIn("frontend.mdc", discovered_names)

    def test_discover_expanded_45_agent_ecosystem_rules(self):
        # Create rule files across different agent tools
        (self.root / ".windsurfrules").write_text("# Windsurf Cascade rules", encoding="utf-8")
        (self.root / ".clinerules").write_text("# Cline rules", encoding="utf-8")
        (self.root / ".roomodes").write_text("# Roo Code custom modes", encoding="utf-8")
        (self.root / "OPENHANDS.md").write_text("# OpenHands repo guidelines", encoding="utf-8")
        (self.root / "DEVIN.md").write_text("# Devin guidelines", encoding="utf-8")
        (self.root / "CONVENTIONS.md").write_text("# Aider conventions", encoding="utf-8")
        (self.root / ".traerules").write_text("# Trae rules", encoding="utf-8")
        (self.root / ".continuerules").write_text("# Continue rules", encoding="utf-8")
        (self.root / "CODEX.md").write_text("# Codex prompt instructions", encoding="utf-8")

        detector = RuleDetector(str(self.root))
        discovered = detector.discover()
        discovered_names = {p.name for p in discovered}

        expected = {
            ".windsurfrules",
            ".clinerules",
            ".roomodes",
            "OPENHANDS.md",
            "DEVIN.md",
            "CONVENTIONS.md",
            ".traerules",
            ".continuerules",
            "CODEX.md",
        }
        for name in expected:
            self.assertIn(name, discovered_names)

    def test_custom_rule_paths(self):
        custom_dir = self.root / "prompts"
        custom_dir.mkdir(parents=True, exist_ok=True)
        (custom_dir / "system.md").write_text("# Custom Prompt", encoding="utf-8")

        detector = RuleDetector(str(self.root), custom_patterns="prompts/*.md")
        discovered = detector.discover()
        self.assertEqual(len(discovered), 1)
        self.assertEqual(discovered[0].name, "system.md")


if __name__ == "__main__":
    unittest.main()
