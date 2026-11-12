# Round 5 handoff

Local worktree: `E:\工作目录\China-PA-13\Analysis`
Branch: `codex/dynamic-health-model-calibration-round5-20261112`
Base: `1e2407664e79b75db3f8a5f8d4c79e5435e5e2dc`

Status: `BLOCKED_TRANSITION_CALIBRATION`. Exact delivered commit is recorded by Git (`git rev-parse HEAD`), not embedded in a self-referential file.

Three raw packages pass their expected SHA256 and cross-population gates. Hazard decomposition, outcome mapping, annual 1/5 age flow, half-cycle incident entry, joint smooth positive case-fatality fitting and fail-closed dynamic runner are implemented.

IHD Male: max=613.3805%; RMS=126.7897%; infeasible intervals=11
IHD Female: max=715.4384%; RMS=151.4146%; infeasible intervals=12
IS Male: max=97.9046%; RMS=30.7272%; infeasible intervals=0
IS Female: max=51.2722%; RMS=16.9344%; infeasible intervals=0

Effective DW range: 0.0399833204–0.219571336. YLL/death range: 7.98960001–67.6582058.

The preserved incidence totals are IHD 45,531.007 / 116,899.570 / 547,363.017 and ischemic stroke 57,420.852 / 143,733.241 / 598,423.448 for 2025–2030 / 2034 / 2050, respectively. Dynamic endpoints are blank if calibration fails. Read CALIBRATION_REVIEW before selecting the next step.

New files are confined to this round plus repository requirements.txt, run_local.ps1 and README_LOCAL_RUN.md. Five source notebooks and five standard nbclient-executed copies, separate legacy and new test logs, validation report, requirements lock and hash manifest are included. Actual checks and counts are in logs/test_results.json and results/model_validation_report.json.

Work must resolve the incompatible age profile and definitions; cohort history, 95+ approximation and equal other mortality also need review. Thresholds are computational screens only. No old-round files or raw ZIPs were changed. No cost, CEA, PSA or main-branch merge was performed. Synthetic parameters never enter empirical results.

<!-- ACTUAL_CHECKS -->
Software tests: {'legacy': 48, 'new': 37, 'total': 85, 'failed': 0}; standard notebooks: 5/5; evidence/file checks: 13; scientific failures: 4.
