# Round 2 audit fix (2026-11-12)

This directory is an additive correction based on commit `433143a50a8d49f6220157ceb3fa075d31af3638`, on branch `codex/data-round2-audit-fix-20261112`. It does not overwrite round 1 or round 2 target-preparation files and is not a formal model input freeze.

## Entry points

- `registers/cost_row_comparison_v2_to_v3.csv`: row-level before/after audit.
- `registers/cost_evidence_links_v3.csv`: explicit `cost_id` to `evidence_id` links and exact-match gates.
- `checks/file_integrity.json`: structural/file checks.
- `checks/scientific_gates.json`: scientific evidence gates.
- `reports/HANDOFF_AUDIT_FIX.md`: next-round handoff.

Missing numeric values remain blank. No formal health model, cost aggregation, or PSA was run.
