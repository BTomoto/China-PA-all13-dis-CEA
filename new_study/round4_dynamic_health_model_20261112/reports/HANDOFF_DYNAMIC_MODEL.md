# Round 4 handoff

**Status:** `BLOCKED_DYNAMIC_PARAMETERS` for empirical dynamic outcomes; `PILOT_CONDITIONAL_RR_DENOMINATOR` for the preserved incidence pilot.

The E: worktree contains a functional annual multi-state difference-cohort engine. The original round 3 IHD and ischemic-stroke incidence results are copied unchanged into the new directory with conditional RR-denominator status. IHD avoided incidence remains 45,531.007 (2025–2030), 116,899.570 (2025–2034) and 547,363.017 (2025–2050); stroke remains 57,420.852, 143,733.241 and 598,423.448. This is still a structural incidence pilot, not a paper-ready health result.

Kyu Table 1's four activity-category RRs are extracted. The multicate PIF function is present but blocked by the absence of approved China age × sex activity-category shares and a Work-approved movement rule. The prior statement that the binary formula did not equalize risk across existing active groups has been corrected in this round's reports. No prior-round files were changed.

Three GBD 2023 raw ZIPs are now verified. The incidence ZIP (`64e613442f4269bb79ff36e26a7069ad5da36a1abc8de566be58f49c3aa6805e`) remains unchanged. The disease-burden ZIP (`9ba35729cab5994ad9ce05427228c71b127d8b4bf03db899681ef250b2a5e2b7`) contains 800 rows for IHD and ischemic stroke: 640 required detailed age-sex Measure/Metric rows and 160 overlapping older-age aggregates. The all-cause ZIP (`dd38441e963a02f9f572afb56c8f2d4dfb39b58bc48b1c7ebff28d0c09fe835e`) contains 400 rows: 320 detailed rows and 80 overlapping aggregates, including 32 detailed age-sex Deaths rates. Model interfaces exclude aggregate ages and retain 95+.

Numeric disease death, patient-years, YLD, YLL and DALY are **not generated** as research outputs. Their result cells remain blank. GBD disease endpoints and all-cause death rates are calibration/validation targets only. A full-incidence synthetic software fixture demonstrates executable transitions and is confined to `tests/`. Next: Work must decide rate-to-hazard conversion and other-cause mortality decomposition; obtain a standard YLL life table; assemble disease-specific survival/duration, remission, recurrence, excess mortality and disability evidence; then inject admitted parameters and rerun locally.

All execution occurred under `E:\工作目录\China-PA-13\Analysis`. The E virtual environment is excluded from Git. No old directory, cost, CEA, PSA or main branch was modified.
