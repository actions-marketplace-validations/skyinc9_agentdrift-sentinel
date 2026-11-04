"""Git diff inspection engine to identify deleted, renamed, and altered files."""

import json
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


class GitDiffer:
    """Extracts git change metadata between base_ref and current HEAD."""

    def __init__(self, repo_root: Path, base_ref: Optional[str] = None):
        self.repo_root = Path(repo_root).resolve()
        self.base_ref = base_ref or self._infer_base_ref()
        self.deleted_files: Set[str] = set()
        self.renamed_files: Dict[str, str] = {}  # old_path -> new_path
        self.modified_files: Set[str] = set()
        self.deleted_scripts: Set[str] = set()
        self.analyzed = False

    def _infer_base_ref(self) -> str:
        """Determines best comparison ref (origin/main, origin/master, or HEAD~1)."""
        candidates = ["origin/main", "origin/master", "main", "master", "HEAD~1"]
        for ref in candidates:
            res = self._run_git(["rev-parse", "--verify", ref])
            if res is not None:
                return ref
        return "HEAD"

    def _run_git(self, args: List[str]) -> Optional[str]:
        """Runs a git command safely in repo_root."""
        try:
            res = subprocess.run(
                ["git"] + args,
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode == 0:
                return res.stdout.strip()
            return None
        except Exception:
            return None

    def analyze(self) -> None:
        """Runs git diff name-status to detect deleted and renamed files."""
        if self.analyzed:
            return

        if not self.base_ref or self.base_ref == "HEAD":
            self.analyzed = True
            return

        # git diff --name-status -M base_ref...HEAD
        # -M enables rename detection
        output = self._run_git(["diff", "--name-status", "-M", f"{self.base_ref}...HEAD"])
        if not output:
            output = self._run_git(["diff", "--name-status", "-M", f"{self.base_ref}"])

        if output:
            for line in output.splitlines():
                parts = line.strip().split("\t")
                if not parts:
                    continue
                status = parts[0]
                if status.startswith("D") and len(parts) >= 2:
                    self.deleted_files.add(parts[1].replace("\\", "/"))
                elif status.startswith("R") and len(parts) >= 3:
                    old_path = parts[1].replace("\\", "/")
                    new_path = parts[2].replace("\\", "/")
                    self.renamed_files[old_path] = new_path
                elif status.startswith("M") and len(parts) >= 2:
                    self.modified_files.add(parts[1].replace("\\", "/"))

        # Check for deleted package.json scripts between base_ref and HEAD
        self._check_deleted_scripts()
        self.analyzed = True

    def _check_deleted_scripts(self) -> None:
        """Checks if package.json in base_ref had scripts that were removed in HEAD."""
        base_pkg_content = self._run_git(["show", f"{self.base_ref}:package.json"])
        head_pkg_path = self.repo_root / "package.json"

        if base_pkg_content and head_pkg_path.exists():
            try:
                base_data = json.loads(base_pkg_content)
                head_data = json.loads(head_pkg_path.read_text(encoding="utf-8"))
                base_scripts = set(base_data.get("scripts", {}).keys())
                head_scripts = set(head_data.get("scripts", {}).keys())
                self.deleted_scripts = base_scripts - head_scripts
            except Exception:
                pass
