"""Reporter module for GitHub Actions summaries, annotations, PR comments, and outputs."""

import json
import os
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional
from .models import AuditReport, Severity


COMMENT_TAG = "<!-- agentdrift-sentinel-report -->"


class Reporter:
    """Formats and publishes desync findings to GitHub Actions environment."""

    def __init__(self, repo_root: Path, report: AuditReport):
        self.repo_root = Path(repo_root).resolve()
        self.report = report

    def render_markdown_summary(self) -> str:
        """Generates a rich GitHub Markdown summary."""
        lines = []
        status_emoji = "🚨" if self.report.error_count > 0 else ("⚠️" if self.report.warning_count > 0 else "✅")
        status_text = "Instruction Desync Detected" if self.report.drift_detected else "All Agent Rules In Sync"

        lines.append(f"## {status_emoji} AgentDrift Sentinel: {status_text}")
        lines.append("")
        lines.append(
            f"**Inspected Rule Files:** `{len(self.report.inspected_rule_files)}` | "
            f"**Errors:** `{self.report.error_count}` | "
            f"**Warnings:** `{self.report.warning_count}` | "
            f"**Info:** `{self.report.info_count}`"
        )
        lines.append("")

        if not self.report.drift_detected:
            lines.append("> 🎯 **Zero Desync Found.** All file paths, package commands, and environment variables referenced in your agent rules exist and match the current codebase.")
            return "\n".join(lines)

        lines.append("| Severity | Rule File | Type | Target | Issue Description |")
        lines.append("| :--- | :--- | :--- | :--- | :--- |")

        for issue in self.report.issues:
            sev_badge = "🔴 `Error`" if issue.severity == Severity.ERROR else ("🟡 `Warning`" if issue.severity == Severity.WARNING else "🔵 `Info`")
            type_label = issue.drift_type.value.replace("_", " ").title()
            file_link = f"`{issue.rule_file}:{issue.line_number}`"
            target_code = f"`{issue.current_reference}`"
            clean_desc = issue.description.replace("|", "\\|")
            lines.append(f"| {sev_badge} | {file_link} | {type_label} | {target_code} | {clean_desc} |")

        lines.append("")

        # Add suggested patch section if available
        if self.report.suggested_patch:
            lines.append("### 🛠️ Suggested Fix Patch")
            lines.append("<details><summary>Click to view auto-generated patch for agent rules</summary>")
            lines.append("")
            lines.append("```diff")
            lines.append(self.report.suggested_patch)
            lines.append("```")
            lines.append("")
            lines.append("_You can apply this patch to keep your AI agents in sync with this PR!_")
            lines.append("</details>")
            lines.append("")

        return "\n".join(lines)

    def write_step_summary(self) -> None:
        """Writes report to GITHUB_STEP_SUMMARY if env variable is defined."""
        summary_file = os.getenv("GITHUB_STEP_SUMMARY")
        if summary_file:
            try:
                with open(summary_file, "a", encoding="utf-8") as f:
                    f.write("\n" + self.render_markdown_summary() + "\n")
            except Exception as e:
                print(f"::warning::Failed to write step summary: {e}")

    def emit_workflow_annotations(self) -> None:
        """Outputs workflow annotations for GitHub Actions log view."""
        for issue in self.report.issues:
            level = "error" if issue.severity == Severity.ERROR else ("warning" if issue.severity == Severity.WARNING else "notice")
            print(f"::{level} file={issue.rule_file},line={issue.line_number},title={issue.title}::{issue.description}")

    def write_github_outputs(self) -> None:
        """Sets step outputs via GITHUB_OUTPUT environment file."""
        output_file = os.getenv("GITHUB_OUTPUT")
        if not output_file:
            return

        try:
            with open(output_file, "a", encoding="utf-8") as f:
                f.write(f"drift-detected={'true' if self.report.drift_detected else 'false'}\n")
                f.write(f"drift-count={len(self.report.issues)}\n")
                f.write(f"error-count={self.report.error_count}\n")
                f.write(f"warning-count={self.report.warning_count}\n")
                # Multi-line output formatting
                f.write("drift-summary<<EOF\n")
                f.write(self.render_markdown_summary() + "\n")
                f.write("EOF\n")
                f.write("suggested-patch<<EOF\n")
                f.write(self.report.suggested_patch + "\n")
                f.write("EOF\n")
        except Exception as e:
            print(f"::warning::Failed to write GITHUB_OUTPUT: {e}")

    def post_pr_comment(self, github_token: str) -> None:
        """Posts or updates an existing comment on the Pull Request."""
        if not github_token:
            return

        event_path = os.getenv("GITHUB_EVENT_PATH")
        if not event_path or not os.path.exists(event_path):
            return

        try:
            with open(event_path, "r", encoding="utf-8") as f:
                event_data = json.load(f)
        except Exception:
            return

        pr_number = event_data.get("pull_request", {}).get("number")
        repo_full_name = os.getenv("GITHUB_REPOSITORY") or event_data.get("repository", {}).get("full_name")

        if not pr_number or not repo_full_name:
            return

        comment_body = f"{COMMENT_TAG}\n" + self.render_markdown_summary()
        headers = {
            "Authorization": f"Bearer {github_token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "AgentDrift-Sentinel-Action",
        }

        # 1. Check for existing comment to update (avoid duplicate spam)
        comments_url = f"https://api.github.com/repos/{repo_full_name}/issues/{pr_number}/comments"
        existing_comment_id = None

        try:
            req = urllib.request.Request(comments_url, headers=headers, method="GET")
            with urllib.request.urlopen(req) as resp:
                comments = json.loads(resp.read().decode("utf-8"))
                for c in comments:
                    if COMMENT_TAG in c.get("body", ""):
                        existing_comment_id = c.get("id")
                        break
        except Exception as e:
            print(f"::debug::Failed to list comments: {e}")

        # 2. Update or create comment
        try:
            if existing_comment_id:
                update_url = f"https://api.github.com/repos/{repo_full_name}/issues/comments/{existing_comment_id}"
                data = json.dumps({"body": comment_body}).encode("utf-8")
                req = urllib.request.Request(update_url, data=data, headers=headers, method="PATCH")
            else:
                data = json.dumps({"body": comment_body}).encode("utf-8")
                req = urllib.request.Request(comments_url, data=data, headers=headers, method="POST")

            with urllib.request.urlopen(req) as resp:
                print(f"AgentDrift Sentinel PR comment posted successfully (status {resp.status}).")
        except Exception as e:
            print(f"::warning::Failed to post PR comment: {e}")
