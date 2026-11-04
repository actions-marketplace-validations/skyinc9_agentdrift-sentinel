# 🤖 BOTS.md - Automated Agent & Bot Integration Guide

Welcome, AI Agent or Automated Bot! This document outlines how automated systems (such as Claude Code, GitHub Copilot Workspace, Cursor Agent, SWE-bench agents, and custom GitHub Bots) should consume, invoke, and interact with **AgentDrift Sentinel**.

---

## 🎯 Primary Purpose for Bots
Whenever you (an AI agent) make code changes in a Pull Request (refactoring folders, renaming modules, removing obsolete scripts, changing configuration):
1. **You risk breaking human-authored or agent-facing instruction files** (`CLAUDE.md`, `AGENTS.md`, `.cursorrules`, `.windsurfrules`, `.clinerules`, `OPENHANDS.md`).
2. **You can run AgentDrift Sentinel to self-audit your work** before declaring a task complete or submitting a PR.
3. **You can apply the generated patch** to automatically keep instructions synchronized with your code changes.

---

## ⚡ Bot Quick-Invocation Commands

### 1. Run Audit with Machine-Readable JSON Output
```bash
python -m src.agentdrift.cli --repo-root . --json
```

### 2. Check if Drift Was Detected Programmatically (Python)
```python
from pathlib import Path
from src.agentdrift.drift_engine import DriftEngine
from src.agentdrift.patcher import RulePatcher

engine = DriftEngine(Path("."))
report = engine.run_audit()

if report.drift_detected:
    patcher = RulePatcher(Path("."))
    patch = patcher.generate_patch(report)
    print(f"Drift detected ({len(report.issues)} issues).")
    print("Unified Patch:")
    print(patch)
else:
    print("All agent rules in sync!")
```

### 3. Automated Self-Healing Workflow for Bots
If you are an agent tasked with refactoring a repository, add this verification step to your task loop:

1. **Perform your code edits** (e.g., refactoring `src/legacy.ts` -> `src/v2/index.ts`).
2. **Run AgentDrift audit**:
   ```bash
   python -m src.agentdrift.cli --repo-root . --json > drift_report.json
   ```
3. **Parse `suggested_patch`**:
   - If `suggested_patch` is non-empty, apply it:
     ```bash
     git apply <<< $(jq -r .suggested_patch drift_report.json)
     ```
4. **Commit the updated rules** alongside your code changes:
   ```bash
   git add CLAUDE.md AGENTS.md .cursorrules .windsurfrules .clinerules
   git commit -m "docs(agent-rules): synchronize instructions with refactored paths"
   ```

---

## 📋 JSON Output Specification

When `--json` or `--format json` is provided, the output on `stdout` conforms to the following schema:

| Property | Type | Description |
| :--- | :--- | :--- |
| `drift_detected` | `boolean` | `true` if any issues were detected |
| `drift_count` | `number` | Total number of issues |
| `error_count` | `number` | Number of high-severity desyncs (renamed paths, deleted files, deleted scripts) |
| `warning_count` | `number` | Number of medium-severity desyncs (missing internal paths, undefined scripts) |
| `info_count` | `number` | Number of low-severity notices (unregistered environment variables) |
| `inspected_rule_files` | `string[]` | Relative file paths of all discovered agent rules |
| `git_base_ref` | `string` or `null` | Base branch ref used for diff comparison |
| `issues` | `DriftIssue[]` | List of identified drift issues |
| `suggested_patch` | `string` | Unified diff formatted patch ready for `git apply` |

### Issue Object Properties
Each item in `issues`:
- `rule_file`: File path where the drift exists (e.g., `CLAUDE.md`).
- `line_number`: 1-indexed line number.
- `drift_type`: One of `renamed_path`, `dead_path`, `dead_command`, `dead_env_var`.
- `severity`: One of `error`, `warning`, `info`.
- `title`: Short summary.
- `description`: Detailed explanation.
- `current_reference`: Exact text string referenced in the rule file.
- `suggested_fix`: Object with `original_line` and `replacement_line` (or `null` if manual review is needed).
- `metadata`: Key-value dictionary containing contextual info (e.g., `{"old_path": "...", "new_path": "..."}`).

---

## 🤝 Rules of Engagement for Autonomous Bots
- **Do not ignore `error_count > 0`**: Errors represent broken file targets that will cause future agents to hallucinate.
- **Always preserve unrelated comments**: When updating rule files, only modify the lines targeted by `suggested_fix`.
- **Verify tests after patching**: Run `python -m unittest discover -s tests -v` to ensure the repository remains in a healthy state.
