import numpy as np
import pandas as pd
from public_inputs import ensure_inputs, read_public_parent


def read_parent(name):
    ensure_inputs()
    source = read_public_parent(name)
    if name != 'PA_binary_20plus':
        return source
    # These Excel proportions already refer to 2025.
    if len(source) != 22 or not source['year'].eq(2025).all():
        raise ValueError('Expected 22 age-sex baseline strata for 2025')
    from binary_pa_rr import AGE_GROUPS, SEXES
    pairs = set(zip(source.sex, source.age_group))
    if pairs != {(s, a) for s in SEXES for a in AGE_GROUPS} or source.duplicated(['sex', 'age_group']).any():
        raise ValueError('Incomplete or duplicated baseline age-sex mapping')
    values = source[['p_inactive', 'p_active', 'psa_precision_n']].apply(pd.to_numeric, errors='raise')
    if not np.isfinite(values.to_numpy()).all() or not values.psa_precision_n.gt(0).all():
        raise ValueError('Baseline values must be finite; precision must be positive')
    if not values[['p_inactive', 'p_active']].ge(0).all().all() or not values[['p_inactive', 'p_active']].le(1).all().all():
        raise ValueError('Baseline proportions must lie between zero and one')
    if not np.allclose(values.p_inactive + values.p_active, 1, rtol=0, atol=1e-12):
        raise ValueError('Baseline proportions must sum to one')
    out = source[['sex', 'age_group']].copy()
    out['n'] = values.psa_precision_n
    out['p_inactive'] = values.p_inactive
    out['p_active'] = values.p_active
    # Retained stratum precision is an assumption, not national survey counts.
    out['inactive_n'] = out.n * out.p_inactive
    out['active_n'] = out.n * out.p_active
    out['source_variant'] = 'MANUSCRIPT_S3_2025_POINT_ESTIMATES'
    out['parameter_status'] = 'POINTS_FROM_S3;PSA_PSEUDO_COUNTS_WITH_RETAINED_LEGACY_PRECISION;NOT_NATIONAL_COUNTS'
    return out
