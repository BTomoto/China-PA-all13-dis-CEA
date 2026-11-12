# Round 4 handoff

**Status:** `BLOCKED_DYNAMIC_PARAMETERS` for empirical dynamic outcomes; `PILOT_CONDITIONAL_RR_DENOMINATOR` for the preserved incidence pilot.

The E: worktree contains a functional annual multi-state difference-cohort engine. The original round 3 IHD and ischemic-stroke incidence results are copied unchanged into the new directory with conditional RR-denominator status. IHD avoided incidence remains 45,531.007 (2025–2030), 116,899.570 (2025–2034) and 547,363.017 (2025–2050); stroke remains 57,420.852, 143,733.241 and 598,423.448. This is still a structural incidence pilot, not a paper-ready health result.

Kyu Table 1's four activity-category RRs are extracted. The multicate PIF function is present but blocked by the absence of approved China age × sex activity-category shares and a Work-approved movement rule. The prior statement that the binary formula did not equalize risk across existing active groups has been corrected in this round's reports. No prior-round files were changed.

The only verified GBD 2023 raw ZIP is IHD/ischemic-stroke incidence (`64e613442f4269bb79ff36e26a7069ad5da36a1abc8de566be58f49c3aa6805e`). It has 4,624 raw records and 64 usable 2023 age–sex–disease Rate/Number pairs; 95+ is retained. No 2023 Prevalence, Deaths, YLD or YLL original export was found. The user has been sent the GBD Results Tool homepage for manual sign-in. See `GBD_DOWNLOAD_MENU.md`.

Numeric disease death, patient-years, YLD, YLL and DALY are **not generated** as research outputs. Their result cells remain blank. A full-incidence synthetic software fixture demonstrates executable transitions and is confined to `tests/`. Next: obtain and validate the original GBD endpoints and mortality/life tables; assemble disease-specific survival/duration, remission, recurrence, excess mortality and disability evidence; have Work decide age-within-band and transition calibration; then inject admitted parameters and rerun locally.

All execution occurred under `E:\工作目录\China-PA-13\Analysis`. The E virtual environment is excluded from Git. No old directory, cost, CEA, PSA or main branch was modified.
