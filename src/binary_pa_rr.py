from __future__ import annotations
from model_io import install as _configure_io
_configure_io()
import math
from pathlib import Path
import numpy as np
import pandas as pd
AGE_GROUPS = ['20-24', '25-29', '30-34', '35-39', '40-44', '45-49', '50-54', '55-59', '60-64', '65-69', '70+']
SEXES = ['Female', 'Male']
STROKE_COMPONENTS = ['ischemic_stroke', 'intracerebral_hemorrhage', 'subarachnoid_hemorrhage']
STROKE_MAPPING_MODES = {'COMMON_STROKE_PIF', 'IS_ONLY'}

def share_common_stroke_rr_draw(rr_draw: object, component_ids: object, stroke_mapping: str) -> np.ndarray:
    if stroke_mapping not in STROKE_MAPPING_MODES:
        raise ValueError(f'Unknown stroke mapping: {stroke_mapping}')
    values = np.asarray(rr_draw, dtype=float).copy()
    components = [str(value) for value in component_ids]
    if values.ndim != 1 or len(values) != len(components):
        raise ValueError('RR draw and component identifiers must be aligned one-dimensional vectors')
    if stroke_mapping == 'COMMON_STROKE_PIF':
        missing = [component for component in STROKE_COMPONENTS if component not in components]
        if missing:
            raise ValueError(f'Missing stroke components: {missing}')
        stroke_indices = [components.index(component) for component in STROKE_COMPONENTS]
        values[stroke_indices] = values[stroke_indices[0]]
    return values

def binary_pif(p0: object, p1: object, rr: object) -> np.ndarray:
    p0_array = np.asarray(p0, dtype=float)
    p1_array = np.asarray(p1, dtype=float)
    rr_array = np.asarray(rr, dtype=float)
    risk0 = p0_array * rr_array + 1.0 - p0_array
    risk1 = p1_array * rr_array + 1.0 - p1_array
    return np.divide(risk0 - risk1, risk0, out=np.zeros_like(risk0, dtype=float), where=risk0 > 0)

def lognormal_sigma(lower_95: float, upper_95: float) -> float:
    lower = float(lower_95)
    upper = float(upper_95)
    if lower <= 0 or upper <= lower:
        raise ValueError(f'Invalid RR interval: {lower}, {upper}')
    return float((math.log(upper) - math.log(lower)) / (2.0 * 1.96))

def build_binary_pa_baseline(parent_pa: pd.DataFrame) -> pd.DataFrame:
    required = {'sex', 'age_group', 'n', 'inactive_n', 'active_n', 'p_inactive', 'p_active', 'source_variant', 'parameter_status'}
    missing = sorted(required - set(parent_pa.columns))
    if missing:
        raise ValueError(f'PA_binary_20plus missing fields: {missing}')
    out = parent_pa[['sex', 'age_group', 'n', 'inactive_n', 'active_n', 'p_inactive', 'p_active', 'source_variant', 'parameter_status']].copy()
    for column in ['n', 'inactive_n', 'active_n', 'p_inactive', 'p_active']:
        out[column] = pd.to_numeric(out[column], errors='raise')
    expected_pairs = {(sex, age) for sex in SEXES for age in AGE_GROUPS}
    observed_pairs = set(zip(out['sex'].astype(str), out['age_group'].astype(str)))
    if observed_pairs != expected_pairs or out.duplicated(['sex', 'age_group']).any():
        missing_pairs = sorted(expected_pairs - observed_pairs)
        extra_pairs = sorted(observed_pairs - expected_pairs)
        raise ValueError(f'Binary PA age-sex mapping is incomplete: missing={missing_pairs}, extra={extra_pairs}')
    if not np.allclose(out['inactive_n'] + out['active_n'], out['n'], atol=1e-08):
        raise ValueError('inactive_n + active_n does not equal n')
    if not np.allclose(out['p_inactive'] + out['p_active'], 1.0, atol=1e-12):
        raise ValueError('p_inactive + p_active does not equal one')
    if not np.allclose(out['p_inactive'], out['inactive_n'] / out['n'], atol=1e-12):
        raise ValueError('p_inactive does not reconcile to inactive_n / n')
    out['probability_sum'] = out['p_inactive'] + out['p_active']
    out['pa_interface'] = 'UNCALIBRATED_BINARY_INACTIVE_ACTIVE'
    return out.sort_values(['sex', 'age_group']).reset_index(drop=True)

def build_pa_beta_parameters(pa_baseline: pd.DataFrame) -> pd.DataFrame:
    out = pa_baseline[['sex', 'age_group', 'n', 'inactive_n', 'active_n', 'source_variant', 'parameter_status']].copy()
    out.insert(0, 'parameter_id', [f'PA|{sex}|{age}' for sex, age in zip(out['sex'], out['age_group'])])
    out['beta_alpha_inactive'] = pd.to_numeric(out['inactive_n'], errors='raise') + 0.5
    out['beta_beta_active'] = pd.to_numeric(out['active_n'], errors='raise') + 0.5
    out['distribution'] = 'Beta'
    out['sampling_rule'] = 'Beta(inactive_n+0.5, active_n+0.5); active=1-inactive'
    out['pa_interface'] = 'UNCALIBRATED_BINARY_INACTIVE_ACTIVE'
    return out

def load_rr_spec(path: Path) -> pd.DataFrame:
    spec = pd.read_csv(path, encoding='utf-8-sig')
    required = {'outcome_id', 'component_id', 'binary_rr', 'lower_95', 'upper_95', 'exact_proxy', 'sex_applicability', 'source_reference', 'approved_status', 'pif_mode_main', 'pif_mode_is_only'}
    missing = sorted(required - set(spec.columns))
    if missing:
        raise ValueError(f'Binary RR decision table missing fields: {missing}')
    if spec['component_id'].duplicated().any():
        duplicates = spec.loc[spec['component_id'].duplicated(False), 'component_id'].tolist()
        raise ValueError(f'Duplicate RR components: {duplicates}')
    for column in ['binary_rr', 'lower_95', 'upper_95']:
        spec[column] = pd.to_numeric(spec[column], errors='raise')
    if not ((spec['lower_95'] > 0) & (spec['lower_95'] <= spec['binary_rr']) & (spec['binary_rr'] <= spec['upper_95'])).all():
        raise ValueError('RR point estimates are not contained within their 95% intervals')
    if not spec['approved_status'].eq('APPROVED_PRESET_MAIN').all():
        raise ValueError('Every active RR row must be approved for the preset main analysis')
    if not set(spec['exact_proxy']).issubset({'exact', 'proxy'}):
        raise ValueError('exact_proxy must contain only exact or proxy')
    stroke = spec.loc[spec['outcome_id'].eq('stroke')].set_index('component_id')
    if set(stroke.index) != set(STROKE_COMPONENTS):
        raise ValueError('The RR table must contain all three stroke components')
    if not np.allclose(stroke['binary_rr'], 1.19) or not np.allclose(stroke['lower_95'], 1.09) or (not np.allclose(stroke['upper_95'], 1.28)):
        raise ValueError('The approved stroke-class interface must use IS RR 1.19 (1.09-1.28)')
    if not stroke['pif_mode_main'].eq('APPLY_COMMON_STROKE_PIF').all():
        raise ValueError('Main analysis must apply one common stroke PIF to all three components')
    if stroke.loc['ischemic_stroke', 'pif_mode_is_only'] != 'APPLY_IS_RR':
        raise ValueError('IS_ONLY must retain the approved RR for ischemic stroke')
    if not stroke.loc[['intracerebral_hemorrhage', 'subarachnoid_hemorrhage'], 'pif_mode_is_only'].eq('ZERO_PIF').all():
        raise ValueError('IS_ONLY must set ICH and SAH PIF to zero')
    spec['log_sigma'] = [lognormal_sigma(lo, hi) for lo, hi in zip(spec['lower_95'], spec['upper_95'])]
    return spec

def component_rr_interface(spec: pd.DataFrame, stroke_mapping: str) -> pd.DataFrame:
    if stroke_mapping not in STROKE_MAPPING_MODES:
        raise ValueError(f'Unknown stroke mapping: {stroke_mapping}')
    out = spec.copy()
    mode_column = 'pif_mode_main' if stroke_mapping == 'COMMON_STROKE_PIF' else 'pif_mode_is_only'
    out['pif_mode'] = out[mode_column]
    out['stroke_mapping'] = stroke_mapping
    out['rr_interface'] = 'BINARY_INACTIVE_VS_ACTIVE'
    return out
