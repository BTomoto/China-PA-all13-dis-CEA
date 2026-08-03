# Known issues

- Full end-to-end reproduction requires locally obtained, authorized IHME/GBD inputs and the project parent workbook; these are intentionally omitted.
- The formal 10,000-draw PSA is not rerun during this import. Only aggregate results are included.
- Notebook execution order is based on the source documentation: notebook `02` is the smoke/audit entry point and notebook `03` is the formal run entry point. The project owner should confirm whether earlier notebooks exist outside the reviewed bundle.
- No standalone automated tests were supplied.
- Author names, preferred citation, repository-wide code license, and public-release eligibility require project-owner confirmation.
- Some notebooks may retain historical output metadata with local paths. Executable code is checked separately; saved output metadata is not treated as a runtime dependency.
