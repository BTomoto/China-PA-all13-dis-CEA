# Local round-five run

Worktree: `E:\工作目录\China-PA-13\Analysis`.

From the repository root in PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\run_local.ps1
```

The current runner builds `new_study/round5_dynamic_calibration_20261112`, runs the 48 unchanged round-four tests plus 37 round-five tests, and executes five notebooks through nbclient with a real project ipykernel. Fixed direct dependency versions are in the round-five requirements; the measured environment lock is in `logs/environment_lock.txt`.

The three original local GBD ZIPs must remain at the paths in the round-five config, with their expected SHA256. ZIPs are read in place and are not stored in the new directory or committed. Raw inputs are not downloaded by this runner.

Current empirical status is `BLOCKED_TRANSITION_CALIBRATION`: software tests and input validation pass, but the joint prevalence/mortality fit does not satisfy its predeclared error gates. Dynamic endpoints remain blank. Read `reports/HANDOFF_ROUND5.md` and `reports/CALIBRATION_REVIEW.md` before changing scientific assumptions.
