# AGENTS.md - AgentDrift Repository Standards

## Workspace Conventions
1. **Core Package:** All audit logic resides in `src/agentdrift/` using Python 3 standard library only to ensure instant zero-overhead execution inside GitHub Actions runners.
2. **Testing:** All features and drift detection types must have corresponding unit tests in `tests/`.
3. **Verification Command:** Always run `python -m unittest discover -s tests -v` to ensure 100% test pass rate.
4. **Action Manifest:** Any new inputs or outputs must be documented in both `action.yml` and `README.md`.
