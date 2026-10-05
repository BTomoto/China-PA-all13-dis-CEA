from __future__ import annotations
from model_io import install as _configure_io
_configure_io()
import gzip
import hashlib
import json
import math
import subprocess
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd
WTP_VALUES = (50000, 100000, 150000)
PERSPECTIVES = {'PROGRAMME_ONLY': {'cost': 'discounted_programme_cost_2025_cny', 'nmb': 'nmb_programme_only_wtp_{wtp}'}, 'PARTIAL_PUBLIC_PAYER': {'cost': 'discounted_partial_public_payer_net_cost_2025_cny', 'nmb': 'nmb_partial_payer_wtp_{wtp}'}}

def frontier_for_group(group: pd.DataFrame, cost_column: str) -> pd.DataFrame:
    means = group.groupby('scenario_id', as_index=False).agg(mean_discounted_dalys=('discounted_dalys_averted', 'mean'), mean_cost_2025_cny=(cost_column, 'mean')).sort_values(['mean_discounted_dalys', 'mean_cost_2025_cny']).reset_index(drop=True)
    status = {scenario: 'CANDIDATE' for scenario in means['scenario_id']}
    for row in means.itertuples(index=False):
        competitors = means.loc[means['scenario_id'].ne(row.scenario_id)]
        dominated = ((competitors['mean_discounted_dalys'] >= row.mean_discounted_dalys) & (competitors['mean_cost_2025_cny'] <= row.mean_cost_2025_cny) & ((competitors['mean_discounted_dalys'] > row.mean_discounted_dalys) | (competitors['mean_cost_2025_cny'] < row.mean_cost_2025_cny))).any()
        if dominated:
            status[row.scenario_id] = 'STRICTLY_DOMINATED'
    frontier = means.loc[means['scenario_id'].map(status).eq('CANDIDATE')].copy()
    frontier = frontier.sort_values('mean_discounted_dalys').reset_index(drop=True)
    changed = True
    while changed and len(frontier) >= 3:
        changed = False
        effects = frontier['mean_discounted_dalys'].to_numpy(float)
        costs = frontier['mean_cost_2025_cny'].to_numpy(float)
        incremental_effects = np.diff(effects)
        incremental_costs = np.diff(costs)
        icers = np.divide(incremental_costs, incremental_effects, out=np.full_like(incremental_costs, np.inf), where=incremental_effects > 0)
        for edge in range(len(icers) - 1):
            if icers[edge] >= icers[edge + 1]:
                removed = str(frontier.iloc[edge + 1]['scenario_id'])
                status[removed] = 'EXTENDED_DOMINATED'
                frontier = frontier.drop(frontier.index[edge + 1]).reset_index(drop=True)
                changed = True
                break
    for scenario in frontier['scenario_id']:
        status[str(scenario)] = 'FRONTIER'
    means['frontier_status'] = means['scenario_id'].map(status)
    means['previous_frontier_scenario'] = pd.NA
    means['incremental_discounted_dalys'] = np.nan
    means['incremental_cost_2025_cny'] = np.nan
    means['incremental_icer_cny_per_daly'] = np.nan
    frontier = frontier.sort_values('mean_discounted_dalys').reset_index(drop=True)
    for index in range(1, len(frontier)):
        current = frontier.iloc[index]
        previous = frontier.iloc[index - 1]
        delta_effect = float(current['mean_discounted_dalys'] - previous['mean_discounted_dalys'])
        delta_cost = float(current['mean_cost_2025_cny'] - previous['mean_cost_2025_cny'])
        mask = means['scenario_id'].eq(current['scenario_id'])
        means.loc[mask, 'previous_frontier_scenario'] = previous['scenario_id']
        means.loc[mask, 'incremental_discounted_dalys'] = delta_effect
        means.loc[mask, 'incremental_cost_2025_cny'] = delta_cost
        means.loc[mask, 'incremental_icer_cny_per_daly'] = delta_cost / delta_effect if delta_effect > 0 else np.nan
    return means

def build_frontier_and_incremental(draws: pd.DataFrame, ceac: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    frontier_rows: list[pd.DataFrame] = []
    incremental_rows: list[pd.DataFrame] = []
    eligible = draws.loc[draws['frontier_eligible'].astype(bool)].copy()
    for horizon in sorted(eligible['horizon_years'].unique()):
        horizon_data = eligible.loc[eligible['horizon_years'].eq(horizon)]
        for perspective, columns in PERSPECTIVES.items():
            frontier = frontier_for_group(horizon_data, columns['cost'])
            frontier.insert(0, 'perspective', perspective)
            frontier.insert(0, 'horizon_years', int(horizon))
            frontier_rows.append(frontier)
            incremental = frontier.copy()
            for wtp in WTP_VALUES:
                nmb_column = columns['nmb'].format(wtp=wtp)
                expected_nmb = horizon_data.groupby('scenario_id')[nmb_column].mean()
                probability = ceac.loc[ceac['horizon_years'].eq(horizon) & ceac['perspective'].eq(perspective) & ceac['wtp_cny_per_daly'].eq(wtp)].set_index('scenario_id')['probability_cost_effective']
                incremental[f'expected_nmb_wtp_{wtp}_2025_cny'] = incremental['scenario_id'].map(expected_nmb)
                incremental[f'probability_cost_effective_wtp_{wtp}'] = incremental['scenario_id'].map(probability)
            incremental_rows.append(incremental)
    return (pd.concat(frontier_rows, ignore_index=True), pd.concat(incremental_rows, ignore_index=True))

def build_evpi(draws: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    eligible = draws.loc[draws['frontier_eligible'].astype(bool)].copy()
    for horizon in sorted(eligible['horizon_years'].unique()):
        horizon_data = eligible.loc[eligible['horizon_years'].eq(horizon)]
        for perspective, columns in PERSPECTIVES.items():
            for wtp in WTP_VALUES:
                nmb_column = columns['nmb'].format(wtp=wtp)
                pivot = horizon_data.pivot(index='draw_id', columns='scenario_id', values=nmb_column)
                expected_by_scenario = pivot.mean(axis=0)
                selected = str(expected_by_scenario.idxmax())
                current_information = float(expected_by_scenario.max())
                perfect_information = float(pivot.max(axis=1).mean())
                rows.append({'horizon_years': int(horizon), 'perspective': perspective, 'wtp_cny_per_daly': int(wtp), 'current_information_optimal_scenario': selected, 'maximum_expected_nmb_2025_cny': current_information, 'expected_nmb_with_perfect_information_2025_cny': perfect_information, 'evpi_2025_cny': perfect_information - current_information, 'n_draws': int(len(pivot)), 'result_status': 'FORMAL_PSA'})
    return pd.DataFrame(rows)
