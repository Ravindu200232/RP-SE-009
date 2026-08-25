# AgentForge test suite

This folder contains a repository-level regression suite for the complete
AgentForge application. It is intentionally separate from the generated-app
tests that AgentForge creates inside customer projects.

## Layout

- `unit/agents/` — builder and code-agent helpers
- `unit/qa_agents/` — QA selection, E2E semantics, convergence, and reporting
- `unit/deployment/` — deployment security and artifact-safety helpers
- `unit/srs/` — SRS JSON recovery and builder-handoff helpers
- `integration/` — shared runtime and cross-agent contracts
- `results/latest.txt` — result from the most recent committed test run
- `results/validation.txt` — full repository validation summary

Run the complete suite from the repository root:

```powershell
python test/run_suite.py
```

The runner uses Python's standard-library `unittest` framework, prints the
detailed result, updates `test/results/latest.txt`, and exits non-zero on any
failure. Tests use temporary directories and do not require AWS, MongoDB,
Ollama, Electron, or a browser session.
