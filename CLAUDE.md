# Agent Guidelines - AgentDrift Sentinel

This repository implements the **AgentDrift Sentinel** GitHub Action, an automated guard preventing instruction-code desynchronization across agent context files (`CLAUDE.md`, `AGENTS.md`, `.cursorrules`, etc.).

## Project Architecture
- `src/agentdrift/`: Core Python package (dependency-free, stdlib only).
  - `src/agentdrift/detector.py`: Scans and discovers agent rule files across the repository.
  - `src/agentdrift/parser.py`: Extracts path, command, and environment variable references.
  - `src/agentdrift/manifest_analyzer.py`: Indexes scripts from manifests.
  - `src/agentdrift/git_differ.py`: Inspects PR git diff for deleted, renamed, or modified assets.
  - `src/agentdrift/drift_engine.py`: Correlates references with codebase state.
  - `src/agentdrift/patcher.py`: Computes unified diff patches to update stale agent rules.
  - `src/agentdrift/reporter.py`: Posts PR comments, step summaries, annotations, and outputs.
  - `src/agentdrift/cli.py`: Unified CLI entrypoint.
- `tests/`: Comprehensive unit test suite.
- `action.yml`: Composite GitHub Action manifest.

## Development & Test Commands
- Run test suite: `python -m unittest discover -s tests -v`
- Run local audit: `python -m src.agentdrift.cli --repo-root .`
- Test with fail flag: `python -m src.agentdrift.cli --repo-root . --fail-on-drift true`
