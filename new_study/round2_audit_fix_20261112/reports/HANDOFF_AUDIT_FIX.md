# Handoff: round 2 audit fix

Branch: `codex/data-round2-audit-fix-20261112`

Base commit: `433143a50a8d49f6220157ceb3fa075d31af3638`

## Completed

- Replaced disease-level evidence inheritance with explicit cost/evidence links.
- Preserved 17 legacy cost values plus two newer standalone evidence candidates.
- Added row-level before/after comparison and independent integrity/science checks.
- Traced Ding's cost construction to IDF and EU-27 sources and classified published China attributable costs as external outputs.
- Reframed the 2010 issue as current-path incompatibility and documented four possible 18+/20+ bridges without choosing one.
- Split GBD filters into archived-confirmed, live-unchecked, and unsupported-for-requested-model states; added a user-login checklist.

## Still open

- Ding online appendix pp27/31 and Zhang/Chaaban detailed input tables were not acquired.
- No comparable 2010-to-2025 path has been selected; target value, attainment gap and annual path remain blank.
- Fine ages 70+ and Rate/cause details require an authenticated GBD menu check.
- Cost coverage, overlap, treatment uptake and 2025 conversion remain unresolved; no cost total is admissible.

## Boundary

No formal health model, cost aggregation, PSA, CEA or policy-cost module was run. This branch is an audit correction, not a model freeze.
