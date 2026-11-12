# Health model pilot handoff

Branch: `codex/health-model-pilot-round3-20261112`

Base remote commit: `204f3e3c3bdf719d189c0a761760f072d77cc5c6`

Status: `INCIDENCE_PILOT_COMPLETE`; dynamic outcomes `BLOCKED_DYNAMIC_PARAMETERS`.

The verified GBD 2023 ZIP contains 2023 IHD and ischemic-stroke incidence Rate/Number with point/lower/upper for Male and Female. GBD 95+ matches combined WPP 95–99 and 100+. Original download date and UI screenshot remain unknown; provenance reconstructs exact conditions from the raw rows.

Results (expected cases, unrounded):

- 2025-2030 IHD: avoided 45,531.01; baseline 11,894,723.11
- 2025-2030 IS: avoided 57,420.85; baseline 16,939,572.20
- 2025-2034 IHD: avoided 116,899.57; baseline 21,593,706.56
- 2025-2034 IS: avoided 143,733.24; baseline 30,076,431.72
- 2025-2050 IHD: avoided 547,363.02; baseline 78,693,160.18
- 2025-2050 IS: avoided 598,423.45; baseline 96,790,693.32

The 2025 baseline is 21.9660515204% and fixed-weight 2030 intervention is 18.6711437924%, agreeing with Work's rounded figures. The 2018 exposure rates are retained by sex and age in the control.

Run `python build_deliverables.py` from this directory to rebuild data, reports and tests. The five notebooks call the same public functions. No fee model, CEA, PSA or formal dynamic endpoint numbers were run. Next steps require 2023 Prevalence, Deaths, YLD, YLL and disease survival/duration evidence plus Work method approval.
