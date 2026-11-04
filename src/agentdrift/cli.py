"""Command-line interface entry point for AgentDrift Sentinel."""

import argparse
import os
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from agentdrift.drift_engine import DriftEngine
    from agentdrift.models import Severity
    from agentdrift.patcher import RulePatcher
    from agentdrift.reporter import Reporter
else:
    from .drift_engine import DriftEngine
    from .models import Severity
    from .patcher import RulePatcher
    from .reporter import Reporter


def str_to_bool(val: str, default: bool = False) -> bool:
    """Converts a string representation to a boolean."""
    if not val:
        return default
    return val.strip().lower() in {"true", "1", "yes", "on"}


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(
        description="AgentDrift Sentinel: AI Instruction-Code Desynchronization Guard."
    )
    parser.add_argument(
        "--repo-root",
        default=os.getenv("GITHUB_WORKSPACE", "."),
        help="Root directory of the repository to audit.",
    )
    parser.add_argument(
        "--rules-paths",
        default=os.getenv("INPUT_RULES_PATHS", ""),
        help="Comma or newline-separated file paths or glob patterns for agent instruction files.",
    )
    parser.add_argument(
        "--base-ref",
        default=os.getenv("INPUT_BASE_REF", ""),
        help="Base git reference or commit SHA to diff against.",
    )
    parser.add_argument(
        "--fail-on-drift",
        default=os.getenv("INPUT_FAIL_ON_DRIFT", "false"),
        help="Whether to exit with a non-zero exit code if drift is detected.",
    )
    parser.add_argument(
        "--fail-severity",
        default=os.getenv("INPUT_FAIL_SEVERITY", "error"),
        choices=["error", "warning", "info"],
        help="Minimum severity level required to trigger failure.",
    )
    parser.add_argument(
        "--auto-suggest-fixes",
        default=os.getenv("INPUT_AUTO_SUGGEST_FIXES", "true"),
        help="Generate unified diff patch for desynced rules.",
    )
    parser.add_argument(
        "--comment-on-pr",
        default=os.getenv("INPUT_COMMENT_ON_PR", "true"),
        help="Whether to post a comment to the pull request.",
    )
    parser.add_argument(
        "--github-token",
        default=os.getenv("INPUT_GITHUB_TOKEN", os.getenv("GITHUB_TOKEN", "")),
        help="GitHub token for API calls.",
    )
    parser.add_argument(
        "--check-paths",
        default=os.getenv("INPUT_CHECK_PATHS", "true"),
        help="Verify file and directory paths referenced in rules.",
    )
    parser.add_argument(
        "--check-commands",
        default=os.getenv("INPUT_CHECK_COMMANDS", "true"),
        help="Verify npm scripts, Makefile targets, and commands.",
    )
    parser.add_argument(
        "--check-env-vars",
        default=os.getenv("INPUT_CHECK_ENV_VARS", "true"),
        help="Verify environment variables mentioned in rules.",
    )
    parser.add_argument(
        "--format",
        default=os.getenv("INPUT_OUTPUT_FORMAT", "markdown"),
        choices=["markdown", "json"],
        help="Output format to display to stdout ('markdown' or 'json').",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Shortcut to output structured JSON for AI bots and tools.",
    )

    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    fail_on_drift = str_to_bool(args.fail_on_drift, False)
    auto_suggest_fixes = str_to_bool(args.auto_suggest_fixes, True)
    comment_on_pr = str_to_bool(args.comment_on_pr, True)
    check_paths = str_to_bool(args.check_paths, True)
    check_commands = str_to_bool(args.check_commands, True)
    check_env_vars = str_to_bool(args.check_env_vars, True)
    output_format = "json" if args.json else args.format.lower()

    if output_format != "json":
        print("🛡️  Starting AgentDrift Sentinel Audit...")
        print(f"📁 Repository Root: {repo_root}")

    engine = DriftEngine(
        repo_root=repo_root,
        custom_rules_paths=args.rules_paths,
        base_ref=args.base_ref or None,
        check_paths=check_paths,
        check_commands=check_commands,
        check_env_vars=check_env_vars,
    )

    report = engine.run_audit()

    if auto_suggest_fixes:
        patcher = RulePatcher(repo_root)
        patcher.generate_patch(report)

    reporter = Reporter(repo_root, report)
    summary_markdown = reporter.render_markdown_summary()

    if output_format == "json":
        import json
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print("\n" + summary_markdown + "\n")

    # Workflow integrations
    reporter.write_step_summary()
    if output_format != "json":
        reporter.emit_workflow_annotations()
    reporter.write_github_outputs()

    if comment_on_pr and args.github_token:
        reporter.post_pr_comment(args.github_token)

    # Determine exit code
    if fail_on_drift and report.drift_detected:
        if args.fail_severity == "error" and report.error_count > 0:
            print(f"::error::AgentDrift Sentinel failed: {report.error_count} high-severity instruction desync error(s) found.")
            return 1
        elif args.fail_severity == "warning" and (report.error_count > 0 or report.warning_count > 0):
            print(f"::error::AgentDrift Sentinel failed: {report.error_count + report.warning_count} instruction desync issue(s) found.")
            return 1
        elif args.fail_severity == "info":
            print(f"::error::AgentDrift Sentinel failed: {len(report.issues)} instruction desync issue(s) found.")
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
