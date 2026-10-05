from __future__ import annotations
from model_io import install as _configure_io
_configure_io()
import hashlib
import json
import math
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
import numpy as np
import pandas as pd
from binary_pa_rr import STROKE_COMPONENTS, binary_pif, build_binary_pa_baseline, component_rr_interface, load_rr_spec
SCRIPT_PATH = Path(__file__).resolve()
BUNDLE_ROOT = SCRIPT_PATH.parent.parent
DATA_ROOT = Path(os.environ.get('ALLDIS_DATA_ROOT', str(BUNDLE_ROOT))).resolve()
OUTPUT = Path(os.environ.get('ALLDIS_OUTPUT_ROOT', str(BUNDLE_ROOT))).resolve()
PARENT_DB = BUNDLE_ROOT / 'src' / 'aggregate_inputs.py'
WPP_FUTURE = DATA_ROOT / 'input' / 'population' / 'WPP2024_China_age_sex_2025_2050.csv'
WPP_HISTORY = DATA_ROOT / 'input' / 'population' / 'WPP2024_China_age_sex_history.csv'
CVD_CORE = DATA_ROOT / 'input' / 'cvd_v16_core'
CVD_COST_LONG = DATA_ROOT / 'input' / 'policy_costs_long_term'
HTN_MAIN = DATA_ROOT / 'input' / 'hypertension' / 'hypertension_5y_main.csv'
OLD_COSTS = DATA_ROOT / 'input' / 'disease_costs' / 'disease_cost_candidates_harmonized_2025cny.csv'
GBD_BURDEN_STANDARDIZED = DATA_ROOT / 'input' / 'gbd_standardized' / 'GBD_burden_components.csv.gz'
GBD_CASES_STANDARDIZED = DATA_ROOT / 'input' / 'gbd_standardized' / 'GBD_cases_components.csv.gz'
RR_SPEC = BUNDLE_ROOT / 'config' / 'binary_rr_interface_spec.csv'
BASE_YEAR = 2025
END_YEAR = 2050
YEARS = list(range(BASE_YEAR, END_YEAR + 1))
HORIZONS = [5, 10, 26]
HEALTH_DISCOUNT_RATE = 0.03
COST_DISCOUNT_RATE = 0.03
AGE_GROUPS = ['20-24', '25-29', '30-34', '35-39', '40-44', '45-49', '50-54', '55-59', '60-64', '65-69', '70+']
SEXES = ['Female', 'Male']
SCENARIOS = [f'S{i}' for i in range(8)]
FRONTIER_SCENARIOS = [f'S{i}' for i in range(7)]
MEASURE_SHORT = {'DALYs (Disability-Adjusted Life Years)': 'DALY', 'YLLs (Years of Life Lost)': 'YLL', 'YLDs (Years Lived with Disability)': 'YLD', 'Deaths': 'Deaths', 'Incidence': 'Incidence', 'Prevalence': 'Prevalence'}
COMPONENT_NAMES = {495: 'ischemic_stroke', 496: 'intracerebral_hemorrhage', 497: 'subarachnoid_hemorrhage'}
OUTCOME_NAMES_CN = {'coronary_heart_disease': '缺血性心脏病', 'stroke': '卒中（3亚型合计）', 'type2_diabetes': '2型糖尿病', 'hypertension': '高血压', 'bladder_cancer': '膀胱癌', 'breast_cancer': '乳腺癌', 'colon_cancer': '结直肠癌', 'endometrial_cancer': '子宫内膜癌（GBD子宫癌代理）', 'oesophageal_cancer': '食管癌', 'gastric_cancer': '胃癌', 'renal_cancer': '肾癌', 'dementia': '痴呆', 'depression': '抑郁症'}

@dataclass(frozen=True)
class AnalysisCase:
    case_id: str
    d1_lag: str = 'group_specific'
    d2_s0: str = 'main_damped'
    d3_disease: str = 'main_2010_2023_damped'
    d9_maintenance: str = 'FULL_MAINTENANCE'
    stroke_mapping: str = 'COMMON_STROKE_PIF'
    changed_decision: str = 'PRIMARY'
CASES = [AnalysisCase('PRIMARY'), AnalysisCase('D1_IMMEDIATE', d1_lag='immediate', changed_decision='D1'), AnalysisCase('D1_DELAYED_PLUS2', d1_lag='delayed_plus2', changed_decision='D1'), AnalysisCase('D2_STABLE_AFTER_2034', d2_s0='stable_after_2034', changed_decision='D2'), AnalysisCase('D2_CONTINUED', d2_s0='constrained_continuation', changed_decision='D2'), AnalysisCase('D3_FIXED_2023_RATE', d3_disease='fixed_2023_rate', changed_decision='D3'), AnalysisCase('D3_RECENT_2018_2023', d3_disease='recent_2018_2023_damped', changed_decision='D3'), AnalysisCase('D3_CONTINUED', d3_disease='constrained_trend_continuation', changed_decision='D3'), AnalysisCase('D9_REDUCED_75', d9_maintenance='REDUCED_75_PERCENT', changed_decision='D9'), AnalysisCase('D9_STOP_AFTER_2034', d9_maintenance='STOP_AFTER_2034', changed_decision='D9'), AnalysisCase('IS_ONLY', stroke_mapping='IS_ONLY', changed_decision='STROKE_MAPPING')]

def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()

def read_parent_sheet(sheet: str) -> pd.DataFrame:
    from aggregate_inputs import read_parent
    return read_parent(sheet)

def normalize_age(value: object) -> str:
    return str(value).strip().replace(' years', '').replace(' year', '')

def load_inputs() -> dict[str, pd.DataFrame]:
    pa = build_binary_pa_baseline(read_parent_sheet('PA_binary_20plus'))
    rr_parent = read_parent_sheet('RR_main')
    rr_spec = load_rr_spec(RR_SPEC)
    lag = read_parent_sheet('lag_assumptions')
    population_parent = read_parent_sheet('population_projection')
    if GBD_BURDEN_STANDARDIZED.exists():
        gbd_burden = pd.read_csv(GBD_BURDEN_STANDARDIZED, encoding='utf-8-sig')
    else:
        gbd_burden = read_parent_sheet('GBD_burden_components')
    if GBD_CASES_STANDARDIZED.exists():
        gbd_cases = pd.read_csv(GBD_CASES_STANDARDIZED, encoding='utf-8-sig')
    else:
        gbd_cases = read_parent_sheet('GBD_cases_components')
    mapping = read_parent_sheet('disease_mapping')
    policy_parent = read_parent_sheet('policy_effects')
    qc_parent = read_parent_sheet('QC_summary')
    policy = pd.read_csv(CVD_CORE / 'policy_scenarios.csv', encoding='utf-8-sig')
    cvd_annual = pd.read_csv(CVD_CORE / 'gbd_ihd_is_annual_2025_2034.csv', encoding='utf-8-sig')
    htn = pd.read_csv(HTN_MAIN, encoding='utf-8-sig')
    cost_candidates = pd.read_csv(OLD_COSTS, encoding='utf-8-sig')
    cost_main = pd.read_csv(CVD_COST_LONG / 'policy_cost_2025_2050_D9_main_interim.csv', encoding='utf-8-sig')
    cost_d9 = pd.read_csv(CVD_COST_LONG / 'policy_cost_2035_2050_D9_sensitivity_provisional.csv', encoding='utf-8-sig')
    wpp_history = pd.read_csv(WPP_HISTORY, encoding='utf-8-sig')
    wpp_future = pd.read_csv(WPP_FUTURE, encoding='utf-8-sig')
    return locals()

def build_population(inputs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    parent = inputs['population_parent']
    baseline = parent.loc[parent['year'].eq(BASE_YEAR), ['sex', 'age_group', 'baseline_population_2025']].copy()
    baseline['baseline_population_2025'] = pd.to_numeric(baseline['baseline_population_2025'], errors='raise')
    wpp = inputs['wpp_future'].loc[inputs['wpp_future']['variant'].eq('Medium'), ['year', 'sex', 'age_group', 'population']].copy()
    wpp['year'] = pd.to_numeric(wpp['year'], errors='raise').astype(int)
    wpp['population'] = pd.to_numeric(wpp['population'], errors='raise')
    wpp = wpp.loc[wpp['year'].between(BASE_YEAR, END_YEAR)].copy()
    anchor = wpp.loc[wpp['year'].eq(BASE_YEAR), ['sex', 'age_group', 'population']].rename(columns={'population': 'wpp_population_2025'})
    out = wpp.merge(anchor, on=['sex', 'age_group'], validate='many_to_one').merge(baseline, on=['sex', 'age_group'], validate='many_to_one')
    out['wpp_index_2025'] = out['population'] / out['wpp_population_2025']
    out['population_model'] = out['population']
    out['parent_to_wpp_2025_ratio'] = out['baseline_population_2025'] / out['wpp_population_2025']
    out['population_source'] = 'UN WPP 2024 Medium annual age-sex population; CVD v16 numeric parent'
    out = out[['year', 'sex', 'age_group', 'population_model', 'population', 'wpp_population_2025', 'baseline_population_2025', 'parent_to_wpp_2025_ratio', 'wpp_index_2025', 'population_source']]
    out = out.sort_values(['year', 'sex', 'age_group']).reset_index(drop=True)
    expected = len(YEARS) * len(SEXES) * len(AGE_GROUPS)
    if len(out) != expected or out['population_model'].isna().any() or (out['population_model'] <= 0).any():
        raise ValueError('2025—2050 model population is incomplete')
    return out

def disease_trend_multiplier(scenario: str, year: int) -> float:
    if year <= 2034:
        return 1.0
    if scenario in {'main_2010_2023_damped', 'recent_2018_2023_damped'}:
        return max(0.0, (2040 - year) / 6.0)
    if scenario == 'fixed_2023_rate':
        return 0.0
    if scenario == 'constrained_trend_continuation':
        return 1.0
    raise ValueError(scenario)

def cumulative_disease_exposure(scenario: str, year: int) -> float:
    if scenario == 'fixed_2023_rate':
        return 0.0
    total = 1.0
    for y in range(2025, int(year) + 1):
        total += disease_trend_multiplier(scenario, y)
    return total

def fit_log_rate_slope(years: np.ndarray, values: np.ndarray) -> tuple[float, float, int]:
    valid = np.isfinite(years) & np.isfinite(values) & (values >= 0)
    years = years[valid].astype(int)
    values = values[valid].astype(float)
    if len(years) == 0:
        return (0.0, math.nan, 2023)
    order = np.argsort(years)
    years, values = (years[order], values[order])
    anchor_year = int(years[-1])
    anchor = float(values[-1])
    positive = values > 0
    if positive.sum() < 2:
        return (0.0, anchor, anchor_year)
    slope = float(np.polyfit(years[positive], np.log(values[positive]), 1)[0])
    return (float(np.clip(slope, -0.1, 0.1)), anchor, anchor_year)

def prepare_gbd(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()
    df['year'] = pd.to_numeric(df['year'], errors='raise').astype(int)
    df['cause_id'] = pd.to_numeric(df['cause_id'], errors='raise').astype(int)
    for col in ['val', 'lower', 'upper']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df['age_group'] = df['age_name'].map(normalize_age)
    df['sex'] = df['sex_name'].astype(str)
    df['outcome_id'] = df['lancet_outcome_id'].astype(str)
    df['outcome_name'] = df['lancet_outcome_name'].astype(str)
    df['component_id'] = [COMPONENT_NAMES.get(int(cid), str(oid)) for cid, oid in zip(df['cause_id'], df['outcome_id'])]
    df = df.loc[df['year'].le(2023) & df['age_group'].isin(AGE_GROUPS) & df['sex'].isin(SEXES)].copy()
    female_only = df['outcome_id'].isin(['breast_cancer', 'endometrial_cancer'])
    df = df.loc[~female_only | df['sex'].eq('Female')].copy()
    return df

def project_gbd(raw: pd.DataFrame, value_domain: str, population: pd.DataFrame, history_pop: pd.DataFrame, scenario: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = prepare_gbd(raw)
    if scenario == 'recent_2018_2023_damped':
        df = df.loc[df['year'].ge(2018)].copy()
    hp = history_pop[['year', 'sex', 'age_group', 'population']].copy()
    hp['year'] = pd.to_numeric(hp['year'], errors='raise').astype(int)
    hp['population'] = pd.to_numeric(hp['population'], errors='raise')
    df = df.merge(hp, on=['year', 'sex', 'age_group'], how='left', validate='many_to_one')
    if df['population'].isna().any():
        raise ValueError('Historical WPP denominators are incomplete')
    df['rate'] = df['val'] / df['population']
    pop_lookup = population.set_index(['year', 'sex', 'age_group'])['population_model'].to_dict()
    group_cols = ['outcome_id', 'outcome_name', 'component_id', 'cause_id', 'cause_name', 'sex', 'age_group', 'measure_name']
    rows: list[dict[str, object]] = []
    slope_rows: list[dict[str, object]] = []
    for keys, group in df.groupby(group_cols, dropna=False, sort=False):
        g = group.sort_values('year')
        slope, anchor_rate, anchor_year = fit_log_rate_slope(g['year'].to_numpy(float), g['rate'].to_numpy(float))
        anchor_row = g.loc[g['year'].eq(anchor_year)].iloc[-1]
        anchor_val = float(anchor_row['val'])
        low_ratio = min(float(anchor_row['lower']) / anchor_val, 1.0) if anchor_val > 0 and pd.notna(anchor_row['lower']) else 1.0
        high_ratio = max(float(anchor_row['upper']) / anchor_val, 1.0) if anchor_val > 0 and pd.notna(anchor_row['upper']) else 1.0
        slope_rows.append({'outcome_id': keys[0], 'outcome_name': keys[1], 'component_id': keys[2], 'cause_id': keys[3], 'cause_name': keys[4], 'sex': keys[5], 'age_group': keys[6], 'measure_name': keys[7], 'value_domain': value_domain, 'anchor_year': anchor_year, 'anchor_rate': anchor_rate, 'history_start_year': int(g['year'].min()), 'history_end_year': int(g['year'].max()), 'annual_log_rate_slope_history_capped': slope, 'raw_history_years': int(g['year'].nunique()), 'd3_scenario': scenario})
        for year in YEARS:
            pop = float(pop_lookup[year, keys[5], keys[6]])
            if not np.isfinite(anchor_rate) or anchor_rate <= 0:
                rate = 0.0 if anchor_rate == 0 else np.nan
            else:
                rate = float(anchor_rate * np.exp(slope * cumulative_disease_exposure(scenario, year)))
            value = rate * pop if np.isfinite(rate) else np.nan
            rows.append({'outcome_id': keys[0], 'outcome_name': keys[1], 'component_id': keys[2], 'cause_id': keys[3], 'cause_name': keys[4], 'sex': keys[5], 'age_group': keys[6], 'measure_name': keys[7], 'measure_short': MEASURE_SHORT.get(str(keys[7]), str(keys[7])), 'value_domain': value_domain, 'year': year, 'projected_value': value, 'projected_lower': value * low_ratio, 'projected_upper': value * high_ratio, 'population_model': pop, 'projected_rate_per_100k': rate * 100000 if np.isfinite(rate) else np.nan, 'anchor_year': anchor_year, 'anchor_rate': anchor_rate, 'history_start_year': int(g['year'].min()), 'history_end_year': int(g['year'].max()), 'annual_log_rate_slope_history_capped': slope, 'annual_slope_multiplier': disease_trend_multiplier(scenario, year), 'cumulative_slope_exposure_since_2023': cumulative_disease_exposure(scenario, year), 'd3_scenario': scenario})
    out = pd.DataFrame(rows)
    slopes = pd.DataFrame(slope_rows)
    if value_domain == 'burden':
        idx_cols = ['outcome_id', 'component_id', 'cause_id', 'sex', 'age_group', 'year']
        for keys, indices in out.groupby(idx_cols, sort=False).groups.items():
            positions = {out.at[i, 'measure_short']: i for i in indices}
            if 'YLD' in positions and 'YLL' in positions and ('DALY' in positions):
                for value_col in ['projected_value', 'projected_lower', 'projected_upper']:
                    out.at[positions['DALY'], value_col] = out.at[positions['YLD'], value_col] + out.at[positions['YLL'], value_col]
                out.at[positions['DALY'], 'identity_rule'] = 'DALY=YLL+YLD enforced'
            elif keys[0] == 'depression' and 'YLD' in positions and ('DALY' in positions):
                for value_col in ['projected_value', 'projected_lower', 'projected_upper']:
                    out.at[positions['DALY'], value_col] = out.at[positions['YLD'], value_col]
                out.at[positions['DALY'], 'identity_rule'] = 'Depression DALY=YLD enforced'
    return (out, slopes)

def s0_rate_schedule(scenario: str) -> dict[int, float]:
    rates = {}
    for year in YEARS:
        if year <= 2034:
            rate = 0.0084
        elif scenario == 'main_damped':
            rate = 0.0084 * max(0.0, (2040 - year) / 6.0)
        elif scenario == 'stable_after_2034':
            rate = 0.0
        elif scenario == 'constrained_continuation':
            rate = 0.0084
        else:
            raise ValueError(scenario)
        rates[year] = rate
    return rates

def load_effect_retention(inputs: dict[str, pd.DataFrame], maintenance: str) -> dict[tuple[str, int], float]:
    if maintenance == 'FULL_MAINTENANCE':
        return {(sid, year): 1.0 for sid in SCENARIOS for year in YEARS if year >= 2035}
    d = inputs['cost_d9']
    d = d.loc[d['maintenance_scenario'].eq(maintenance) & d['cost_structure_scenario'].eq('STRUCTURAL_ANCHOR') & d['perspective'].eq('payer'), ['scenario_id', 'year', 'effect_retention_relative_to_2034']].copy()
    return {(str(r.scenario_id), int(r.year)): float(r.effect_retention_relative_to_2034) if pd.notna(r.effect_retention_relative_to_2034) else 1.0 for r in d.itertuples(index=False)}

def build_pa_trajectories(inputs: dict[str, pd.DataFrame], case: AnalysisCase) -> pd.DataFrame:
    pa = inputs['pa'].copy()
    policy = inputs['policy'].copy().set_index('scenario_id')
    rates = s0_rate_schedule(case.d2_s0)
    retention = load_effect_retention(inputs, case.d9_maintenance)
    rows = []
    for p in pa.itertuples(index=False):
        inactive = float(p.p_inactive)
        for year in YEARS:
            if year > BASE_YEAR:
                inactive = min(0.999, inactive * (1.0 + rates[year]))
            active = 1.0 - inactive
            for sid in SCENARIOS:
                pol = policy.loc[sid]
                if sid == 'S0':
                    uptake = 0.0
                    realised = 0.0
                elif year <= 2034:
                    uptake = float(np.clip((year - BASE_YEAR + 0.5) / max(float(pol.ramp_years), 1.0), 0.0, 1.0))
                    realised = float(pol.theta_mean) * float(pol.coverage_mean) * uptake
                else:
                    uptake_2034 = float(np.clip((2034 - BASE_YEAR + 0.5) / max(float(pol.ramp_years), 1.0), 0.0, 1.0))
                    realised = float(pol.theta_mean) * float(pol.coverage_mean) * uptake_2034 * retention.get((sid, year), 1.0)
                    uptake = uptake_2034 * retention.get((sid, year), 1.0)
                movers = inactive * realised
                inactive_policy = inactive - movers
                active_policy = 1.0 - inactive_policy
                rows.append({'year': year, 'sex': p.sex, 'age_group': p.age_group, 'scenario_id': sid, 'inactive_s0': inactive, 'active_s0': active, 'inactive_policy': inactive_policy, 'active_policy': active_policy, 's0_annual_relative_change': rates[year], 'policy_uptake_or_retention': uptake, 'realised_relative_reduction_in_inactive_pa': realised, 'd2_scenario': case.d2_s0, 'd9_maintenance_scenario': case.d9_maintenance, 'pa_interface': 'UNCALIBRATED_BINARY_INACTIVE_ACTIVE'})
    out = pd.DataFrame(rows)
    prob_sum = out[['inactive_policy', 'active_policy']].sum(axis=1)
    if not np.allclose(prob_sum, 1.0, atol=1e-10) or (out[['inactive_policy', 'active_policy']] < -1e-12).any().any():
        raise ValueError('PA trajectory probabilities are invalid')
    return out

def build_rr_interface(inputs: dict[str, pd.DataFrame], stroke_mapping: str) -> pd.DataFrame:
    parent = inputs['rr_parent'].copy()
    parent['rr_inactive_vs_active'] = pd.to_numeric(parent['rr_inactive_vs_active'], errors='raise')
    parent_lookup = parent.set_index('outcome_id')['rr_inactive_vs_active'].to_dict()
    spec = component_rr_interface(inputs['rr_spec'], stroke_mapping)
    for outcome, expected in parent_lookup.items():
        observed = spec.loc[spec['outcome_id'].eq(outcome), 'binary_rr'].unique()
        if len(observed) != 1 or not np.isclose(float(observed[0]), float(expected)):
            raise ValueError(f'RR decision table does not reconcile to approved parent value for {outcome}')
    out = spec.rename(columns={'binary_rr': 'rr_inactive_vs_active', 'sex_applicability': 'sex_use', 'source_reference': 'rr_source'}).copy()
    return out

def lag_multiplier(outcome_id: str, year: int, lag_table: pd.DataFrame, mode: str) -> float:
    if mode == 'immediate':
        return 1.0
    if outcome_id in {'hypertension', 'depression'}:
        group = 'fast'
    elif outcome_id in {'coronary_heart_disease', 'stroke', 'type2_diabetes'}:
        group = 'medium'
    elif outcome_id in {'bladder_cancer', 'breast_cancer', 'colon_cancer', 'endometrial_cancer', 'oesophageal_cancer', 'gastric_cancer', 'renal_cancer'}:
        group = 'cancer'
    elif outcome_id == 'dementia':
        group = 'dementia'
    else:
        raise KeyError(outcome_id)
    row = lag_table.loc[lag_table['lag_group'].eq(group) & lag_table['analysis_role'].eq('main_structural')].iloc[0]
    delay, full = (float(row.start_delay_years), float(row.time_to_full))
    if mode == 'delayed_plus2':
        delay += 2.0
        full += 2.0
    elapsed = year - BASE_YEAR + 1
    if elapsed <= delay:
        return 0.0
    if full <= delay:
        return 1.0
    return float(np.clip((elapsed - delay) / (full - delay), 0.0, 1.0))

def calculate_health(projected: pd.DataFrame, pa: pd.DataFrame, rr: pd.DataFrame, lag: pd.DataFrame, lag_mode: str) -> pd.DataFrame:
    merged = projected.merge(rr, on=['outcome_id', 'component_id'], how='inner', validate='many_to_one')
    merged = merged.loc[merged['sex_use'].eq('Both') | merged['sex'].eq(merged['sex_use'])].copy()
    merged = merged.merge(pa, on=['year', 'sex', 'age_group'], how='inner', validate='many_to_many')
    merged['pif_raw'] = binary_pif(merged['inactive_s0'], merged['inactive_policy'], merged['rr_inactive_vs_active'])
    merged.loc[merged['pif_mode'].eq('ZERO_PIF'), 'pif_raw'] = 0.0
    lag_lookup = {(outcome, year): lag_multiplier(outcome, year, lag, lag_mode) for outcome in merged['outcome_id'].astype(str).unique() for year in YEARS}
    merged['disease_lag_multiplier'] = [lag_lookup[str(outcome), int(year)] for outcome, year in zip(merged['outcome_id'], merged['year'])]
    merged['pif_effective'] = merged['pif_raw'] * merged['disease_lag_multiplier']
    merged['avoided_value'] = merged['projected_value'] * merged['pif_effective']
    merged['d1_lag_mode'] = lag_mode
    merged['pif_formula'] = '[(p0*RR+1-p0)-(p1*RR+1-p1)]/(p0*RR+1-p0)'
    return merged

def calculate_hypertension(inputs: dict[str, pd.DataFrame], population: pd.DataFrame, pa: pd.DataFrame, rr_interface: pd.DataFrame, lag_mode: str) -> pd.DataFrame:
    htn = inputs['htn'][['sex', 'age_group', 'hypertension_prevalence_2025']].copy()
    htn['hypertension_prevalence_2025'] = pd.to_numeric(htn['hypertension_prevalence_2025'], errors='raise')
    base = population[['year', 'sex', 'age_group', 'population_model']].merge(htn, on=['sex', 'age_group'], validate='many_to_one')
    base['projected_value'] = base['population_model'] * base['hypertension_prevalence_2025']
    base['outcome_id'] = 'hypertension'
    base['component_id'] = 'hypertension'
    base['measure_short'] = 'Hypertension patient-years'
    base['measure_name'] = 'Hypertension patient-years'
    base['value_domain'] = 'hypertension'
    rr = rr_interface.loc[rr_interface['outcome_id'].eq('hypertension')]
    return calculate_health(base, pa, rr, inputs['lag'], lag_mode)

def select_policy_cost(inputs: dict[str, pd.DataFrame], maintenance: str, perspective: str) -> pd.DataFrame:
    parent = inputs['cost_main'].loc[inputs['cost_main']['cost_structure_scenario'].eq('STRUCTURAL_ANCHOR') & inputs['cost_main']['perspective'].eq(perspective) & inputs['cost_main']['year'].between(2025, 2034)].copy()
    if maintenance == 'FULL_MAINTENANCE':
        future = inputs['cost_main'].loc[inputs['cost_main']['cost_structure_scenario'].eq('STRUCTURAL_ANCHOR') & inputs['cost_main']['perspective'].eq(perspective) & inputs['cost_main']['year'].between(2035, 2050)].copy()
    else:
        future = inputs['cost_d9'].loc[inputs['cost_d9']['maintenance_scenario'].eq(maintenance) & inputs['cost_d9']['cost_structure_scenario'].eq('STRUCTURAL_ANCHOR') & inputs['cost_d9']['perspective'].eq(perspective)].copy()
    out = pd.concat([parent, future], ignore_index=True)
    out['year'] = pd.to_numeric(out['year'], errors='raise').astype(int)
    out['annual_programme_cost_2025_cny'] = pd.to_numeric(out['annual_programme_cost_2025_cny'], errors='coerce')
    expected = len(YEARS) * len(SCENARIOS)
    if len(out) != expected or out.duplicated(['year', 'scenario_id']).any():
        raise ValueError(f'Policy cost schedule incomplete for {maintenance}/{perspective}: {len(out)}')
    return out.sort_values(['year', 'scenario_id']).reset_index(drop=True)

def annual_summary(health: pd.DataFrame) -> pd.DataFrame:
    grouped = health.groupby(['scenario_id', 'year', 'measure_short'], as_index=False)['avoided_value'].sum()
    out = grouped.pivot_table(index=['scenario_id', 'year'], columns='measure_short', values='avoided_value', fill_value=0.0).reset_index()
    out.columns.name = None
    for col in ['DALY', 'Deaths', 'YLL', 'YLD']:
        if col not in out:
            out[col] = 0.0
    return out

def summarize_horizons(annual_burden: pd.DataFrame, annual_cases: pd.DataFrame, htn: pd.DataFrame, costs: pd.DataFrame, scenario_names: dict[str, str]) -> pd.DataFrame:
    cases = annual_cases.groupby(['scenario_id', 'year', 'measure_short'], as_index=False)['avoided_value'].sum().pivot_table(index=['scenario_id', 'year'], columns='measure_short', values='avoided_value', fill_value=0.0).reset_index()
    cases.columns.name = None
    htn_annual = htn.groupby(['scenario_id', 'year'], as_index=False)['avoided_value'].sum().rename(columns={'avoided_value': 'Hypertension patient-years'})
    annual = annual_burden.merge(cases, on=['scenario_id', 'year'], how='left').merge(htn_annual, on=['scenario_id', 'year'], how='left')
    annual = annual.merge(costs[['scenario_id', 'year', 'annual_programme_cost_2025_cny']], on=['scenario_id', 'year'], how='left')
    annual['discount_factor_health'] = 1.0 / (1.0 + HEALTH_DISCOUNT_RATE) ** (annual['year'] - BASE_YEAR)
    annual['discount_factor_cost'] = 1.0 / (1.0 + COST_DISCOUNT_RATE) ** (annual['year'] - BASE_YEAR)
    annual['discounted_daly'] = annual['DALY'] * annual['discount_factor_health']
    annual['discounted_deaths'] = annual['Deaths'] * annual['discount_factor_health']
    annual['discounted_programme_cost'] = annual['annual_programme_cost_2025_cny'] * annual['discount_factor_cost']
    rows = []
    for horizon in HORIZONS:
        end = BASE_YEAR + horizon - 1
        d = annual.loc[annual['year'].between(BASE_YEAR, end)]
        for sid in SCENARIOS:
            g = d.loc[d['scenario_id'].eq(sid)]
            cost = float(g['discounted_programme_cost'].sum(min_count=1))
            daly = float(g['discounted_daly'].sum())
            rows.append({'horizon_years': horizon, 'end_year': end, 'scenario_id': sid, 'scenario_name_cn': scenario_names[sid], 'cumulative_avoided_daly_undiscounted': float(g['DALY'].sum()), 'discounted_dalys_averted': daly, 'cumulative_avoided_deaths_undiscounted': float(g['Deaths'].sum()), 'discounted_deaths_averted': float(g['discounted_deaths'].sum()), 'cumulative_avoided_incidence': float(g.get('Incidence', pd.Series(dtype=float)).sum()), 'cumulative_avoided_prevalence_patient_years': float(g.get('Prevalence', pd.Series(dtype=float)).sum()), 'cumulative_avoided_hypertension_patient_years': float(g['Hypertension patient-years'].sum()), 'discounted_programme_cost_2025_cny': cost, 'icer_vs_s0_programme_only_cny_per_daly': cost / daly if np.isfinite(cost) and daly > 0 else np.nan, 'nmb_wtp_50000_programme_only': daly * 50000 - cost if np.isfinite(cost) else np.nan, 'nmb_wtp_150000_programme_only': daly * 150000 - cost if np.isfinite(cost) else np.nan, 'frontier_eligible': sid in FRONTIER_SCENARIOS, 'decision_view': 'INTERIM_BRIDGE_PROGRAMME_COST_ONLY'})
    return (pd.DataFrame(rows), annual)

def cost_effectiveness_frontier(summary: pd.DataFrame, horizon: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    data = summary.loc[summary['horizon_years'].eq(horizon) & summary['frontier_eligible'].eq(True) & summary['discounted_programme_cost_2025_cny'].notna()].sort_values(['discounted_dalys_averted', 'discounted_programme_cost_2025_cny']).reset_index(drop=True)
    dominated_rows, keep = ([], [])
    best_cost = np.inf
    for idx in range(len(data) - 1, -1, -1):
        row = data.iloc[idx]
        if float(row['discounted_programme_cost_2025_cny']) >= best_cost - 1e-09:
            x = row.to_dict()
            x['dominance_type'] = 'strong'
            dominated_rows.append(x)
        else:
            keep.append(row.to_dict())
            best_cost = float(row['discounted_programme_cost_2025_cny'])
    frontier = pd.DataFrame(list(reversed(keep)))
    changed = True
    while changed and len(frontier) >= 3:
        changed = False
        effects = frontier['discounted_dalys_averted'].to_numpy(float)
        costs = frontier['discounted_programme_cost_2025_cny'].to_numpy(float)
        icers = np.diff(costs) / np.diff(effects)
        for i in range(1, len(icers)):
            if icers[i] <= icers[i - 1] + 1e-12:
                removed = frontier.iloc[i].to_dict()
                removed['dominance_type'] = 'extended'
                dominated_rows.append(removed)
                frontier = frontier.drop(frontier.index[i]).reset_index(drop=True)
                changed = True
                break
    if not frontier.empty:
        frontier['incremental_cost'] = frontier['discounted_programme_cost_2025_cny'].diff()
        frontier['incremental_dalys'] = frontier['discounted_dalys_averted'].diff()
        frontier['incremental_icer'] = frontier['incremental_cost'] / frontier['incremental_dalys']
        frontier['horizon_years'] = horizon
    dominated = pd.DataFrame(dominated_rows)
    if not dominated.empty:
        dominated['horizon_years'] = horizon
    return (frontier, dominated)

def build_d4_cost_table(inputs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    candidates = inputs['cost_candidates'].set_index('outcome_id')
    selected_ids = {'bladder_cancer': 'DC-BLADDER-2020', 'breast_cancer': 'DC-BREAST-2020', 'colon_cancer': 'DC-COLON-2020', 'endometrial_cancer': 'DC-ENDOMETRIAL-2020', 'oesophageal_cancer': 'DC-OESOPH-2020', 'gastric_cancer': 'DC-GASTRIC-2020', 'renal_cancer': 'DC-RENAL-2020'}
    rows = []
    for outcome in OUTCOME_NAMES_CN:
        if outcome == 'hypertension':
            rows.append({'outcome_id': outcome, 'd4_status': 'MISSING_INCIDENCE_AND_STRICT_FIRST_YEAR_CONNECTION', 'cost_2025_cny': np.nan, 'cost_id': ''})
        elif outcome in {'type2_diabetes', 'depression', 'dementia'}:
            rows.append({'outcome_id': outcome, 'd4_status': 'MISSING_STRICT_FIRST_YEAR_COST', 'cost_2025_cny': np.nan, 'cost_id': ''})
        elif outcome == 'coronary_heart_disease':
            value = 205.47 * 6.8974 * 1.03330083672
            rows.append({'outcome_id': outcome, 'd4_status': 'PROXY_STRICT_FIRST_YEAR_AVAILABLE', 'cost_2025_cny': value, 'cost_id': 'COST002_SANTOS_2020_CONVERTED'})
        elif outcome == 'stroke':
            value = 791.19 * 6.8974 * 1.03330083672
            rows.append({'outcome_id': outcome, 'd4_status': 'PROXY_STRICT_FIRST_YEAR_AVAILABLE', 'cost_2025_cny': value, 'cost_id': 'COST005_SANTOS_2020_CONVERTED'})
        else:
            cid = selected_ids[outcome]
            row = inputs['cost_candidates'].loc[inputs['cost_candidates']['cost_id'].eq(cid)].iloc[0]
            rows.append({'outcome_id': outcome, 'd4_status': 'PROXY_STRICT_FIRST_YEAR_AVAILABLE', 'cost_2025_cny': float(row.cost_2025_cny), 'cost_id': cid})
    out = pd.DataFrame(rows)
    out['cost_boundary'] = 'incident case first-year direct medical cost'
    out['public_payer_share'] = np.nan
    out['public_payer_net_CEA_ready'] = 'NO'
    return out

def calculate_partial_medical_savings(case_health: pd.DataFrame, d4_costs: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    inc = case_health.loc[case_health['measure_short'].eq('Incidence')].copy()
    inc = inc.groupby(['year', 'scenario_id', 'outcome_id'], as_index=False)['avoided_value'].sum()
    inc = inc.merge(d4_costs, on='outcome_id', how='left', validate='many_to_one')
    inc['partial_direct_medical_savings_2025_cny'] = inc['avoided_value'] * inc['cost_2025_cny']
    coverage = inc.groupby(['scenario_id', 'year'], as_index=False).agg(total_avoided_incidence=('avoided_value', 'sum'), covered_avoided_incidence=('avoided_value', lambda x: float(x[inc.loc[x.index, 'cost_2025_cny'].notna()].sum())), partial_direct_medical_savings_2025_cny=('partial_direct_medical_savings_2025_cny', 'sum'))
    coverage['avoided_incidence_coverage_share'] = coverage['covered_avoided_incidence'] / coverage['total_avoided_incidence'].replace(0, np.nan)
    coverage['result_status'] = 'INCOMPLETE_D4_TOTAL_DIRECT_MEDICAL_SAVINGS_NOT_HEADLINE'
    return (inc, coverage)

def calculate_dementia_long_term_care(case_health: pd.DataFrame, inputs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    prevalence = case_health.loc[case_health['outcome_id'].eq('dementia') & case_health['measure_short'].eq('Prevalence')].copy()
    prevalence = prevalence.groupby(['year', 'scenario_id'], as_index=False)['avoided_value'].sum()
    candidates = inputs['cost_candidates'].set_index('cost_id')
    total = float(candidates.loc['DC-DEM-CN-SOCIAL-2015', 'cost_2025_cny'])
    direct = float(candidates.loc['DC-DEM-CN-2015', 'cost_2025_cny'])
    care = total - direct
    prevalence['dementia_nonmedical_and_informal_care_cost_2025_cny_per_patient_year'] = care
    prevalence['dementia_long_term_care_savings_2025_cny'] = prevalence['avoided_value'] * care
    prevalence['d10_status'] = 'PROVISIONAL_D10B_SOCIAL_COST_SATELLITE'
    return prevalence

def summarize_structural_case(case: AnalysisCase, summary: pd.DataFrame) -> pd.DataFrame:
    focus = summary.loc[summary['scenario_id'].eq('S6')].copy()
    focus.insert(0, 'case_id', case.case_id)
    focus.insert(1, 'changed_decision', case.changed_decision)
    focus['d1_lag'] = case.d1_lag
    focus['d2_s0'] = case.d2_s0
    focus['d3_disease'] = case.d3_disease
    focus['d9_maintenance'] = case.d9_maintenance
    focus['stroke_mapping'] = case.stroke_mapping
    return focus

def compare_cvd_projection(inputs: dict[str, pd.DataFrame], burden_projection: pd.DataFrame) -> pd.DataFrame:
    cvd = inputs['cvd_annual'].copy()
    cvd['component_id'] = cvd['disease_id'].map({'IHD': 'coronary_heart_disease', 'IS': 'ischemic_stroke'})
    measure_map = {'deaths': 'Deaths', 'yll': 'YLL', 'yld': 'YLD', 'daly': 'DALY'}
    left = burden_projection.loc[burden_projection['component_id'].isin(['coronary_heart_disease', 'ischemic_stroke']) & burden_projection['year'].between(2025, 2034), ['year', 'component_id', 'sex', 'age_group', 'measure_short', 'projected_value']].copy()
    right = cvd.melt(id_vars=['year', 'component_id', 'sex', 'age_group'], value_vars=list(measure_map), var_name='metric', value_name='cvd_v16_value')
    right['measure_short'] = right['metric'].map(measure_map)
    comp = left.merge(right.drop(columns='metric'), on=['year', 'component_id', 'sex', 'age_group', 'measure_short'], how='outer', validate='one_to_one')
    comp['absolute_difference'] = comp['projected_value'] - comp['cvd_v16_value']
    comp['relative_difference'] = comp['absolute_difference'] / comp['cvd_v16_value'].abs().clip(lower=1e-12)
    return comp

def build_stroke_pif_audit(pa: pd.DataFrame, rr_interface: pd.DataFrame, lag: pd.DataFrame) -> pd.DataFrame:
    stroke = rr_interface.loc[rr_interface['component_id'].eq('ischemic_stroke')].iloc[0]
    out = pa.copy()
    out['rr_used_to_calculate_common_stroke_pif'] = float(stroke['rr_inactive_vs_active'])
    out['common_stroke_pif_raw'] = binary_pif(out['inactive_s0'], out['inactive_policy'], out['rr_used_to_calculate_common_stroke_pif'])
    out['stroke_lag_multiplier'] = [lag_multiplier('stroke', int(year), lag, 'group_specific') for year in out['year']]
    out['common_stroke_pif_effective'] = out['common_stroke_pif_raw'] * out['stroke_lag_multiplier']
    out['main_is_pif_effective'] = out['common_stroke_pif_effective']
    out['main_ich_pif_effective'] = out['common_stroke_pif_effective']
    out['main_sah_pif_effective'] = out['common_stroke_pif_effective']
    out['is_only_is_pif_effective'] = out['common_stroke_pif_effective']
    out['is_only_ich_pif_effective'] = 0.0
    out['is_only_sah_pif_effective'] = 0.0
    out['source_parameter_specificity'] = 'ISCHEMIC_STROKE_SPECIFIC'
    out['main_mapping_interpretation'] = 'COMMON_STROKE_PIF_COMPONENT_ALLOCATION_NOT_ICH_OR_SAH_RR'
    return out

def build_stroke_mapping_difference(structural: pd.DataFrame) -> pd.DataFrame:
    metrics = ['cumulative_avoided_daly_undiscounted', 'discounted_dalys_averted', 'cumulative_avoided_deaths_undiscounted', 'discounted_deaths_averted', 'cumulative_avoided_incidence', 'discounted_programme_cost_2025_cny', 'icer_vs_s0_programme_only_cny_per_daly', 'nmb_wtp_50000_programme_only', 'nmb_wtp_150000_programme_only']
    main = structural.loc[structural['case_id'].eq('PRIMARY')].set_index('horizon_years')
    is_only = structural.loc[structural['case_id'].eq('IS_ONLY')].set_index('horizon_years')
    rows: list[dict[str, object]] = []
    for horizon in HORIZONS:
        for metric in metrics:
            main_value = float(main.loc[horizon, metric])
            sensitivity_value = float(is_only.loc[horizon, metric])
            rows.append({'scenario_id': 'S6', 'horizon_years': horizon, 'metric': metric, 'common_stroke_pif_main': main_value, 'is_only': sensitivity_value, 'is_only_minus_main': sensitivity_value - main_value, 'relative_change_is_only_vs_main': (sensitivity_value - main_value) / main_value if main_value else np.nan})
    return pd.DataFrame(rows)
