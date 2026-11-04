"""Tests for DriftEngine desynchronization detection."""

import json
import tempfile
import unittest
from pathlib import Path
from src.agentdrift.drift_engine import DriftEngine
from src.agentdrift.models import DriftType, Severity
from src.agentdrift.patcher import RulePatcher


class TestDriftEngine(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name).resolve()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_detect_dead_path_on_filesystem(self):
        # Create CLAUDE.md referencing a non-existent internal file
        (self.root / "CLAUDE.md").write_text(
            "Modify `src/legacy_auth.ts` for login handling.", encoding="utf-8"
        )

        engine = DriftEngine(self.root)
        report = engine.run_audit()

        self.assertTrue(report.drift_detected)
        self.assertEqual(len(report.issues), 1)
        issue = report.issues[0]
        self.assertEqual(issue.drift_type, DriftType.DEAD_PATH)
        self.assertEqual(issue.current_reference, "src/legacy_auth.ts")

    def test_detect_renamed_path_with_suggested_fix(self):
        (self.root / "CLAUDE.md").write_text(
            "Please check `src/old_router.ts` for endpoints.", encoding="utf-8"
        )

        engine = DriftEngine(self.root)
        # Simulate git differ having detected a rename
        engine.git_differ.renamed_files["src/old_router.ts"] = "src/routes/index.ts"

        report = engine.run_audit()
        self.assertTrue(report.drift_detected)
        issue = report.issues[0]
        self.assertEqual(issue.drift_type, DriftType.RENAMED_PATH)
        self.assertEqual(issue.severity, Severity.ERROR)
        self.assertIsNotNone(issue.suggested_fix)

        # Test patch generation
        patcher = RulePatcher(self.root)
        patch = patcher.generate_patch(report)
        self.assertIn("-Please check `src/old_router.ts` for endpoints.", patch)
        self.assertIn("+Please check `src/routes/index.ts` for endpoints.", patch)

    def test_detect_deleted_script_in_package_json(self):
        # package.json only has 'build', but rule instructs 'test:unit'
        (self.root / "package.json").write_text(
            json.dumps({"scripts": {"build": "tsc"}}), encoding="utf-8"
        )
        (self.root / ".cursorrules").write_text(
            "Always run `npm run test:unit` before creating PR.", encoding="utf-8"
        )

        engine = DriftEngine(self.root)
        engine.git_differ.deleted_scripts.add("test:unit")

        report = engine.run_audit()
        self.assertTrue(report.drift_detected)
        self.assertTrue(any(i.drift_type == DriftType.DEAD_COMMAND and i.severity == Severity.ERROR for i in report.issues))


if __name__ == "__main__":
    unittest.main()
