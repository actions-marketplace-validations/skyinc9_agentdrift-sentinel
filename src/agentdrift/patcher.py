"""Auto-fix and unified diff generation for desynchronized agent instructions."""

import difflib
from pathlib import Path
from typing import Dict, List
from .models import AuditReport, SuggestedFix


class RulePatcher:
    """Generates suggested unified diff patches to update agent instruction files."""

    def __init__(self, repo_root: Path):
        self.repo_root = Path(repo_root).resolve()

    def generate_patch(self, report: AuditReport) -> str:
        """Computes a unified git diff applying all available suggested fixes."""
        fixes_by_file: Dict[str, List[SuggestedFix]] = {}
        for issue in report.issues:
            if issue.suggested_fix:
                rule_file = issue.suggested_fix.rule_file
                fixes_by_file.setdefault(rule_file, []).append(issue.suggested_fix)

        if not fixes_by_file:
            return ""

        diff_chunks: List[str] = []

        for rel_file, fixes in fixes_by_file.items():
            file_path = self.repo_root / rel_file
            if not file_path.exists():
                continue

            try:
                original_content = file_path.read_text(encoding="utf-8")
            except Exception:
                continue

            lines = original_content.splitlines(keepends=True)
            modified_lines = list(lines)

            # Apply fixes by line index (1-based to 0-based)
            for fix in fixes:
                idx = fix.line_number - 1
                if 0 <= idx < len(modified_lines):
                    # Replace line content while maintaining trailing newline
                    has_newline = modified_lines[idx].endswith("\n")
                    new_line = fix.replacement_line + ("\n" if has_newline else "")
                    modified_lines[idx] = new_line

            diff = difflib.unified_diff(
                lines,
                modified_lines,
                fromfile=f"a/{rel_file}",
                tofile=f"b/{rel_file}",
            )
            diff_text = "".join(diff)
            if diff_text:
                diff_chunks.append(diff_text)

        patch_str = "\n".join(diff_chunks)
        report.suggested_patch = patch_str
        return patch_str
