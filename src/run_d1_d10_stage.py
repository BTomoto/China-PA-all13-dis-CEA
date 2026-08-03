from __future__ import annotations

import hashlib
import json
import math
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


SCRIPT_PATH = Path(__file__).resolve()
BUNDLE_ROOT = SCRIPT_PATH.parent.parent
PORTABLE_MODE = (BUNDLE_ROOT / "input" / "parent" / "中国20岁以上成年人身体活动不足13结局综合政策CEA父数据库_v1.xlsx").exists()

if PORTABLE_MODE:
    ROOT = BUNDLE_ROOT
    PARENT_DB = ROOT / "input" / "parent" / "中国20岁以上成年人身体活动不足13结局综合政策CEA父数据库_v1.xlsx"
    WPP_FUTURE = ROOT / "input" / "population" / "WPP2024_China_age_sex_2025_2050.csv"
    WPP_HISTORY = ROOT / "input" / "population" / "WPP2024_China_age_sex_history.csv"
    CVD_CORE = ROOT / "input" / "cvd_v16_core"
    CVD_COST_LONG = ROOT / "input" / "policy_costs_long_term"
    HTN_MAIN = ROOT / "input" / "hypertension" / "hypertension_5y_main.csv"
    OLD_COSTS = ROOT / "input" / "disease_costs" / "disease_cost_candidates_harmonized_2025cny.csv"
    GBD_BURDEN_STANDARDIZED = ROOT / "input" / "gbd_standardized" / "GBD_burden_components.csv.gz"
    GBD_CASES_STANDARDIZED = ROOT / "input" / "gbd_standardized" / "GBD_cases_components.csv.gz"
    OUTPUT = ROOT
else:
    ROOT = SCRIPT_PATH.parents[2]
    PARENT_DB = ROOT / "upload" / "中国20岁以上成年人身体活动不足13结局综合政策CEA父数据库_v1.xlsx"
    WPP_FUTURE = ROOT / "outputs" / "ALLdis_2025_2050迁移阶段_v1.0" / "input" / "processed_wpp" / "WPP2024_China_age_sex_2025_2050.csv"
    WPP_HISTORY = ROOT / "work" / "runs" / "repro_v29_20260801" / "input" / "processed_wpp" / "WPP2024_China_age_sex_2018_2023.csv"
    CVD_CORE = ROOT / "work" / "extracted" / "cvd_v16" / "CVD_CEA_v16_prepublication_revision" / "input" / "core"
    CVD_COST_LONG = ROOT / "outputs" / "ALLdis_CVDv16与成本迁移阶段_v1.1" / "input" / "policy_costs_long_term"
    HTN_MAIN = ROOT / "work" / "runs" / "repro_v29_20260801" / "input" / "hypertension" / "hypertension_5y_main.csv"
    OLD_COSTS = ROOT / "work" / "runs" / "repro_v29_20260801" / "input" / "disease_costs_v2" / "disease_cost_candidates_harmonized_2025cny.csv"
    GBD_BURDEN_STANDARDIZED = None
    GBD_CASES_STANDARDIZED = None
    OUTPUT = ROOT / "outputs" / "ALLdis_父数据库第一阶段D1_D10_v1.1"

BASE_YEAR = 2025
END_YEAR = 2050
YEARS = list(range(BASE_YEAR, END_YEAR + 1))
HORIZONS = [5, 10, 26]
HEALTH_DISCOUNT_RATE = 0.03
COST_DISCOUNT_RATE = 0.03
AGE_GROUPS = ["20-24", "25-29", "30-34", "35-39", "40-44", "45-49", "50-54", "55-59", "60-64", "65-69", "70+"]
SEXES = ["Female", "Male"]
SCENARIOS = [f"S{i}" for i in range(8)]
FRONTIER_SCENARIOS = [f"S{i}" for i in range(7)]
MEASURE_SHORT = {
    "DALYs (Disability-Adjusted Life Years)": "DALY",
    "YLLs (Years of Life Lost)": "YLL",
    "YLDs (Years Lived with Disability)": "YLD",
    "Deaths": "Deaths",
    "Incidence": "Incidence",
    "Prevalence": "Prevalence",
}
COMPONENT_NAMES = {
    495: "ischemic_stroke",
    496: "intracerebral_hemorrhage",
    497: "subarachnoid_hemorrhage",
}
OUTCOME_NAMES_CN = {
    "coronary_heart_disease": "缺血性心脏病",
    "stroke": "卒中（3亚型合计）",
    "type2_diabetes": "2型糖尿病",
    "hypertension": "高血压",
    "bladder_cancer": "膀胱癌",
    "breast_cancer": "乳腺癌",
    "colon_cancer": "结直肠癌",
    "endometrial_cancer": "子宫内膜癌（GBD子宫癌代理）",
    "oesophageal_cancer": "食管癌",
    "gastric_cancer": "胃癌",
    "renal_cancer": "肾癌",
    "dementia": "痴呆",
    "depression": "抑郁症",
}


@dataclass(frozen=True)
class AnalysisCase:
    case_id: str
    d1_lag: str = "group_specific"
    d2_s0: str = "main_damped"
    d3_disease: str = "main_2010_2023_damped"
    d9_maintenance: str = "FULL_MAINTENANCE"
    changed_decision: str = "PRIMARY"


CASES = [
    AnalysisCase("PRIMARY"),
    AnalysisCase("D1_IMMEDIATE", d1_lag="immediate", changed_decision="D1"),
    AnalysisCase("D1_DELAYED_PLUS2", d1_lag="delayed_plus2", changed_decision="D1"),
    AnalysisCase("D2_STABLE_AFTER_2034", d2_s0="stable_after_2034", changed_decision="D2"),
    AnalysisCase("D2_CONTINUED", d2_s0="constrained_continuation", changed_decision="D2"),
    AnalysisCase("D3_FIXED_2023_RATE", d3_disease="fixed_2023_rate", changed_decision="D3"),
    AnalysisCase("D3_RECENT_2018_2023", d3_disease="recent_2018_2023_damped", changed_decision="D3"),
    AnalysisCase("D3_CONTINUED", d3_disease="constrained_trend_continuation", changed_decision="D3"),
    AnalysisCase("D9_REDUCED_75", d9_maintenance="REDUCED_75_PERCENT", changed_decision="D9"),
    AnalysisCase("D9_STOP_AFTER_2034", d9_maintenance="STOP_AFTER_2034", changed_decision="D9"),
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_parent_sheet(sheet: str) -> pd.DataFrame:
    df = pd.read_excel(PARENT_DB, sheet_name=sheet, header=2)
    return df.dropna(how="all").reset_index(drop=True)


def normalize_age(value: object) -> str:
    return str(value).strip().replace(" years", "").replace(" year", "")


def load_inputs() -> dict[str, pd.DataFrame]:
    pa = read_parent_sheet("PA_binary_20plus")
    pa = pa[["sex", "age_group", "n", "inactive_n", "moderate_n", "high_n", "p_inactive"]].copy()
    pa["low_prev"] = pd.to_numeric(pa["inactive_n"], errors="raise") / pd.to_numeric(pa["n"], errors="raise")
    pa["moderate_prev"] = pd.to_numeric(pa["moderate_n"], errors="raise") / pd.to_numeric(pa["n"], errors="raise")
    pa["high_prev"] = pd.to_numeric(pa["high_n"], errors="raise") / pd.to_numeric(pa["n"], errors="raise")
    pa["probability_sum"] = pa[["low_prev", "moderate_prev", "high_prev"]].sum(axis=1)

    rr = read_parent_sheet("RR_main")
    lag = read_parent_sheet("lag_assumptions")
    population_parent = read_parent_sheet("population_projection")
    if GBD_BURDEN_STANDARDIZED is not None and GBD_BURDEN_STANDARDIZED.exists():
        gbd_burden = pd.read_csv(GBD_BURDEN_STANDARDIZED, encoding="utf-8-sig")
    else:
        gbd_burden = read_parent_sheet("GBD_burden_components")
    if GBD_CASES_STANDARDIZED is not None and GBD_CASES_STANDARDIZED.exists():
        gbd_cases = pd.read_csv(GBD_CASES_STANDARDIZED, encoding="utf-8-sig")
    else:
        gbd_cases = read_parent_sheet("GBD_cases_components")
    mapping = read_parent_sheet("disease_mapping")
    policy_parent = read_parent_sheet("policy_effects")
    qc_parent = read_parent_sheet("QC_summary")

    policy = pd.read_csv(CVD_CORE / "policy_scenarios.csv", encoding="utf-8-sig")
    rr_cvd = pd.read_csv(CVD_CORE / "rr_3level_ihd_is.csv", encoding="utf-8-sig")
    pa_cvd = pd.read_csv(CVD_CORE / "pa_baseline_2025_3level.csv", encoding="utf-8-sig")
    cvd_annual = pd.read_csv(CVD_CORE / "gbd_ihd_is_annual_2025_2034.csv", encoding="utf-8-sig")
    htn = pd.read_csv(HTN_MAIN, encoding="utf-8-sig")
    cost_candidates = pd.read_csv(OLD_COSTS, encoding="utf-8-sig")
    cost_main = pd.read_csv(CVD_COST_LONG / "policy_cost_2025_2050_D9_main_interim.csv", encoding="utf-8-sig")
    cost_d9 = pd.read_csv(CVD_COST_LONG / "policy_cost_2035_2050_D9_sensitivity_provisional.csv", encoding="utf-8-sig")
    wpp_history = pd.read_csv(WPP_HISTORY, encoding="utf-8-sig")
    wpp_future = pd.read_csv(WPP_FUTURE, encoding="utf-8-sig")
    return locals()


def build_population(inputs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    parent = inputs["population_parent"]
    baseline = parent.loc[parent["year"].eq(BASE_YEAR), ["sex", "age_group", "baseline_population_2025"]].copy()
    baseline["baseline_population_2025"] = pd.to_numeric(baseline["baseline_population_2025"], errors="raise")
    wpp = inputs["wpp_future"].loc[
        inputs["wpp_future"]["variant"].eq("Medium"), ["year", "sex", "age_group", "population"]
    ].copy()
    wpp["year"] = pd.to_numeric(wpp["year"], errors="raise").astype(int)
    wpp["population"] = pd.to_numeric(wpp["population"], errors="raise")
    wpp = wpp.loc[wpp["year"].between(BASE_YEAR, END_YEAR)].copy()
    anchor = wpp.loc[wpp["year"].eq(BASE_YEAR), ["sex", "age_group", "population"]].rename(columns={"population": "wpp_population_2025"})
    out = wpp.merge(anchor, on=["sex", "age_group"], validate="many_to_one").merge(
        baseline, on=["sex", "age_group"], validate="many_to_one"
    )
    out["wpp_index_2025"] = out["population"] / out["wpp_population_2025"]
    out["population_model"] = out["population"]
    out["parent_to_wpp_2025_ratio"] = out["baseline_population_2025"] / out["wpp_population_2025"]
    out["population_source"] = "UN WPP 2024 Medium annual age-sex population; CVD v16 numeric parent"
    out = out[["year", "sex", "age_group", "population_model", "population", "wpp_population_2025", "baseline_population_2025", "parent_to_wpp_2025_ratio", "wpp_index_2025", "population_source"]]
    out = out.sort_values(["year", "sex", "age_group"]).reset_index(drop=True)
    expected = len(YEARS) * len(SEXES) * len(AGE_GROUPS)
    if len(out) != expected or out["population_model"].isna().any() or (out["population_model"] <= 0).any():
        raise ValueError("2025—2050 model population is incomplete")
    return out


def disease_trend_multiplier(scenario: str, year: int) -> float:
    if year <= 2034:
        return 1.0
    if scenario in {"main_2010_2023_damped", "recent_2018_2023_damped"}:
        return max(0.0, (2040 - year) / 6.0)
    if scenario == "fixed_2023_rate":
        return 0.0
    if scenario == "constrained_trend_continuation":
        return 1.0
    raise ValueError(scenario)


def cumulative_disease_exposure(scenario: str, year: int) -> float:
    if scenario == "fixed_2023_rate":
        return 0.0
    total = 1.0  # 2024 transition after the 2023 anchor
    for y in range(2025, int(year) + 1):
        total += disease_trend_multiplier(scenario, y)
    return total


def fit_log_rate_slope(years: np.ndarray, values: np.ndarray) -> tuple[float, float, int]:
    valid = np.isfinite(years) & np.isfinite(values) & (values >= 0)
    years = years[valid].astype(int)
    values = values[valid].astype(float)
    if len(years) == 0:
        return 0.0, math.nan, 2023
    order = np.argsort(years)
    years, values = years[order], values[order]
    anchor_year = int(years[-1])
    anchor = float(values[-1])
    positive = values > 0
    if positive.sum() < 2:
        return 0.0, anchor, anchor_year
    slope = float(np.polyfit(years[positive], np.log(values[positive]), 1)[0])
    return float(np.clip(slope, -0.10, 0.10)), anchor, anchor_year


def prepare_gbd(raw: pd.DataFrame) -> pd.DataFrame:
    df = raw.copy()
    df["year"] = pd.to_numeric(df["year"], errors="raise").astype(int)
    df["cause_id"] = pd.to_numeric(df["cause_id"], errors="raise").astype(int)
    for col in ["val", "lower", "upper"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["age_group"] = df["age_name"].map(normalize_age)
    df["sex"] = df["sex_name"].astype(str)
    df["outcome_id"] = df["lancet_outcome_id"].astype(str)
    df["outcome_name"] = df["lancet_outcome_name"].astype(str)
    df["component_id"] = [COMPONENT_NAMES.get(int(cid), str(oid)) for cid, oid in zip(df["cause_id"], df["outcome_id"])]
    df = df.loc[df["year"].le(2023) & df["age_group"].isin(AGE_GROUPS) & df["sex"].isin(SEXES)].copy()
    female_only = df["outcome_id"].isin(["breast_cancer", "endometrial_cancer"])
    df = df.loc[~female_only | df["sex"].eq("Female")].copy()
    return df


def project_gbd(raw: pd.DataFrame, value_domain: str, population: pd.DataFrame, history_pop: pd.DataFrame, scenario: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = prepare_gbd(raw)
    if scenario == "recent_2018_2023_damped":
        df = df.loc[df["year"].ge(2018)].copy()
    hp = history_pop[["year", "sex", "age_group", "population"]].copy()
    hp["year"] = pd.to_numeric(hp["year"], errors="raise").astype(int)
    hp["population"] = pd.to_numeric(hp["population"], errors="raise")
    df = df.merge(hp, on=["year", "sex", "age_group"], how="left", validate="many_to_one")
    if df["population"].isna().any():
        raise ValueError("Historical WPP denominators are incomplete")
    df["rate"] = df["val"] / df["population"]
    pop_lookup = population.set_index(["year", "sex", "age_group"])["population_model"].to_dict()
    group_cols = ["outcome_id", "outcome_name", "component_id", "cause_id", "cause_name", "sex", "age_group", "measure_name"]
    rows: list[dict[str, object]] = []
    slope_rows: list[dict[str, object]] = []
    for keys, group in df.groupby(group_cols, dropna=False, sort=False):
        g = group.sort_values("year")
        slope, anchor_rate, anchor_year = fit_log_rate_slope(g["year"].to_numpy(float), g["rate"].to_numpy(float))
        anchor_row = g.loc[g["year"].eq(anchor_year)].iloc[-1]
        anchor_val = float(anchor_row["val"])
        low_ratio = min(float(anchor_row["lower"]) / anchor_val, 1.0) if anchor_val > 0 and pd.notna(anchor_row["lower"]) else 1.0
        high_ratio = max(float(anchor_row["upper"]) / anchor_val, 1.0) if anchor_val > 0 and pd.notna(anchor_row["upper"]) else 1.0
        slope_rows.append({
            "outcome_id": keys[0], "outcome_name": keys[1], "component_id": keys[2], "cause_id": keys[3],
            "cause_name": keys[4], "sex": keys[5], "age_group": keys[6], "measure_name": keys[7],
            "value_domain": value_domain, "anchor_year": anchor_year, "anchor_rate": anchor_rate,
            "history_start_year": int(g["year"].min()), "history_end_year": int(g["year"].max()),
            "annual_log_rate_slope_history_capped": slope, "raw_history_years": int(g["year"].nunique()),
            "d3_scenario": scenario,
        })
        for year in YEARS:
            pop = float(pop_lookup[(year, keys[5], keys[6])])
            if not np.isfinite(anchor_rate) or anchor_rate <= 0:
                rate = 0.0 if anchor_rate == 0 else np.nan
            else:
                rate = float(anchor_rate * np.exp(slope * cumulative_disease_exposure(scenario, year)))
            value = rate * pop if np.isfinite(rate) else np.nan
            rows.append({
                "outcome_id": keys[0], "outcome_name": keys[1], "component_id": keys[2], "cause_id": keys[3],
                "cause_name": keys[4], "sex": keys[5], "age_group": keys[6], "measure_name": keys[7],
                "measure_short": MEASURE_SHORT.get(str(keys[7]), str(keys[7])), "value_domain": value_domain,
                "year": year, "projected_value": value, "projected_lower": value * low_ratio,
                "projected_upper": value * high_ratio, "population_model": pop,
                "projected_rate_per_100k": rate * 100000 if np.isfinite(rate) else np.nan,
                "anchor_year": anchor_year, "anchor_rate": anchor_rate,
                "history_start_year": int(g["year"].min()), "history_end_year": int(g["year"].max()),
                "annual_log_rate_slope_history_capped": slope,
                "annual_slope_multiplier": disease_trend_multiplier(scenario, year),
                "cumulative_slope_exposure_since_2023": cumulative_disease_exposure(scenario, year),
                "d3_scenario": scenario,
            })
    out = pd.DataFrame(rows)
    slopes = pd.DataFrame(slope_rows)
    if value_domain == "burden":
        idx_cols = ["outcome_id", "component_id", "cause_id", "sex", "age_group", "year"]
        for keys, indices in out.groupby(idx_cols, sort=False).groups.items():
            positions = {out.at[i, "measure_short"]: i for i in indices}
            if "YLD" in positions and "YLL" in positions and "DALY" in positions:
                for value_col in ["projected_value", "projected_lower", "projected_upper"]:
                    out.at[positions["DALY"], value_col] = out.at[positions["YLD"], value_col] + out.at[positions["YLL"], value_col]
                out.at[positions["DALY"], "identity_rule"] = "DALY=YLL+YLD enforced"
            elif keys[0] == "depression" and "YLD" in positions and "DALY" in positions:
                for value_col in ["projected_value", "projected_lower", "projected_upper"]:
                    out.at[positions["DALY"], value_col] = out.at[positions["YLD"], value_col]
                out.at[positions["DALY"], "identity_rule"] = "Depression DALY=YLD enforced"
    return out, slopes


def s0_rate_schedule(scenario: str) -> dict[int, float]:
    rates = {}
    for year in YEARS:
        if year <= 2034:
            rate = 0.0084
        elif scenario == "main_damped":
            rate = 0.0084 * max(0.0, (2040 - year) / 6.0)
        elif scenario == "stable_after_2034":
            rate = 0.0
        elif scenario == "constrained_continuation":
            rate = 0.0084
        else:
            raise ValueError(scenario)
        rates[year] = rate
    return rates


def load_effect_retention(inputs: dict[str, pd.DataFrame], maintenance: str) -> dict[tuple[str, int], float]:
    if maintenance == "FULL_MAINTENANCE":
        return {(sid, year): 1.0 for sid in SCENARIOS for year in YEARS if year >= 2035}
    d = inputs["cost_d9"]
    d = d.loc[
        d["maintenance_scenario"].eq(maintenance)
        & d["cost_structure_scenario"].eq("STRUCTURAL_ANCHOR")
        & d["perspective"].eq("payer"),
        ["scenario_id", "year", "effect_retention_relative_to_2034"],
    ].copy()
    return {(str(r.scenario_id), int(r.year)): float(r.effect_retention_relative_to_2034) if pd.notna(r.effect_retention_relative_to_2034) else 1.0 for r in d.itertuples(index=False)}


def build_pa_trajectories(inputs: dict[str, pd.DataFrame], case: AnalysisCase) -> pd.DataFrame:
    pa = inputs["pa"].copy()
    policy = inputs["policy"].copy().set_index("scenario_id")
    rates = s0_rate_schedule(case.d2_s0)
    retention = load_effect_retention(inputs, case.d9_maintenance)
    rows = []
    for p in pa.itertuples(index=False):
        low = float(p.low_prev)
        nonlow = max(float(p.moderate_prev + p.high_prev), 1e-15)
        mod_ratio = float(p.moderate_prev) / nonlow
        high_ratio = float(p.high_prev) / nonlow
        for year in YEARS:
            if year > BASE_YEAR:
                low = min(0.999, low * (1.0 + rates[year]))
            active = 1.0 - low
            mod_s0, high_s0 = active * mod_ratio, active * high_ratio
            for sid in SCENARIOS:
                pol = policy.loc[sid]
                if sid == "S0":
                    uptake = 0.0
                    realised = 0.0
                elif year <= 2034:
                    uptake = float(np.clip((year - BASE_YEAR + 0.5) / max(float(pol.ramp_years), 1.0), 0.0, 1.0))
                    realised = float(pol.theta_mean) * float(pol.coverage_mean) * uptake
                else:
                    uptake_2034 = float(np.clip((2034 - BASE_YEAR + 0.5) / max(float(pol.ramp_years), 1.0), 0.0, 1.0))
                    realised = float(pol.theta_mean) * float(pol.coverage_mean) * uptake_2034 * retention.get((sid, year), 1.0)
                    uptake = uptake_2034 * retention.get((sid, year), 1.0)
                movers = low * realised
                low_policy = low - movers
                mod_policy = mod_s0 + movers * 0.8
                high_policy = high_s0 + movers * 0.2
                rows.append({
                    "year": year, "sex": p.sex, "age_group": p.age_group, "scenario_id": sid,
                    "low_s0": low, "moderate_s0": mod_s0, "high_s0": high_s0,
                    "low_policy": low_policy, "moderate_policy": mod_policy, "high_policy": high_policy,
                    "s0_annual_relative_change": rates[year], "policy_uptake_or_retention": uptake,
                    "realised_relative_reduction_in_low_pa": realised, "d2_scenario": case.d2_s0,
                    "d9_maintenance_scenario": case.d9_maintenance,
                })
    out = pd.DataFrame(rows)
    prob_sum = out[["low_policy", "moderate_policy", "high_policy"]].sum(axis=1)
    if not np.allclose(prob_sum, 1.0, atol=1e-10) or (out[["low_policy", "moderate_policy", "high_policy"]] < -1e-12).any().any():
        raise ValueError("PA trajectory probabilities are invalid")
    return out


def build_rr_bridge(inputs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    parent = inputs["rr"].copy()
    parent["rr_inactive_vs_active"] = pd.to_numeric(parent["rr_inactive_vs_active"], errors="raise")
    rr_by_outcome = parent.set_index("outcome_id")["rr_inactive_vs_active"].to_dict()
    sex_use = parent.set_index("outcome_id")["sex_use"].to_dict()
    cvd = inputs["rr_cvd"].set_index("disease_id")
    component_rows = []
    for outcome in OUTCOME_NAMES_CN:
        if outcome == "hypertension":
            components = ["hypertension"]
        elif outcome == "stroke":
            components = ["ischemic_stroke", "intracerebral_hemorrhage", "subarachnoid_hemorrhage"]
        else:
            components = [outcome]
        for component in components:
            if component == "coronary_heart_disease":
                rr_low, rr_mod, source = float(cvd.loc["IHD", "rr_low"]), float(cvd.loc["IHD", "rr_moderate"]), "CVD v16 three-level RR"
            elif component == "ischemic_stroke":
                rr_low, rr_mod, source = float(cvd.loc["IS", "rr_low"]), float(cvd.loc["IS", "rr_moderate"]), "CVD v16 three-level RR"
            else:
                rr_low, rr_mod, source = float(rr_by_outcome[outcome]), 1.0, "Parent binary RR bridged as moderate=high=1"
            component_rows.append({
                "outcome_id": outcome, "component_id": component, "rr_low": rr_low, "rr_moderate": rr_mod,
                "rr_high": 1.0, "sex_use": sex_use.get(outcome, "Both"), "rr_bridge_source": source,
            })
    return pd.DataFrame(component_rows)


def lag_multiplier(outcome_id: str, year: int, lag_table: pd.DataFrame, mode: str) -> float:
    if mode == "immediate":
        return 1.0
    if outcome_id in {"hypertension", "depression"}:
        group = "fast"
    elif outcome_id in {"coronary_heart_disease", "stroke", "type2_diabetes"}:
        group = "medium"
    elif outcome_id in {"bladder_cancer", "breast_cancer", "colon_cancer", "endometrial_cancer", "oesophageal_cancer", "gastric_cancer", "renal_cancer"}:
        group = "cancer"
    elif outcome_id == "dementia":
        group = "dementia"
    else:
        raise KeyError(outcome_id)
    row = lag_table.loc[(lag_table["lag_group"].eq(group)) & lag_table["analysis_role"].eq("main_structural")].iloc[0]
    delay, full = float(row.start_delay_years), float(row.time_to_full)
    if mode == "delayed_plus2":
        delay += 2.0
        full += 2.0
    elapsed = year - BASE_YEAR + 1
    if elapsed <= delay:
        return 0.0
    if full <= delay:
        return 1.0
    return float(np.clip((elapsed - delay) / (full - delay), 0.0, 1.0))


def calculate_health(projected: pd.DataFrame, pa: pd.DataFrame, rr: pd.DataFrame, lag: pd.DataFrame, lag_mode: str) -> pd.DataFrame:
    merged = projected.merge(rr, on=["outcome_id", "component_id"], how="inner", validate="many_to_one")
    merged = merged.loc[merged["sex_use"].eq("Both") | merged["sex"].eq(merged["sex_use"])].copy()
    merged = merged.merge(pa, on=["year", "sex", "age_group"], how="inner", validate="many_to_many")
    risk_s0 = merged["low_s0"] * merged["rr_low"] + merged["moderate_s0"] * merged["rr_moderate"] + merged["high_s0"] * merged["rr_high"]
    risk_policy = merged["low_policy"] * merged["rr_low"] + merged["moderate_policy"] * merged["rr_moderate"] + merged["high_policy"] * merged["rr_high"]
    merged["pif_raw"] = np.divide(risk_s0 - risk_policy, risk_s0, out=np.zeros(len(merged)), where=risk_s0.to_numpy(float) > 0)
    lag_lookup = {
        (outcome, year): lag_multiplier(outcome, year, lag, lag_mode)
        for outcome in merged["outcome_id"].astype(str).unique()
        for year in YEARS
    }
    merged["disease_lag_multiplier"] = [
        lag_lookup[(str(outcome), int(year))]
        for outcome, year in zip(merged["outcome_id"], merged["year"])
    ]
    merged["pif_effective"] = merged["pif_raw"] * merged["disease_lag_multiplier"]
    merged["avoided_value"] = merged["projected_value"] * merged["pif_effective"]
    merged["d1_lag_mode"] = lag_mode
    return merged


def calculate_hypertension(inputs: dict[str, pd.DataFrame], population: pd.DataFrame, pa: pd.DataFrame, rr_bridge: pd.DataFrame, lag_mode: str) -> pd.DataFrame:
    htn = inputs["htn"][["sex", "age_group", "hypertension_prevalence_2025"]].copy()
    htn["hypertension_prevalence_2025"] = pd.to_numeric(htn["hypertension_prevalence_2025"], errors="raise")
    base = population[["year", "sex", "age_group", "population_model"]].merge(htn, on=["sex", "age_group"], validate="many_to_one")
    base["projected_value"] = base["population_model"] * base["hypertension_prevalence_2025"]
    base["outcome_id"] = "hypertension"
    base["component_id"] = "hypertension"
    base["measure_short"] = "Hypertension patient-years"
    base["measure_name"] = "Hypertension patient-years"
    base["value_domain"] = "hypertension"
    rr = rr_bridge.loc[rr_bridge["outcome_id"].eq("hypertension")]
    return calculate_health(base, pa, rr, inputs["lag"], lag_mode)


def select_policy_cost(inputs: dict[str, pd.DataFrame], maintenance: str, perspective: str) -> pd.DataFrame:
    parent = inputs["cost_main"].loc[
        inputs["cost_main"]["cost_structure_scenario"].eq("STRUCTURAL_ANCHOR")
        & inputs["cost_main"]["perspective"].eq(perspective)
        & inputs["cost_main"]["year"].between(2025, 2034)
    ].copy()
    if maintenance == "FULL_MAINTENANCE":
        future = inputs["cost_main"].loc[
            inputs["cost_main"]["cost_structure_scenario"].eq("STRUCTURAL_ANCHOR")
            & inputs["cost_main"]["perspective"].eq(perspective)
            & inputs["cost_main"]["year"].between(2035, 2050)
        ].copy()
    else:
        future = inputs["cost_d9"].loc[
            inputs["cost_d9"]["maintenance_scenario"].eq(maintenance)
            & inputs["cost_d9"]["cost_structure_scenario"].eq("STRUCTURAL_ANCHOR")
            & inputs["cost_d9"]["perspective"].eq(perspective)
        ].copy()
    out = pd.concat([parent, future], ignore_index=True)
    out["year"] = pd.to_numeric(out["year"], errors="raise").astype(int)
    out["annual_programme_cost_2025_cny"] = pd.to_numeric(out["annual_programme_cost_2025_cny"], errors="coerce")
    expected = len(YEARS) * len(SCENARIOS)
    if len(out) != expected or out.duplicated(["year", "scenario_id"]).any():
        raise ValueError(f"Policy cost schedule incomplete for {maintenance}/{perspective}: {len(out)}")
    return out.sort_values(["year", "scenario_id"]).reset_index(drop=True)


def annual_summary(health: pd.DataFrame) -> pd.DataFrame:
    grouped = health.groupby(["scenario_id", "year", "measure_short"], as_index=False)["avoided_value"].sum()
    out = grouped.pivot_table(index=["scenario_id", "year"], columns="measure_short", values="avoided_value", fill_value=0.0).reset_index()
    out.columns.name = None
    for col in ["DALY", "Deaths", "YLL", "YLD"]:
        if col not in out:
            out[col] = 0.0
    return out


def summarize_horizons(annual_burden: pd.DataFrame, annual_cases: pd.DataFrame, htn: pd.DataFrame, costs: pd.DataFrame, scenario_names: dict[str, str]) -> pd.DataFrame:
    cases = annual_cases.groupby(["scenario_id", "year", "measure_short"], as_index=False)["avoided_value"].sum().pivot_table(
        index=["scenario_id", "year"], columns="measure_short", values="avoided_value", fill_value=0.0
    ).reset_index()
    cases.columns.name = None
    htn_annual = htn.groupby(["scenario_id", "year"], as_index=False)["avoided_value"].sum().rename(columns={"avoided_value": "Hypertension patient-years"})
    annual = annual_burden.merge(cases, on=["scenario_id", "year"], how="left").merge(htn_annual, on=["scenario_id", "year"], how="left")
    annual = annual.merge(costs[["scenario_id", "year", "annual_programme_cost_2025_cny"]], on=["scenario_id", "year"], how="left")
    annual["discount_factor_health"] = 1.0 / (1.0 + HEALTH_DISCOUNT_RATE) ** (annual["year"] - BASE_YEAR)
    annual["discount_factor_cost"] = 1.0 / (1.0 + COST_DISCOUNT_RATE) ** (annual["year"] - BASE_YEAR)
    annual["discounted_daly"] = annual["DALY"] * annual["discount_factor_health"]
    annual["discounted_deaths"] = annual["Deaths"] * annual["discount_factor_health"]
    annual["discounted_programme_cost"] = annual["annual_programme_cost_2025_cny"] * annual["discount_factor_cost"]
    rows = []
    for horizon in HORIZONS:
        end = BASE_YEAR + horizon - 1
        d = annual.loc[annual["year"].between(BASE_YEAR, end)]
        for sid in SCENARIOS:
            g = d.loc[d["scenario_id"].eq(sid)]
            cost = float(g["discounted_programme_cost"].sum(min_count=1))
            daly = float(g["discounted_daly"].sum())
            rows.append({
                "horizon_years": horizon, "end_year": end, "scenario_id": sid,
                "scenario_name_cn": scenario_names[sid],
                "cumulative_avoided_daly_undiscounted": float(g["DALY"].sum()),
                "discounted_dalys_averted": daly,
                "cumulative_avoided_deaths_undiscounted": float(g["Deaths"].sum()),
                "discounted_deaths_averted": float(g["discounted_deaths"].sum()),
                "cumulative_avoided_incidence": float(g.get("Incidence", pd.Series(dtype=float)).sum()),
                "cumulative_avoided_prevalence_patient_years": float(g.get("Prevalence", pd.Series(dtype=float)).sum()),
                "cumulative_avoided_hypertension_patient_years": float(g["Hypertension patient-years"].sum()),
                "discounted_programme_cost_2025_cny": cost,
                "icer_vs_s0_programme_only_cny_per_daly": cost / daly if np.isfinite(cost) and daly > 0 else np.nan,
                "nmb_wtp_50000_programme_only": daly * 50000 - cost if np.isfinite(cost) else np.nan,
                "nmb_wtp_150000_programme_only": daly * 150000 - cost if np.isfinite(cost) else np.nan,
                "frontier_eligible": sid in FRONTIER_SCENARIOS,
                "decision_view": "INTERIM_BRIDGE_PROGRAMME_COST_ONLY",
            })
    return pd.DataFrame(rows), annual


def cost_effectiveness_frontier(summary: pd.DataFrame, horizon: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    data = summary.loc[
        summary["horizon_years"].eq(horizon) & summary["frontier_eligible"].eq(True)
        & summary["discounted_programme_cost_2025_cny"].notna()
    ].sort_values(["discounted_dalys_averted", "discounted_programme_cost_2025_cny"]).reset_index(drop=True)
    dominated_rows, keep = [], []
    best_cost = np.inf
    for idx in range(len(data) - 1, -1, -1):
        row = data.iloc[idx]
        if float(row["discounted_programme_cost_2025_cny"]) >= best_cost - 1e-9:
            x = row.to_dict(); x["dominance_type"] = "strong"; dominated_rows.append(x)
        else:
            keep.append(row.to_dict()); best_cost = float(row["discounted_programme_cost_2025_cny"])
    frontier = pd.DataFrame(list(reversed(keep)))
    changed = True
    while changed and len(frontier) >= 3:
        changed = False
        effects = frontier["discounted_dalys_averted"].to_numpy(float)
        costs = frontier["discounted_programme_cost_2025_cny"].to_numpy(float)
        icers = np.diff(costs) / np.diff(effects)
        for i in range(1, len(icers)):
            if icers[i] <= icers[i - 1] + 1e-12:
                removed = frontier.iloc[i].to_dict(); removed["dominance_type"] = "extended"; dominated_rows.append(removed)
                frontier = frontier.drop(frontier.index[i]).reset_index(drop=True); changed = True; break
    if not frontier.empty:
        frontier["incremental_cost"] = frontier["discounted_programme_cost_2025_cny"].diff()
        frontier["incremental_dalys"] = frontier["discounted_dalys_averted"].diff()
        frontier["incremental_icer"] = frontier["incremental_cost"] / frontier["incremental_dalys"]
        frontier["horizon_years"] = horizon
    dominated = pd.DataFrame(dominated_rows)
    if not dominated.empty:
        dominated["horizon_years"] = horizon
    return frontier, dominated


def build_d4_cost_table(inputs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    candidates = inputs["cost_candidates"].set_index("outcome_id")
    selected_ids = {
        "bladder_cancer": "DC-BLADDER-2020", "breast_cancer": "DC-BREAST-2020",
        "colon_cancer": "DC-COLON-2020", "endometrial_cancer": "DC-ENDOMETRIAL-2020",
        "oesophageal_cancer": "DC-OESOPH-2020", "gastric_cancer": "DC-GASTRIC-2020",
        "renal_cancer": "DC-RENAL-2020",
    }
    rows = []
    for outcome in OUTCOME_NAMES_CN:
        if outcome == "hypertension":
            rows.append({"outcome_id": outcome, "d4_status": "MISSING_INCIDENCE_AND_STRICT_FIRST_YEAR_CONNECTION", "cost_2025_cny": np.nan, "cost_id": ""})
        elif outcome in {"type2_diabetes", "depression", "dementia"}:
            rows.append({"outcome_id": outcome, "d4_status": "MISSING_STRICT_FIRST_YEAR_COST", "cost_2025_cny": np.nan, "cost_id": ""})
        elif outcome == "coronary_heart_disease":
            value = 205.47 * 6.8974 * 1.03330083672
            rows.append({"outcome_id": outcome, "d4_status": "PROXY_STRICT_FIRST_YEAR_AVAILABLE", "cost_2025_cny": value, "cost_id": "COST002_SANTOS_2020_CONVERTED"})
        elif outcome == "stroke":
            value = 791.19 * 6.8974 * 1.03330083672
            rows.append({"outcome_id": outcome, "d4_status": "PROXY_STRICT_FIRST_YEAR_AVAILABLE", "cost_2025_cny": value, "cost_id": "COST005_SANTOS_2020_CONVERTED"})
        else:
            cid = selected_ids[outcome]
            row = inputs["cost_candidates"].loc[inputs["cost_candidates"]["cost_id"].eq(cid)].iloc[0]
            rows.append({"outcome_id": outcome, "d4_status": "PROXY_STRICT_FIRST_YEAR_AVAILABLE", "cost_2025_cny": float(row.cost_2025_cny), "cost_id": cid})
    out = pd.DataFrame(rows)
    out["cost_boundary"] = "incident case first-year direct medical cost"
    out["public_payer_share"] = np.nan
    out["public_payer_net_CEA_ready"] = "NO"
    return out


def calculate_partial_medical_savings(case_health: pd.DataFrame, d4_costs: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    inc = case_health.loc[case_health["measure_short"].eq("Incidence")].copy()
    inc = inc.groupby(["year", "scenario_id", "outcome_id"], as_index=False)["avoided_value"].sum()
    inc = inc.merge(d4_costs, on="outcome_id", how="left", validate="many_to_one")
    inc["partial_direct_medical_savings_2025_cny"] = inc["avoided_value"] * inc["cost_2025_cny"]
    coverage = inc.groupby(["scenario_id", "year"], as_index=False).agg(
        total_avoided_incidence=("avoided_value", "sum"),
        covered_avoided_incidence=("avoided_value", lambda x: float(x[inc.loc[x.index, "cost_2025_cny"].notna()].sum())),
        partial_direct_medical_savings_2025_cny=("partial_direct_medical_savings_2025_cny", "sum"),
    )
    coverage["avoided_incidence_coverage_share"] = coverage["covered_avoided_incidence"] / coverage["total_avoided_incidence"].replace(0, np.nan)
    coverage["result_status"] = "INCOMPLETE_D4_TOTAL_DIRECT_MEDICAL_SAVINGS_NOT_HEADLINE"
    return inc, coverage


def calculate_dementia_long_term_care(case_health: pd.DataFrame, inputs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    prevalence = case_health.loc[(case_health["outcome_id"].eq("dementia")) & case_health["measure_short"].eq("Prevalence")].copy()
    prevalence = prevalence.groupby(["year", "scenario_id"], as_index=False)["avoided_value"].sum()
    candidates = inputs["cost_candidates"].set_index("cost_id")
    total = float(candidates.loc["DC-DEM-CN-SOCIAL-2015", "cost_2025_cny"])
    direct = float(candidates.loc["DC-DEM-CN-2015", "cost_2025_cny"])
    care = total - direct
    prevalence["dementia_nonmedical_and_informal_care_cost_2025_cny_per_patient_year"] = care
    prevalence["dementia_long_term_care_savings_2025_cny"] = prevalence["avoided_value"] * care
    prevalence["d10_status"] = "PROVISIONAL_D10B_SOCIAL_COST_SATELLITE"
    return prevalence


def summarize_structural_case(case: AnalysisCase, summary: pd.DataFrame) -> pd.DataFrame:
    focus = summary.loc[summary["scenario_id"].eq("S6")].copy()
    focus.insert(0, "case_id", case.case_id)
    focus.insert(1, "changed_decision", case.changed_decision)
    focus["d1_lag"] = case.d1_lag
    focus["d2_s0"] = case.d2_s0
    focus["d3_disease"] = case.d3_disease
    focus["d9_maintenance"] = case.d9_maintenance
    return focus


def compare_cvd_bridge(inputs: dict[str, pd.DataFrame], population: pd.DataFrame, burden_projection: pd.DataFrame, pa_traj: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    cvd = inputs["cvd_annual"].copy()
    cvd["component_id"] = cvd["disease_id"].map({"IHD": "coronary_heart_disease", "IS": "ischemic_stroke"})
    measure_map = {"deaths": "Deaths", "yll": "YLL", "yld": "YLD", "daly": "DALY"}
    left = burden_projection.loc[
        burden_projection["component_id"].isin(["coronary_heart_disease", "ischemic_stroke"])
        & burden_projection["year"].between(2025, 2034),
        ["year", "component_id", "sex", "age_group", "measure_short", "projected_value"],
    ].copy()
    right = cvd.melt(
        id_vars=["year", "component_id", "sex", "age_group"], value_vars=list(measure_map),
        var_name="metric", value_name="cvd_v16_value",
    )
    right["measure_short"] = right["metric"].map(measure_map)
    comp = left.merge(right.drop(columns="metric"), on=["year", "component_id", "sex", "age_group", "measure_short"], how="outer", validate="one_to_one")
    comp["absolute_difference"] = comp["projected_value"] - comp["cvd_v16_value"]
    comp["relative_difference"] = comp["absolute_difference"] / comp["cvd_v16_value"].abs().clip(lower=1e-12)

    pa_cvd = inputs["pa_cvd"][["sex", "age_group", "low_prev", "moderate_prev", "high_prev"]].copy()
    pa_parent = inputs["pa"][["sex", "age_group", "low_prev", "moderate_prev", "high_prev"]].copy()
    pa_comp = pa_parent.merge(pa_cvd, on=["sex", "age_group"], suffixes=("_parent", "_cvd"), validate="one_to_one")
    for level in ["low", "moderate", "high"]:
        pa_comp[f"{level}_difference"] = pa_comp[f"{level}_prev_parent"] - pa_comp[f"{level}_prev_cvd"]
    return comp, pa_comp


def run_analysis() -> dict[str, pd.DataFrame]:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "data").mkdir(exist_ok=True)
    (OUTPUT / "results").mkdir(exist_ok=True)
    inputs = load_inputs()
    population = build_population(inputs)
    rr_bridge = build_rr_bridge(inputs)
    d4_costs = build_d4_cost_table(inputs)
    scenario_names = inputs["policy"].set_index("scenario_id")["scenario_name_cn"].astype(str).to_dict()

    projection_cache: dict[tuple[str, str], tuple[pd.DataFrame, pd.DataFrame]] = {}
    structural_rows = []
    primary_tables: dict[str, pd.DataFrame] = {}
    for case in CASES:
        print(f"Running {case.case_id}", flush=True)
        key_b = ("burden", case.d3_disease)
        key_c = ("cases", case.d3_disease)
        if key_b not in projection_cache:
            projection_cache[key_b] = project_gbd(inputs["gbd_burden"], "burden", population, inputs["wpp_history"], case.d3_disease)
        if key_c not in projection_cache:
            projection_cache[key_c] = project_gbd(inputs["gbd_cases"], "cases", population, inputs["wpp_history"], case.d3_disease)
        burden_proj, burden_slopes = projection_cache[key_b]
        cases_proj, case_slopes = projection_cache[key_c]
        pa_traj = build_pa_trajectories(inputs, case)
        burden_health = calculate_health(burden_proj, pa_traj, rr_bridge, inputs["lag"], case.d1_lag)
        case_health = calculate_health(cases_proj, pa_traj, rr_bridge, inputs["lag"], case.d1_lag)
        htn_health = calculate_hypertension(inputs, population, pa_traj, rr_bridge, case.d1_lag)
        costs = select_policy_cost(inputs, case.d9_maintenance, "payer")
        a_burden = annual_summary(burden_health)
        summary, annual = summarize_horizons(a_burden, case_health, htn_health, costs, scenario_names)
        structural_rows.append(summarize_structural_case(case, summary))
        if case.case_id == "PRIMARY":
            partial_savings, partial_coverage = calculate_partial_medical_savings(case_health, d4_costs)
            dementia_care = calculate_dementia_long_term_care(case_health, inputs)
            recent_key = ("burden", "recent_2018_2023_damped")
            if recent_key not in projection_cache:
                projection_cache[recent_key] = project_gbd(
                    inputs["gbd_burden"],
                    "burden",
                    population,
                    inputs["wpp_history"],
                    "recent_2018_2023_damped",
                )
            recent_burden_proj = projection_cache[recent_key][0]
            cvd_comp, pa_comp = compare_cvd_bridge(inputs, population, recent_burden_proj, pa_traj)
            cvd_comp["crosscheck_projection_scenario"] = "recent_2018_2023_damped"
            frontiers, dominated = [], []
            for horizon in HORIZONS:
                f, d = cost_effectiveness_frontier(summary, horizon)
                frontiers.append(f); dominated.append(d)
            daly_detail = burden_health.loc[burden_health["measure_short"].eq("DALY")].copy()
            daly_detail["discounted_avoided_daly"] = daly_detail["avoided_value"] / (1 + HEALTH_DISCOUNT_RATE) ** (daly_detail["year"] - BASE_YEAR)
            contribution_disease = daly_detail.loc[daly_detail["scenario_id"].eq("S6")].groupby(["outcome_id"], as_index=False)[["avoided_value", "discounted_avoided_daly"]].sum().sort_values("discounted_avoided_daly", ascending=False)
            contribution_disease["outcome_name_cn"] = contribution_disease["outcome_id"].map(OUTCOME_NAMES_CN)
            contribution_disease["contribution_share"] = contribution_disease["discounted_avoided_daly"] / contribution_disease["discounted_avoided_daly"].sum()
            contribution_age = daly_detail.loc[daly_detail["scenario_id"].eq("S6")].groupby(["age_group"], as_index=False)[["avoided_value", "discounted_avoided_daly"]].sum()
            contribution_age["contribution_share"] = contribution_age["discounted_avoided_daly"] / contribution_age["discounted_avoided_daly"].sum()
            contribution_sex = daly_detail.loc[daly_detail["scenario_id"].eq("S6")].groupby(["sex"], as_index=False)[["avoided_value", "discounted_avoided_daly"]].sum()
            contribution_sex["contribution_share"] = contribution_sex["discounted_avoided_daly"] / contribution_sex["discounted_avoided_daly"].sum()
            primary_tables = {
                "population": population, "pa_baseline": inputs["pa"], "pa_trajectory": pa_traj,
                "rr_bridge": rr_bridge, "burden_projection": burden_proj, "case_projection": cases_proj,
                "burden_slopes": burden_slopes, "case_slopes": case_slopes,
                "burden_health_detail": burden_health, "case_health_detail": case_health,
                "hypertension_health_detail": htn_health, "annual_results": annual, "horizon_summary": summary,
                "frontiers": pd.concat(frontiers, ignore_index=True),
                "dominated": pd.concat([d for d in dominated if not d.empty], ignore_index=True) if any(not d.empty for d in dominated) else pd.DataFrame(),
                "d4_cost_interface": d4_costs, "partial_medical_savings_detail": partial_savings,
                "partial_medical_savings_coverage": partial_coverage, "dementia_long_term_care": dementia_care,
                "contribution_disease": contribution_disease, "contribution_age": contribution_age,
                "contribution_sex": contribution_sex, "cvd_projection_crosscheck": cvd_comp,
                "pa_crosscheck": pa_comp, "policy_cost_payer": costs,
                "policy_cost_societal": select_policy_cost(inputs, case.d9_maintenance, "societal"),
            }

    structural = pd.concat(structural_rows, ignore_index=True)
    primary_tables["structural_sensitivity_s6"] = structural
    primary_tables["method_decisions"] = pd.DataFrame([
        ["D1", "A", "疾病组特异性累积滞后", "IMPLEMENTED", "主分析按fast/medium/cancer/dementia分组；即时和+2年敏感性已运行"],
        ["D2", "A", "S0 0.84%至2034；2035—2040衰减至0", "IMPLEMENTED", "2034后稳定和持续趋势敏感性已运行"],
        ["D3", "A", "2010—2023年龄—性别疾病率趋势，并于2035—2040衰减", "IMPLEMENTED_GBD_FINAL_HISTORY", "主分析使用2010—2023；2018—2023近期窗口、2023固定率和趋势持续作为结构敏感性"],
        ["D4", "A", "新发病例/首次事件×首年直接医疗费用", "PARTIAL", "IHD、卒中和7癌可算；T2D、抑郁、痴呆及高血压严格接口仍缺"],
        ["D5", "A", "公共支付方主视角；总直接费用扩展", "FRAMEWORK_READY_NOT_HEADLINE", "公共支付比例缺失，暂报政策实施成本桥接CEA"],
        ["D6", "A", "劳动生产率卫星模块；RAND外部对标", "INTERFACE_READY_NO_ESTIMATE", "父数据库不含劳动参数"],
        ["D7", "A", "有效劳动×产出弹性；工资法敏感性", "INTERFACE_READY_NO_ESTIMATE", "父数据库不含年龄性别就业和生产率参数"],
        ["D8", "A", "20—69岁，65—69按实际就业率", "INTERFACE_READY_NO_ESTIMATE", "年龄边界已锁定，数值待劳动输入"],
        ["D9", "A", "政策特异性维护—持续—衰减", "IMPLEMENTED_INTERIM_COST", "full/reduced75%/stop已运行；2035后资本更新仍为INTERIM"],
        ["D10", "B", "高血压直接诊疗；痴呆长期照护入社会成本", "IMPLEMENTED_PROVISIONAL", "高血压避免患者年已算；痴呆长期照护为社会成本卫星结果"],
    ], columns=["decision_id", "choice", "locked_rule", "implementation_status", "notes"])
    primary_tables["productivity_interface"] = pd.DataFrame([
        ["labour_force_participation", "sex-age-year", "20-69", "MISSING", "D7/D8"],
        ["employment_rate", "sex-age-year", "20-69; 65-69 actual", "MISSING", "D7/D8"],
        ["output_per_effective_worker", "year", "2025 CNY", "MISSING", "D7"],
        ["labour_output_elasticity", "scalar/scenario", "unitless", "MISSING", "D7"],
        ["disease_productivity_loss", "outcome-age-sex", "absence/presenteeism/exit/caregiver", "MISSING", "D6/D7"],
        ["wage_input", "sex-age-year", "2025 CNY", "MISSING_SENSITIVITY_ONLY", "D7"],
    ], columns=["input_id", "required_granularity", "unit_or_boundary", "status", "decision_link"])
    return primary_tables


def build_qc(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    checks = []
    def add(check_id: str, passed: bool, observed: object, expected: object, severity: str = "ERROR"):
        checks.append({"check_id": check_id, "passed": bool(passed), "observed": observed, "expected": expected, "severity": severity})
    add("PARENT_DB_EXISTS", PARENT_DB.exists(), str(PARENT_DB), "exists")
    add("POPULATION_ROWS", len(tables["population"]) == 572, len(tables["population"]), 572)
    add("PA_STRATA", len(tables["pa_baseline"]) == 22, len(tables["pa_baseline"]), 22)
    add("PA_BASE_SUM", np.allclose(tables["pa_baseline"]["probability_sum"], 1.0, atol=1e-10), float((tables["pa_baseline"]["probability_sum"] - 1).abs().max()), "<=1e-10")
    pa_cols = tables["pa_trajectory"][["low_policy", "moderate_policy", "high_policy"]]
    add("PA_TRAJECTORY_SUM", np.allclose(pa_cols.sum(axis=1), 1.0, atol=1e-10), float((pa_cols.sum(axis=1) - 1).abs().max()), "<=1e-10")
    add("RR_COMPONENTS", len(tables["rr_bridge"]) == 15, len(tables["rr_bridge"]), 15)
    add("GBD_HISTORY_START", int(tables["burden_slopes"]["history_start_year"].min()) == 2010, int(tables["burden_slopes"]["history_start_year"].min()), 2010)
    add("GBD_HISTORY_END", int(tables["burden_slopes"]["history_end_year"].max()) == 2023, int(tables["burden_slopes"]["history_end_year"].max()), 2023)
    add("GBD_HISTORY_YEARS", int(tables["burden_slopes"]["raw_history_years"].min()) == 14, int(tables["burden_slopes"]["raw_history_years"].min()), 14)
    add("BURDEN_OUTCOMES", tables["burden_projection"]["outcome_id"].nunique() == 12, tables["burden_projection"]["outcome_id"].nunique(), 12)
    add("STROKE_COMPONENTS", tables["burden_projection"].loc[tables["burden_projection"]["outcome_id"].eq("stroke"), "component_id"].nunique() == 3, tables["burden_projection"].loc[tables["burden_projection"]["outcome_id"].eq("stroke"), "component_id"].nunique(), 3)
    daly = tables["burden_projection"].pivot_table(index=["outcome_id", "component_id", "sex", "age_group", "year"], columns="measure_short", values="projected_value", aggfunc="sum")
    mask = daly[[c for c in ["DALY", "YLL", "YLD"] if c in daly]].notna().all(axis=1)
    identity_error = float((daly.loc[mask, "DALY"] - daly.loc[mask, "YLL"] - daly.loc[mask, "YLD"]).abs().max())
    add("DALY_IDENTITY", identity_error < 1e-6, identity_error, "<1e-6")
    add("COST_SCHEDULE_ROWS", len(tables["policy_cost_payer"]) == 208, len(tables["policy_cost_payer"]), 208)
    add("S7_COST_MISSING", tables["policy_cost_payer"].loc[tables["policy_cost_payer"]["scenario_id"].eq("S7"), "annual_programme_cost_2025_cny"].isna().all(), int(tables["policy_cost_payer"].loc[tables["policy_cost_payer"]["scenario_id"].eq("S7"), "annual_programme_cost_2025_cny"].notna().sum()), 0)
    cvd_max = float(tables["cvd_projection_crosscheck"]["relative_difference"].abs().max())
    add("CVD_V16_PROJECTION_CROSSCHECK", cvd_max < 1e-6, cvd_max, "<1e-6")
    pa_max = float(tables["pa_crosscheck"][["low_difference", "moderate_difference", "high_difference"]].abs().max().max())
    add("CVD_V16_PA_CROSSCHECK", pa_max < 1e-12, pa_max, "<1e-12")
    add("STRUCTURAL_CASES", tables["structural_sensitivity_s6"]["case_id"].nunique() == len(CASES), tables["structural_sensitivity_s6"]["case_id"].nunique(), len(CASES))
    return pd.DataFrame(checks)


def save_tables(tables: dict[str, pd.DataFrame], qc: pd.DataFrame) -> None:
    compact = {
        "00_QC.csv": qc,
        "01_population_2025_2050.csv": tables["population"],
        "02_PA_baseline_from_parent.csv": tables["pa_baseline"],
        "03_RR_three_level_bridge.csv": tables["rr_bridge"],
        "04_D1_D10_method_status.csv": tables["method_decisions"],
        "05_primary_horizon_summary.csv": tables["horizon_summary"],
        "06_primary_annual_results.csv": tables["annual_results"],
        "07_primary_frontiers.csv": tables["frontiers"],
        "08_primary_dominated.csv": tables["dominated"],
        "09_S6_structural_sensitivity.csv": tables["structural_sensitivity_s6"],
        "10_S6_disease_DALY_contribution_2025_2050.csv": tables["contribution_disease"],
        "11_S6_age_DALY_contribution_2025_2050.csv": tables["contribution_age"],
        "12_S6_sex_DALY_contribution_2025_2050.csv": tables["contribution_sex"],
        "13_D4_cost_interface.csv": tables["d4_cost_interface"],
        "14_D4_partial_medical_savings_coverage.csv": tables["partial_medical_savings_coverage"],
        "15_D10_dementia_long_term_care.csv": tables["dementia_long_term_care"],
        "16_D6_D8_productivity_interface.csv": tables["productivity_interface"],
        "17_CVDv16_projection_crosscheck.csv": tables["cvd_projection_crosscheck"],
        "18_CVDv16_PA_crosscheck.csv": tables["pa_crosscheck"],
        "19_policy_cost_payer_2025_2050.csv": tables["policy_cost_payer"],
        "20_policy_cost_societal_2025_2050.csv": tables["policy_cost_societal"],
        "21_GBD_rate_slope_audit_burden.csv": tables["burden_slopes"],
        "22_GBD_rate_slope_audit_cases.csv": tables["case_slopes"],
    }
    for name, df in compact.items():
        df.to_csv(OUTPUT / "results" / name, index=False, encoding="utf-8-sig")
    detail = {
        "GBD_burden_projection_2025_2050.csv.gz": tables["burden_projection"],
        "GBD_cases_projection_2025_2050.csv.gz": tables["case_projection"],
        "PA_trajectory_primary.csv.gz": tables["pa_trajectory"],
        "health_burden_detail_primary.csv.gz": tables["burden_health_detail"],
        "health_cases_detail_primary.csv.gz": tables["case_health_detail"],
        "hypertension_detail_primary.csv.gz": tables["hypertension_health_detail"],
        "D4_partial_medical_savings_detail.csv.gz": tables["partial_medical_savings_detail"],
    }
    for name, df in detail.items():
        df.to_csv(OUTPUT / "data" / name, index=False, encoding="utf-8-sig", compression="gzip")
    shutil.copy2(PARENT_DB, OUTPUT / "data" / PARENT_DB.name)


def create_notebook(tables: dict[str, pd.DataFrame], qc: pd.DataFrame) -> None:
    def markdown(source: str) -> dict[str, object]:
        return {"cell_type": "markdown", "metadata": {}, "source": source.splitlines(keepends=True)}

    def code(source: str) -> dict[str, object]:
        return {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": source.splitlines(keepends=True)}

    cells = [
        markdown(
            "# ALLdis父数据库第一阶段：D1—D10确定性分析\n\n"
            "本Notebook使用上传的父数据库v1、WPP 2024人口、CVD v16政策效果/成本父版本，运行2025—2050确定性分析。"
            "GBD输入封装在标准化投影层，新GBD到达后只需替换该层并重跑。"
        ),
        markdown(
            "## 可选：从标准化输入重新运行模型\n\n"
            "交付包已包含当前运行所需输入。将`RUN_MODEL`改为`True`后执行本单元，可从`input/`重建`results/`和`data/`。"
            "新GBD到达时应先生成同字段的两个标准化文件；不要覆盖官方原始ZIP。"
        ),
        code(
            "from pathlib import Path\nimport subprocess, sys\n"
            "PROJECT = Path.cwd()\nRUN_MODEL = False\n"
            "if RUN_MODEL:\n"
            "    subprocess.run([sys.executable, str(PROJECT / 'src' / 'run_d1_d10_stage.py')], check=True)\n"
            "else:\n"
            "    print('使用已封库结果；如需重算，请将 RUN_MODEL 改为 True。')"
        ),
        code(
            "import pandas as pd\n"
            "RESULTS = PROJECT / 'results'\n"
            "qc = pd.read_csv(RESULTS / '00_QC.csv')\nqc"
        ),
        markdown("## D1—D10实施状态"),
        code("methods = pd.read_csv(RESULTS / '04_D1_D10_method_status.csv')\nmethods"),
        markdown("## 5年、10年与2025—2050累计结果"),
        code(
            "summary = pd.read_csv(RESULTS / '05_primary_horizon_summary.csv')\n"
            "summary.loc[summary['scenario_id'].isin(['S2','S4','S6']), [\n"
            " 'horizon_years','scenario_id','cumulative_avoided_daly_undiscounted',\n"
            " 'cumulative_avoided_deaths_undiscounted','cumulative_avoided_incidence',\n"
            " 'discounted_programme_cost_2025_cny','icer_vs_s0_programme_only_cny_per_daly']]"
        ),
        markdown("## 成本效果前沿（政策实施成本桥接视角）"),
        code("frontier = pd.read_csv(RESULTS / '07_primary_frontiers.csv')\nfrontier"),
        markdown("## S6疾病、年龄与性别贡献"),
        code(
            "disease = pd.read_csv(RESULTS / '10_S6_disease_DALY_contribution_2025_2050.csv')\n"
            "age = pd.read_csv(RESULTS / '11_S6_age_DALY_contribution_2025_2050.csv')\n"
            "sex = pd.read_csv(RESULTS / '12_S6_sex_DALY_contribution_2025_2050.csv')\n"
            "display(disease, age, sex)"
        ),
        markdown("## D1、D2、D3与D9结构敏感性"),
        code("sens = pd.read_csv(RESULTS / '09_S6_structural_sensitivity.csv')\nsens"),
        markdown(
            "## D4—D8与D10边界说明\n\n"
            "D4严格首年事件费用目前只覆盖IHD、卒中和7种癌症；公共支付比例与4个结局的严格首年费用仍缺，"
            "所以本阶段不把部分医疗费用节约写入公共支付方headline净成本。D6—D8已建立接口但不输出虚构数值。"
            "D10输出高血压避免患者年，并将痴呆长期照护作为暂定社会成本卫星结果。"
        ),
        code(
            "d4 = pd.read_csv(RESULTS / '13_D4_cost_interface.csv')\n"
            "d4coverage = pd.read_csv(RESULTS / '14_D4_partial_medical_savings_coverage.csv')\n"
            "productivity = pd.read_csv(RESULTS / '16_D6_D8_productivity_interface.csv')\n"
            "display(d4, d4coverage.loc[d4coverage['scenario_id'].eq('S6')].tail(), productivity)"
        ),
    ]
    nb = {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    (OUTPUT / "00_父数据库D1_D10确定性分析.ipynb").write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")


def create_readme(tables: dict[str, pd.DataFrame], qc: pd.DataFrame) -> None:
    summary = tables["horizon_summary"]
    s6 = summary.loc[summary["scenario_id"].eq("S6")].set_index("horizon_years")
    frontier = tables["frontiers"]
    qc_pass = int(qc["passed"].sum())
    qc_total = len(qc)
    disease = tables["contribution_disease"].head(5)
    lines = [
        "# ALLdis GBD 2010—2023更新与D1—D10确定性封库 v1.3",
        "",
        f"生成时间：{datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')}",
        "",
        "## 本阶段定位",
        "",
        "本阶段使用用户上传的GBD 2023原始ZIP补充2010—2017，并与父数据库v1中的2018—2023拼接为连续历史序列；父数据库继续提供三水平身体活动基线和13结局RR。",
        "人口采用WPP 2024 Medium原始年龄—性别序列并与CVD v16保持一致；父数据库旧2025人口仅作迁移审计。政策效果与政策实施成本继承CVD v16。",
        "D3主分析使用2010—2023年龄—性别疾病率趋势，2035—2040衰减至零；2018—2023近期趋势、2023固定率和趋势持续均作为结构敏感性。",
        "",
        "## 主要确定性结果（S6综合政策）",
        "",
    ]
    for h in HORIZONS:
        r = s6.loc[h]
        lines.append(
            f"- {h}年（截至{int(r.end_year)}）：累计避免DALY {r.cumulative_avoided_daly_undiscounted:,.0f}，"
            f"避免死亡 {r.cumulative_avoided_deaths_undiscounted:,.0f}，避免新发病例 {r.cumulative_avoided_incidence:,.0f}；"
            f"贴现政策实施成本 {r.discounted_programme_cost_2025_cny/1e8:,.2f}亿元。"
        )
    lines += [
        "",
        "上述CEA是政策实施成本桥接视角，不是D5最终公共支付方净成本。D4事件费用和公共支付比例补齐后，"
        "才能形成正式公共支付方净成本、ICER和NMB。",
        "",
        "## 2025—2050 S6避免DALY贡献前五位",
        "",
    ]
    for r in disease.itertuples(index=False):
        lines.append(f"- {r.outcome_name_cn}：{r.discounted_avoided_daly:,.0f}贴现DALY（{r.contribution_share:.1%}）")
    lines += [
        "",
        "## D1—D10完成度",
        "",
        "- D1、D2：已正式接入主分析并运行结构敏感性。",
        "- D3：2010—2023主趋势已接入；近期趋势、固定率和持续趋势敏感性均已运行。",
        "- D4：严格首年事件费用仅部分覆盖，结果单列且不进入headline。",
        "- D5：公共支付方接口已建；缺公共支付比例，暂报政策实施成本桥接CEA。",
        "- D6—D8：计算接口与年龄边界已建，缺劳动与生产率输入，未输出估计值。",
        "- D9：full、75%维护和2034后停止三条路径已运行；2035—2050资本更新成本仍为INTERIM。",
        "- D10：高血压避免患者年已运行；痴呆长期照护作为暂定社会成本卫星模块。",
        "",
        "## 质量控制",
        "",
        f"- QC通过：{qc_pass}/{qc_total}。",
        f"- CVD v16疾病投影最大相对差异：{tables['cvd_projection_crosscheck']['relative_difference'].abs().max():.3e}。",
        f"- 父数据库与CVD v16三水平PA基线最大绝对差异：{tables['pa_crosscheck'][['low_difference','moderate_difference','high_difference']].abs().max().max():.3e}。",
        "- 本阶段未运行正式10,000次PSA；更新后的2×100次烟雾测试通过后即可交由用户本地运行。",
        "",
        "## GBD更新状态与正式PSA顺序",
        "",
        "1. 2010—2017原始ZIP已保留并标准化；2018—2023继续来自同为GBD 2023的父数据库；",
        "2. WPP 2024历史人口已扩展为2010—2023，并与旧2018—2023序列逐格一致；",
        "3. 本轮重新估计率趋势并重建2025—2050疾病投影；",
        "4. 下一步运行2批×100次联合PSA烟雾测试；",
        "5. 全部QC通过后，使用正式运行Notebook执行20批×500次、合计10,000次PSA。",
        "",
        "本地重新运行模型会更新CSV与Notebook结果层，但不会自动刷新Excel审计工作簿；新GBD版本封库时应重新生成工作簿并重建清单。",
    ]
    (OUTPUT / "README_阶段结果与GBD更新说明.md").write_text("\n".join(lines), encoding="utf-8")


def create_manifest(qc: pd.DataFrame) -> None:
    slope_audit = pd.read_csv(OUTPUT / "results" / "21_GBD_rate_slope_audit_burden.csv", encoding="utf-8-sig")
    history_start = int(slope_audit["history_start_year"].min())
    history_end = int(slope_audit["history_end_year"].max())
    status = {
        "analysis_version": "ALLdis_D1_D10_GBD2010_2023_v1.3",
        "parent_database_sha256": sha256(PARENT_DB),
        "gbd_history_window": f"{history_start}-{history_end}",
        "projection_horizon": "2025-2050",
        "formal_psa_run": False,
        "qc_passed": bool(qc.loc[qc["severity"].eq("ERROR"), "passed"].all()),
        "headline_decision_view": "INTERIM_BRIDGE_PROGRAMME_COST_ONLY",
        "d3_status": "GBD_2010_2023_MAIN_HISTORY_LOCKED",
        "formal_psa_ready_after_smoke_qc": True,
        "d4_d5_status": "PARTIAL_NOT_HEADLINE",
        "d6_d8_status": "INTERFACE_ONLY",
        "d9_2035_2050_cost_status": "INTERIM",
        "workbook_refresh_required_after_local_model_rerun": True,
    }
    (OUTPUT / "STAGE_STATUS.json").write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    files = []
    for path in sorted(OUTPUT.rglob("*")):
        if path.is_file() and path.name != "DELIVERABLE_MANIFEST.csv":
            files.append({"relative_path": path.relative_to(OUTPUT).as_posix(), "size_bytes": path.stat().st_size, "sha256": sha256(path)})
    pd.DataFrame(files).to_csv(OUTPUT / "DELIVERABLE_MANIFEST.csv", index=False, encoding="utf-8-sig")


def main() -> None:
    if OUTPUT.exists() and not PORTABLE_MODE:
        shutil.rmtree(OUTPUT)
    elif PORTABLE_MODE:
        for directory in [OUTPUT / "results", OUTPUT / "data"]:
            if directory.exists():
                shutil.rmtree(directory)
        for filename in [
            "00_父数据库D1_D10确定性分析.ipynb",
            "README_阶段结果与GBD更新说明.md",
            "DELIVERABLE_MANIFEST.csv",
            "STAGE_STATUS.json",
            "ALLdis_父数据库第一阶段D1_D10结果_v1.1.xlsx",
            "ALLdis_父数据库第一阶段D1_D10结果_v1.1.xlsx.inspect.ndjson",
        ]:
            path = OUTPUT / filename
            if path.exists():
                path.unlink()
    tables = run_analysis()
    qc = build_qc(tables)
    save_tables(tables, qc)
    create_notebook(tables, qc)
    create_readme(tables, qc)
    create_manifest(qc)
    print(qc.to_string(index=False))
    print("OUTPUT", OUTPUT)


if __name__ == "__main__":
    main()
