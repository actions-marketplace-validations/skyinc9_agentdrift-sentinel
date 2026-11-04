"""Parser for extracting code, path, command, and env var references from agent rule files."""

import os
import re
from pathlib import Path
from typing import List
from .models import RuleReference

# Regex patterns for path references
PATH_IN_BACKTICKS = re.compile(r"`([a-zA-Z0-9_\-\./]+(?:/[a-zA-Z0-9_\-\./]+|\.[a-zA-Z0-9_]+))`")
MARKDOWN_LINK_PATH = re.compile(r"\[.*?\]\((?!https?://)(?!#)([a-zA-Z0-9_\-\./]+)\)")
STANDALONE_PATH = re.compile(
    r"(?:^|[\s(])([a-zA-Z0-9_\-\.]+(?:/[a-zA-Z0-9_\-\.]+)+\.[a-zA-Z0-9_]+)(?:[\s):]|$)"
)

# Common extensions indicating files
KNOWN_EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".json", ".yaml", ".yml",
    ".toml", ".sh", ".bash", ".rs", ".go", ".cpp", ".c", ".h", ".hpp", ".java",
    ".rb", ".php", ".css", ".scss", ".html", ".sql", ".md", ".env", ".lock"
}

# Regex for shell commands and package scripts
NPM_SCRIPT_REGEX = re.compile(
    r"`?(?:npm|pnpm|yarn|bun)(?:\s+run)?\s+([a-zA-Z0-9_\-:]+)`?", re.IGNORECASE
)
MAKE_TARGET_REGEX = re.compile(r"`?make\s+([a-zA-Z0-9_\-]+)`?", re.IGNORECASE)

# Regex for environment variables
ENV_VAR_REGEX = re.compile(r"`?([A-Z][A-Z0-9_]{2,40})`?")
PROCESS_ENV_REGEX = re.compile(r"process\.env\.([A-Z0-9_]+)")
OS_ENV_REGEX = re.compile(r'os\.environ\[?[\'"]([A-Z0-9_]+)[\'"]\]?')


class RuleParser:
    """Extracts verifiable entities from agent rule files."""

    def __init__(self, repo_root: Path):
        self.repo_root = Path(repo_root).resolve()

    def parse_file(self, file_path: Path) -> List[RuleReference]:
        """Parses a rule file and returns all identified references."""
        references: List[RuleReference] = []
        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                content = file_path.read_text(encoding="latin-1")
            except Exception:
                return references

        lines = content.splitlines()
        try:
            rel_rule_file = str(file_path.resolve().relative_to(self.repo_root)).replace("\\", "/")
        except ValueError:
            try:
                rel_rule_file = str(file_path.relative_to(self.repo_root)).replace("\\", "/")
            except ValueError:
                rel_rule_file = os.path.relpath(str(file_path), str(self.repo_root)).replace("\\", "/")

        in_code_block = False

        for idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            if stripped.startswith("```"):
                in_code_block = not in_code_block

            # 1. Path references
            # From backticks
            for match in PATH_IN_BACKTICKS.finditer(line):
                candidate = match.group(1).strip()
                if self._is_valid_path_candidate(candidate):
                    references.append(
                        RuleReference(
                            rule_file=rel_rule_file,
                            line_number=idx,
                            raw_text=line,
                            ref_type="path",
                            target_value=self._normalize_path(candidate),
                            context_snippet=line.strip(),
                        )
                    )

            # From markdown links
            for match in MARKDOWN_LINK_PATH.finditer(line):
                candidate = match.group(1).strip()
                if self._is_valid_path_candidate(candidate):
                    references.append(
                        RuleReference(
                            rule_file=rel_rule_file,
                            line_number=idx,
                            raw_text=line,
                            ref_type="path",
                            target_value=self._normalize_path(candidate),
                            context_snippet=line.strip(),
                        )
                    )

            # 2. Command & script references
            for match in NPM_SCRIPT_REGEX.finditer(line):
                script_name = match.group(1).strip()
                if script_name not in {"run", "install", "i", "add", "remove", "publish", "exec"}:
                    references.append(
                        RuleReference(
                            rule_file=rel_rule_file,
                            line_number=idx,
                            raw_text=line,
                            ref_type="command",
                            target_value=script_name,
                            context_snippet=line.strip(),
                        )
                    )

            for match in MAKE_TARGET_REGEX.finditer(line):
                target_name = match.group(1).strip()
                if target_name not in {"-f", "-j", "-B"}:
                    references.append(
                        RuleReference(
                            rule_file=rel_rule_file,
                            line_number=idx,
                            raw_text=line,
                            ref_type="make_target",
                            target_value=target_name,
                            context_snippet=line.strip(),
                        )
                    )

            # 3. Environment variables
            for match in PROCESS_ENV_REGEX.finditer(line):
                var_name = match.group(1).strip()
                references.append(
                    RuleReference(
                        rule_file=rel_rule_file,
                        line_number=idx,
                        raw_text=line,
                        ref_type="env_var",
                        target_value=var_name,
                        context_snippet=line.strip(),
                    )
                )

            for match in OS_ENV_REGEX.finditer(line):
                var_name = match.group(1).strip()
                references.append(
                    RuleReference(
                        rule_file=rel_rule_file,
                        line_number=idx,
                        raw_text=line,
                        ref_type="env_var",
                        target_value=var_name,
                        context_snippet=line.strip(),
                    )
                )

        return references

    def _is_valid_path_candidate(self, candidate: str) -> bool:
        """Filters out non-path strings like versions, CLI flags, words with dots."""
        if not candidate or len(candidate) < 2:
            return False
        if candidate.startswith("-") or candidate.startswith("@"):
            return False
        if "http://" in candidate or "https://" in candidate:
            return False
        if candidate.startswith("v1") or candidate.startswith("v2") or candidate.startswith("0."):
            return False
        # Ignore semantic versions or common words like e.g., i.e.
        if candidate in {"e.g.", "i.e.", "etc.", "true", "false", "null", "undefined"}:
            return False
        # Must have a slash or a known file extension
        has_slash = "/" in candidate or "\\" in candidate
        has_ext = any(candidate.lower().endswith(ext) for ext in KNOWN_EXTENSIONS)
        return has_slash or has_ext

    def _normalize_path(self, path_str: str) -> str:
        """Strips leading ./ and standardizes slashes."""
        p = path_str.replace("\\", "/")
        if p.startswith("./"):
            p = p[2:]
        return p.rstrip("/")
