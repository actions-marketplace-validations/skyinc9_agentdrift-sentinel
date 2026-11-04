"""Rule file discovery engine for agent context & instruction files."""

import glob
import os
from pathlib import Path
from typing import List, Set


# Standard well-known AI agent instruction files across ecosystem
WELL_KNOWN_AGENT_FILES = [
    # Claude & Anthropic
    "CLAUDE.md",
    "CLAUDE_LOCAL.md",
    ".claude/rules/**/*.md",
    # Open Agent Standards
    "AGENTS.md",
    "AGENT.md",
    ".agents/rules/**/*.md",
    ".agents/skills/**/SKILL.md",
    # Cursor
    ".cursorrules",
    ".cursor/rules/**/*.mdc",
    ".cursor/rules/**/*.md",
    # Windsurf (Cascade)
    ".windsurfrules",
    ".windsurf/rules/**/*.md",
    # GitHub Copilot
    ".github/copilot-instructions.md",
    ".copilot/rules/**/*.md",
    # Cline & Roo Code
    ".clinerules",
    ".roomodes",
    ".cline/rules/**/*.md",
    # Gemini & Antigravity
    "GEMINI.md",
    ".gemini/rules/**/*.md",
    # Aider
    "CONVENTIONS.md",
    ".aider.conf.yml",
    # OpenHands & Devin
    "OPENHANDS.md",
    "DEVIN.md",
    ".devin/instructions.md",
    # Trae & Continue
    ".traerules",
    ".trae/rules/**/*.md",
    ".continuerules",
    # Goose
    ".goosehints",
    # Model-Specific Context Files
    "CODEX.md",
    "KIMI.md",
    "QWEN.md",
    "DEEPSEEK.md",
    "VIBE.md",
]


class RuleDetector:
    """Discovers all agent instruction documents within a repository."""

    def __init__(self, repo_root: str, custom_patterns: str = ""):
        self.repo_root = Path(repo_root).resolve()
        self.custom_patterns = [
            p.strip() for p in custom_patterns.replace("\n", ",").split(",") if p.strip()
        ]

    def discover(self) -> List[Path]:
        """Returns a list of resolved Path objects for all matched agent rule files."""
        matched: Set[Path] = set()
        patterns_to_check = self.custom_patterns if self.custom_patterns else WELL_KNOWN_AGENT_FILES

        for pattern in patterns_to_check:
            # Check direct relative path or glob
            full_pattern = str(self.repo_root / pattern)
            for path_str in glob.glob(full_pattern, recursive=True):
                p = Path(path_str).resolve()
                if p.is_file() and p.exists():
                    matched.add(p)

        # Always check well-known files if nothing matched from custom
        if not matched:
            for pattern in WELL_KNOWN_AGENT_FILES:
                full_pattern = str(self.repo_root / pattern)
                for path_str in glob.glob(full_pattern, recursive=True):
                    p = Path(path_str).resolve()
                    if p.is_file() and p.exists():
                        matched.add(p)

        # Sort for deterministic behavior
        return sorted(list(matched))
