# Upload audit

Audit date: 2026-08-04 (Asia/Shanghai)

## Scope and archive review

- Source archive: `china-pa-all-dis-cea_github_ready_v1.0.zip`, 102,710,584 bytes, modified 2026-08-03 23:54:59.
- Archive contents: 207 entries, of which 181 are files. The archive was extracted to a separate audit directory and did not overwrite the source.
- Exact SHA-256 duplicate groups inside the extracted archive: none.
- Nested archives/compressed files: 21. These include three IHME ZIP files, one 65,966,558-byte formal PSA RAR, GBD/processed `.csv.gz` inputs, and draw-level PSA `.csv.gz` outputs.

## Prepared for upload

The staged import contains project code (`src/`), two notebooks (`notebooks/`), selected non-restricted configuration/input CSVs required by existing relative paths (`input/`), aggregate final tables and figures (`results/`), methods/project documents (`docs/`), environment metadata, repository documentation, and audit manifests. Deterministic tables remain in `results/` because the executable code uses those paths; formal PSA aggregates are separated below `results/tables/` and `results/figures/`. The exact committed list is the Git tree for this commit and can be reproduced with `git ls-tree -r --name-only HEAD` after commit.

## Excluded from upload

The complete item-level list is in `archive_manifest/excluded_files.csv`. Main exclusions are:

- The outer ZIP and the 65,966,558-byte `formal_psa_raw_archive/psa_formal.rar`: original archives and duplicate/intermediate content.
- `input/gbd_raw_2010_2017/`: original IHME downloads; redistribution not established.
- Standardized/derived GBD inputs, GBD projections, parent workbook, and GBD-derived CVD inputs: excluded conservatively pending license confirmation.
- Draw-level formal and smoke-test PSA files: large intermediates not needed to inspect aggregate final results.
- `src/__pycache__/`, `.pyc`, workbook previews, generated audit workbooks/manifests, and temporary/prompts: cache, old/generated, redundant, or non-project delivery artifacts.
- Historical smoke-test outputs and older duplicate presentation material: formal v1.4 aggregate PSA results and v1.5 narrative documentation are preferred; uncertain important documentation is retained or listed rather than deleted from the source.

## Large-file check

- Files over 50 MiB in the source archive: one (`formal_psa_raw_archive/psa_formal.rar`, 65,966,558 bytes); excluded.
- Files over 100 MiB in the extracted source: none.
- The outer ZIP is 102,710,584 bytes, below 100 MiB (104,857,600 bytes), and is excluded.
- No Git LFS configuration is used.

## Sensitive-information check

Filename, header, and text-pattern scans found no API keys, GitHub tokens, passwords, cookies, private keys, `.env` files, or obvious patient/person identifiers. Binary Office files were not treated as conclusively cleared by text scanning; they were retained only when they are project-generated documentation or aggregate workbooks, and this remains subject to project-owner review.

## Licensed-data check

IHME/GBD raw and derived data were identified. All clearly identified raw downloads and conservative categories of derived inputs were excluded. Aggregate analytical outputs remain, but their redistribution/public-release status must still be confirmed by the project owner. UN WPP-derived aggregate population inputs are retained with provenance; applicable citation/use requirements remain in force.

## Duplicate and version handling

No byte-identical duplicates were detected by SHA-256 within the extracted archive. Version labels indicate v1.4 formal PSA aggregates and v1.5 narrative documentation as the current formal materials; smoke-test/draw-level and preview artifacts were excluded. No source file was deleted or overwritten.

## Verification limitations

The audit is technical and conservative; it is not legal advice, a formal privacy certification, or a substitute for the data providers' current terms. See `KNOWN_ISSUES.md` for remaining manual confirmations.
