# Local run

Worktree: `E:\工作目录\China-PA-13\Analysis` during this round; all code resolves paths relative to the script and remains portable.

From the repository root in PowerShell:

```powershell
py -m venv .venv
.\run_local.ps1
```

Python 3.11+ standard library is sufficient for round four; repository `requirements.txt` retains third-party packages used by earlier rounds. The runner checks all three GBD ZIP hashes, 640 detailed disease-endpoint rows, 320 detailed all-cause rows, frozen incidence rows, software fixture, 48 automated tests and five notebooks. Empirical dynamic endpoints remain `BLOCKED_DYNAMIC_PARAMETERS`; the synthetic test fixture is excluded from scientific results.
