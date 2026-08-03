# Data availability and access

This repository intentionally omits individual-level data and restricted or redistribution-uncertain source data.

## Omitted inputs

- Original IHME GBD downloads (`input/gbd_raw_2010_2017/`). Obtain them through the IHME GBD Results Tool under the applicable terms.
- Standardized or derived GBD input extracts and projections. Regenerate these locally after obtaining authorized source data.
- The project parent workbook and GBD-derived CVD inputs, pending confirmation that redistribution is permitted.
- Draw-level 10,000-run PSA files and the original RAR archive. Aggregate final tables and figures are retained.

Place authorized local inputs at the paths expected by the scripts. The repository `.gitignore` prevents these files from being staged accidentally. `data/templates/` is reserved for non-sensitive schemas; `data/processed/` is reserved for small, redistribution-approved processed data.

No patient-level or personally identifying data was identified in the reviewed bundle. This is a filename/header/pattern audit, not a legal determination or formal de-identification certification.
