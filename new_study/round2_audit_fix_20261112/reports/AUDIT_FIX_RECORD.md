# Audit fix record

## Cost linkage

The prior `outcome_id` lookup was removed from the corrected interface. Every carried source field now requires an explicit `cost_id`/`evidence_id` link and exact agreement on original study, amount, currency, and cost definition. The legacy assumed price year remains a separate provenance field and is never relabelled as source-verified.

- T2D 3583, 6056 and 10164 CNY no longer inherit 2019. The separate 2092.87 USD/2019 evidence candidate remains intact.
- CRC 3447 USD no longer inherits 2014. The separate 61829 CNY/2014 evidence candidate remains intact.
- Dementia 6225 USD is `NOT_VERIFIED_EXACT`; Jia's published 19144.36 USD total and the approximate 6223.83 calculation remain distinguishable.

## Validation

File/identifier integrity and scientific evidence gates are reported separately. The finalizer upserts checks by unique `check_id`, so repeated runs update rather than append.
