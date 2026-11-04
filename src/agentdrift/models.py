"""Data models for AgentDrift Sentinel."""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class DriftType(str, Enum):
    DEAD_PATH = "dead_path"
    RENAMED_PATH = "renamed_path"
    DEAD_COMMAND = "dead_command"
    DEAD_ENV_VAR = "dead_env_var"
    MODIFIED_BEHAVIOR = "modified_behavior"


@dataclass
class RuleReference:
    """A reference found inside an agent instruction file."""
    rule_file: str
    line_number: int
    raw_text: str
    ref_type: str  # 'path', 'command', 'env_var'
    target_value: str
    context_snippet: str = ""


@dataclass
class SuggestedFix:
    """A suggested modification to an agent rule file."""
    rule_file: str
    line_number: int
    original_line: str
    replacement_line: str
    explanation: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_file": self.rule_file,
            "line_number": self.line_number,
            "original_line": self.original_line,
            "replacement_line": self.replacement_line,
            "explanation": self.explanation,
        }


@dataclass
class DriftIssue:
    """An identified desynchronization between agent rules and actual codebase."""
    rule_file: str
    line_number: int
    drift_type: DriftType
    severity: Severity
    title: str
    description: str
    current_reference: str
    suggested_fix: Optional[SuggestedFix] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_file": self.rule_file,
            "line_number": self.line_number,
            "drift_type": self.drift_type.value,
            "severity": self.severity.value,
            "title": self.title,
            "description": self.description,
            "current_reference": self.current_reference,
            "suggested_fix": self.suggested_fix.to_dict() if self.suggested_fix else None,
            "metadata": self.metadata,
        }


@dataclass
class AuditReport:
    """Comprehensive audit report produced by AgentDrift Sentinel."""
    inspected_rule_files: List[str] = field(default_factory=list)
    issues: List[DriftIssue] = field(default_factory=list)
    suggested_patch: str = ""
    git_base_ref: Optional[str] = None
    git_head_ref: Optional[str] = None

    @property
    def drift_detected(self) -> bool:
        return len(self.issues) > 0

    @property
    def error_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == Severity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == Severity.WARNING)

    @property
    def info_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == Severity.INFO)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "drift_detected": self.drift_detected,
            "drift_count": len(self.issues),
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "info_count": self.info_count,
            "inspected_rule_files": self.inspected_rule_files,
            "git_base_ref": self.git_base_ref,
            "issues": [issue.to_dict() for issue in self.issues],
            "suggested_patch": self.suggested_patch,
        }
