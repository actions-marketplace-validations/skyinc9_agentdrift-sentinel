"""Core evaluation engine that correlates agent rules with codebase state."""

import os
from pathlib import Path
from typing import List, Optional
from .detector import RuleDetector
from .git_differ import GitDiffer
from .manifest_analyzer import ManifestAnalyzer
from .models import AuditReport, DriftIssue, DriftType, Severity, SuggestedFix
from .parser import RuleParser


INTERNAL_PATH_PREFIXES = (
    "src/", "lib/", "app/", "test/", "tests/", "pkg/", "scripts/", "config/",
    "components/", "pages/", "routes/", "models/", "services/", "controllers/",
    "docs/", "bin/", "utils/", "helpers/", "core/", "internal/"
)


class DriftEngine:
    """Audits agent instruction files and generates desync reports."""

    def __init__(
        self,
        repo_root: Path,
        custom_rules_paths: str = "",
        base_ref: Optional[str] = None,
        check_paths: bool = True,
        check_commands: bool = True,
        check_env_vars: bool = True,
    ):
        self.repo_root = Path(repo_root).resolve()
        self.custom_rules_paths = custom_rules_paths
        self.base_ref = base_ref
        self.check_paths = check_paths
        self.check_commands = check_commands
        self.check_env_vars = check_env_vars

        self.detector = RuleDetector(str(self.repo_root), custom_rules_paths)
        self.parser = RuleParser(self.repo_root)
        self.manifest_analyzer = ManifestAnalyzer(self.repo_root)
        self.git_differ = GitDiffer(self.repo_root, base_ref)

    def run_audit(self) -> AuditReport:
        """Executes the full desync analysis across discovered rule files."""
        self.manifest_analyzer.analyze()
        self.git_differ.analyze()

        rule_files = self.detector.discover()
        inspected = []
        for p in rule_files:
            try:
                rel = p.resolve().relative_to(self.repo_root)
            except ValueError:
                try:
                    rel = p.relative_to(self.repo_root)
                except ValueError:
                    rel = os.path.relpath(str(p), str(self.repo_root))
            inspected.append(str(rel).replace("\\", "/"))

        report = AuditReport(
            inspected_rule_files=inspected,
            git_base_ref=self.git_differ.base_ref,
        )

        for rule_path in rule_files:
            references = self.parser.parse_file(rule_path)
            for ref in references:
                issue = self._evaluate_reference(ref)
                if issue:
                    report.issues.append(issue)

        return report

    def _evaluate_reference(self, ref) -> Optional[DriftIssue]:
        """Evaluates a single rule reference against repository state."""
        rel_target = ref.target_value.replace("\\", "/")

        # 1. Path Reference Audits
        if ref.ref_type == "path" and self.check_paths:
            # Case A: Renamed in PR
            if rel_target in self.git_differ.renamed_files:
                new_path = self.git_differ.renamed_files[rel_target]
                replacement_line = ref.raw_text.replace(ref.target_value, new_path)
                return DriftIssue(
                    rule_file=ref.rule_file,
                    line_number=ref.line_number,
                    drift_type=DriftType.RENAMED_PATH,
                    severity=Severity.ERROR,
                    title=f"Renamed file referenced in {ref.rule_file}:{ref.line_number}",
                    description=f"File `{rel_target}` was renamed to `{new_path}` in this PR, but agent rules still point to the old path.",
                    current_reference=ref.target_value,
                    suggested_fix=SuggestedFix(
                        rule_file=ref.rule_file,
                        line_number=ref.line_number,
                        original_line=ref.raw_text,
                        replacement_line=replacement_line,
                        explanation=f"Update reference `{rel_target}` -> `{new_path}`",
                    ),
                    metadata={"old_path": rel_target, "new_path": new_path},
                )

            # Case B: Deleted in PR
            if rel_target in self.git_differ.deleted_files:
                return DriftIssue(
                    rule_file=ref.rule_file,
                    line_number=ref.line_number,
                    drift_type=DriftType.DEAD_PATH,
                    severity=Severity.ERROR,
                    title=f"Deleted file referenced in {ref.rule_file}:{ref.line_number}",
                    description=f"File `{rel_target}` was deleted in this PR, causing agents to target non-existent code.",
                    current_reference=ref.target_value,
                    suggested_fix=None,
                    metadata={"deleted_path": rel_target},
                )

            # Case C: General dead path on filesystem
            target_fs_path = self.repo_root / rel_target
            if not target_fs_path.exists():
                # Only flag if it clearly looks like an internal path
                is_internal = (
                    rel_target.startswith(INTERNAL_PATH_PREFIXES)
                    or any(rel_target.endswith(ext) for ext in [".ts", ".tsx", ".js", ".jsx", ".py", ".go", ".rs", ".json"])
                )
                # Ignore rule files referencing themselves or standard git docs
                if is_internal and not rel_target.startswith(".git/"):
                    return DriftIssue(
                        rule_file=ref.rule_file,
                        line_number=ref.line_number,
                        drift_type=DriftType.DEAD_PATH,
                        severity=Severity.WARNING,
                        title=f"Unresolved file path in {ref.rule_file}:{ref.line_number}",
                        description=f"Path `{rel_target}` does not exist in the repository.",
                        current_reference=ref.target_value,
                    )

        # 2. Command / Script Audits
        elif ref.ref_type == "command" and self.check_commands:
            script_name = ref.target_value
            # Case A: Deleted in this PR
            if script_name in self.git_differ.deleted_scripts:
                return DriftIssue(
                    rule_file=ref.rule_file,
                    line_number=ref.line_number,
                    drift_type=DriftType.DEAD_COMMAND,
                    severity=Severity.ERROR,
                    title=f"Deleted script `{script_name}` instructed in {ref.rule_file}:{ref.line_number}",
                    description=f"The script `{script_name}` was removed from `package.json` in this PR, but agent instructions still tell the AI to execute it.",
                    current_reference=script_name,
                )

            # Case B: Manifest exists but script is missing
            if self.manifest_analyzer.npm_scripts and script_name not in self.manifest_analyzer.npm_scripts:
                # Exclude common built-in commands like test, start
                if script_name not in {"test", "start", "build"}:
                    return DriftIssue(
                        rule_file=ref.rule_file,
                        line_number=ref.line_number,
                        drift_type=DriftType.DEAD_COMMAND,
                        severity=Severity.WARNING,
                        title=f"Undefined script `{script_name}` in {ref.rule_file}:{ref.line_number}",
                        description=f"Script `{script_name}` is not defined in any `package.json` `scripts` block.",
                        current_reference=script_name,
                    )

        # 3. Makefile Targets
        elif ref.ref_type == "make_target" and self.check_commands:
            target_name = ref.target_value
            if self.manifest_analyzer.make_targets and target_name not in self.manifest_analyzer.make_targets:
                return DriftIssue(
                    rule_file=ref.rule_file,
                    line_number=ref.line_number,
                    drift_type=DriftType.DEAD_COMMAND,
                    severity=Severity.WARNING,
                    title=f"Undefined Makefile target `{target_name}` in {ref.rule_file}:{ref.line_number}",
                    description=f"Target `{target_name}` was not found in `Makefile`.",
                    current_reference=target_name,
                )

        # 4. Environment Variables
        elif ref.ref_type == "env_var" and self.check_env_vars:
            var_name = ref.target_value
            # Standard common system env vars to skip
            if var_name in {"NODE_ENV", "PATH", "PORT", "HOST", "CI", "DEBUG", "HOME", "USER"}:
                return None
            if self.manifest_analyzer.env_vars and var_name not in self.manifest_analyzer.env_vars:
                return DriftIssue(
                    rule_file=ref.rule_file,
                    line_number=ref.line_number,
                    drift_type=DriftType.DEAD_ENV_VAR,
                    severity=Severity.INFO,
                    title=f"Unregistered environment variable `{var_name}` in {ref.rule_file}:{ref.line_number}",
                    description=f"Environment variable `{var_name}` is mentioned in agent rules but missing from `.env.example`.",
                    current_reference=var_name,
                )

        return None
