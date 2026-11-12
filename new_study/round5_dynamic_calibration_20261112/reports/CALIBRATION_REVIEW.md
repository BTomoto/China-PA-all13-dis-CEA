# Calibration review

Status: `BLOCKED_TRANSITION_CALIBRATION`.

- IHD Male: max=613.3805%; RMS=126.7897%; infeasible intervals=11
- IHD Female: max=715.4384%; RMS=151.4146%; infeasible intervals=12
- IS Male: max=97.9046%; RMS=30.7272%; infeasible intervals=0
- IS Female: max=51.2722%; RMS=16.9344%; infeasible intervals=0

The pre-fit gate applies to all four disease-sex groups. No failing group is admitted and no fit threshold is relaxed. The current stationary no-remission structure and exported incidence/prevalence/mortality definitions require Work review. Do not infer a data transcription error solely from failure. Possible unresolved issues include incident event versus disease-state definitions, prevalent sequelae, historical cohort effects, boundary conditions, and open-age approximation. No disease structure or incidence totals have been changed.

A provisional dynamic result cannot be released until Work selects a defensible calibration path. The simple D/P initial curve is retained only as a diagnostic sensitivity; it is not substituted for the failed joint fit.

<!-- ACTUAL_CHECKS -->
Software tests: {'legacy': 48, 'new': 37, 'total': 85, 'failed': 0}; standard notebooks: 5/5; evidence/file checks: 13; scientific failures: 4.
