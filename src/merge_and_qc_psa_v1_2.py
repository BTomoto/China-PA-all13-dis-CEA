from __future__ import annotations
from model_io import install as _configure_io
_configure_io()
import argparse
import json
import os
from pathlib import Path
import numpy as np
import pandas as pd
ROOT = Path(__file__).resolve().parent.parent
ANALYSIS_ROOT = Path(os.environ.get('ALLDIS_ANALYSIS_ROOT', str(ROOT))).resolve()
WTP_VALUES = [50000, 100000, 150000]
PERSPECTIVES = {'PROGRAMME_ONLY': 'nmb_programme_only_wtp_{wtp}', 'PARTIAL_PUBLIC_PAYER': 'nmb_partial_payer_wtp_{wtp}'}

def summarize(draws: pd.DataFrame) -> pd.DataFrame:
    metrics = ['discounted_dalys_averted', 'undiscounted_dalys_averted', 'discounted_deaths_averted', 'undiscounted_incidence_averted', 'discounted_programme_cost_2025_cny', 'discounted_partial_direct_medical_savings_2025_cny', 'discounted_partial_public_payer_net_cost_2025_cny', 'programme_only_icer_cny_per_daly', 'partial_payer_icer_cny_per_daly']
    rows = []
    for (horizon, sid), g in draws.groupby(['horizon_years', 'scenario_id'], sort=False):
        for metric in metrics:
            x = pd.to_numeric(g[metric], errors='coerce').dropna()
            if x.empty:
                continue
            rows.append({'horizon_years': int(horizon), 'scenario_id': sid, 'metric': metric, 'n_draws': int(len(x)), 'mean': float(x.mean()), 'sd': float(x.std(ddof=1)), 'p2_5': float(x.quantile(0.025)), 'median': float(x.quantile(0.5)), 'p97_5': float(x.quantile(0.975)), 'result_status': 'FORMAL'})
    return pd.DataFrame(rows)

def build_ceac(draws: pd.DataFrame, formal: bool) -> tuple[pd.DataFrame, pd.DataFrame]:
    eligible = draws.loc[draws['frontier_eligible'].astype(bool)].copy()
    ceac_rows = []
    ceaf_rows = []
    for horizon in sorted(eligible['horizon_years'].unique()):
        h = eligible.loc[eligible['horizon_years'].eq(horizon)].copy()
        for perspective, pattern in PERSPECTIVES.items():
            for wtp in WTP_VALUES:
                col = pattern.format(wtp=wtp)
                pivot = h.pivot(index='draw_id', columns='scenario_id', values=col)
                best = pivot.idxmax(axis=1)
                expected = pivot.mean(axis=0)
                ceaf_sid = str(expected.idxmax())
                for sid in sorted(pivot.columns):
                    ceac_rows.append({'horizon_years': int(horizon), 'perspective': perspective, 'wtp_cny_per_daly': int(wtp), 'scenario_id': sid, 'probability_cost_effective': float((best == sid).mean()), 'expected_nmb_2025_cny': float(expected[sid]), 'n_draws': int(len(best)), 'result_status': 'FORMAL_PSA'})
                ceaf_rows.append({'horizon_years': int(horizon), 'perspective': perspective, 'wtp_cny_per_daly': int(wtp), 'ceaf_scenario_id': ceaf_sid, 'ceaf_probability': float((best == ceaf_sid).mean()), 'maximum_expected_nmb_2025_cny': float(expected[ceaf_sid]), 'n_draws': int(len(best)), 'result_status': 'FORMAL_PSA'})
    return (pd.DataFrame(ceac_rows), pd.DataFrame(ceaf_rows))

def batch_stability(draws: pd.DataFrame) -> pd.DataFrame:
    metrics = ['discounted_dalys_averted', 'discounted_programme_cost_2025_cny', 'discounted_partial_public_payer_net_cost_2025_cny']
    focus = draws.loc[draws['scenario_id'].eq('S6') & draws['horizon_years'].isin([5, 10])].copy()
    rows = []
    for horizon in [5, 10]:
        g = focus.loc[focus['horizon_years'].eq(horizon)]
        for metric in metrics:
            overall = float(g[metric].mean())
            for batch, bg in g.groupby('batch_id'):
                value = float(bg[metric].mean())
                rows.append({'horizon_years': horizon, 'scenario_id': 'S6', 'metric': metric, 'batch_id': int(batch), 'batch_mean': value, 'overall_mean': overall, 'relative_difference': (value - overall) / overall if overall != 0 else np.nan, 'n_draws': int(bg['draw_id'].nunique())})
    return pd.DataFrame(rows)

def convergence(draws: pd.DataFrame, formal: bool) -> pd.DataFrame:
    focus = draws.loc[draws['scenario_id'].eq('S6') & draws['horizon_years'].eq(10)].sort_values('draw_id')
    checkpoints = [25, 50, 100, 150, 200]
    if formal:
        checkpoints += [500, 1000, 2000, 5000, 10000]
    checkpoints = [x for x in checkpoints if x <= len(focus)]
    rows = []
    metrics = ['discounted_dalys_averted', 'discounted_programme_cost_2025_cny', 'discounted_partial_public_payer_net_cost_2025_cny']
    for n in checkpoints:
        g = focus.iloc[:n]
        for metric in metrics:
            mean = float(g[metric].mean())
            sd = float(g[metric].std(ddof=1))
            rows.append({'checkpoint_draws': n, 'scenario_id': 'S6', 'horizon_years': 10, 'metric': metric, 'cumulative_mean': mean, 'cumulative_sd': sd, 'standard_error': sd / np.sqrt(n), 'relative_standard_error': sd / np.sqrt(n) / abs(mean) if mean else np.nan})
    return pd.DataFrame(rows)
