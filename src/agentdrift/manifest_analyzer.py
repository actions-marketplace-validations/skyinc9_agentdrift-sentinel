"""Manifest analyzer to index valid commands, scripts, targets, and env vars."""

import json
import re
from pathlib import Path
from typing import Set, Dict, Any


MAKEFILE_TARGET_REGEX = re.compile(r"^([a-zA-Z0-9_\-]+)\s*:", re.MULTILINE)
ENV_FILE_VAR_REGEX = re.compile(r"^\s*([A-Z0-9_]+)\s*=", re.MULTILINE)


class ManifestAnalyzer:
    """Extracts known scripts, targets, and environment variables from repo manifests."""

    def __init__(self, repo_root: Path):
        self.repo_root = Path(repo_root).resolve()
        self.npm_scripts: Set[str] = set()
        self.make_targets: Set[str] = set()
        self.env_vars: Set[str] = set()
        self.analyzed = False

    def analyze(self) -> None:
        """Parses all discovered manifests in the workspace."""
        if self.analyzed:
            return

        self._parse_package_jsons()
        self._parse_makefiles()
        self._parse_env_examples()
        self.analyzed = True

    def _parse_package_jsons(self) -> None:
        """Finds root and workspace package.json files."""
        for pkg_path in self.repo_root.glob("**/package.json"):
            # skip node_modules
            if "node_modules" in pkg_path.parts:
                continue
            try:
                data = json.loads(pkg_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    scripts = data.get("scripts", {})
                    if isinstance(scripts, dict):
                        for script_name in scripts.keys():
                            self.npm_scripts.add(script_name)
            except Exception:
                pass

    def _parse_makefiles(self) -> None:
        """Finds Makefile files in the repository."""
        for make_path in [self.repo_root / "Makefile", self.repo_root / "makefile"]:
            if make_path.exists() and make_path.is_file():
                try:
                    content = make_path.read_text(encoding="utf-8", errors="ignore")
                    for match in MAKEFILE_TARGET_REGEX.finditer(content):
                        target = match.group(1).strip()
                        if not target.startswith("."):
                            self.make_targets.add(target)
                except Exception:
                    pass

    def _parse_env_examples(self) -> None:
        """Finds sample env files (.env.example, .env.sample, etc.)."""
        sample_names = [".env.example", ".env.sample", ".env.template", ".env.dist"]
        for name in sample_names:
            for env_path in self.repo_root.glob(f"**/{name}"):
                if "node_modules" in env_path.parts:
                    continue
                try:
                    content = env_path.read_text(encoding="utf-8", errors="ignore")
                    for match in ENV_FILE_VAR_REGEX.finditer(content):
                        self.env_vars.add(match.group(1).strip())
                except Exception:
                    pass
