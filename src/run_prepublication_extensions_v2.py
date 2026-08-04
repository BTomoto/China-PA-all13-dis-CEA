from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


BASE_YEAR = 2025
END_YEAR = 2050
HORIZONS = (5, 10, 26)
SCENARIOS = tuple(f"S{i}" for i in range(8))
FOUR_OUTCOMES = ("type2_diabetes", "depression", "dementia", "hypertension")
AGE_MIDPOINT = {
    "20-24": 22,
    "25-29": 27,
    "30-34": 32,
    "35-39": 37,
    "40-44": 42,
    "45-49": 47,
    "50-54": 52,
    "55-59": 57,
    "60-64": 62,
    "65-69": 67,
}
OUTCOME_CN = {
    "type2_diabetes": "2型糖尿病",
    "depression": "抑郁症",
    "dementia": "痴呆",
    "hypertension": "高血压",
}
LANCET_CANCERS = {
    "bladder_cancer",
    "breast_cancer",
    "colon_cancer",
    "endometrial_cancer",
    "oesophageal_cancer",
    "gastric_cancer",
    "renal_cancer",
}
LANCET_UNIT_COST_2020_USD = {
    "bladder_cancer": 2514.0,
    "breast_cancer": 1676.0,
    "colon_cancer": 3447.0,
    "endometrial_cancer": 3133.0,
    "oesophageal_cancer": 1117.0,
    "gastric_cancer": 1117.0,
    "renal_cancer": 1843.0,
    "coronary_heart_disease": 205.47,
    "depression": 243.046852,
    "stroke": 791.19,
    "type2_diabetes": 185.075154,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ALLdis pre-publication economic extension")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--authorised-data-root",
        type=Path,
        required=True,
        help="Authorised local archive containing data/*.csv.gz and input/gbd_standardized/*.csv.gz",
    )
    parser.add_argument("--draws", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=20260803)
    return parser.parse_args()


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path, encoding="utf-8-sig")


def param_dict(params: pd.DataFrame) -> dict[str, float]:
    return dict(zip(params["parameter_id"], pd.to_numeric(params["value"], errors="raise")))


def weighted_payer_share(p: dict[str, float]) -> float:
    numerator = (
        p["EMPLOYEE_MEDICAL_ENROLMENT"] * p["EMPLOYEE_INPATIENT_FUND_SHARE"]
        + p["RESIDENT_MEDICAL_ENROLMENT"] * p["RESIDENT_INPATIENT_FUND_SHARE"]
    )
    denominator = p["EMPLOYEE_MEDICAL_ENROLMENT"] + p["RESIDENT_MEDICAL_ENROLMENT"]
    return numerator / denominator


def load_inputs(repo: Path, source: Path) -> dict[str, pd.DataFrame]:
    return {
        "cases": read_csv(source / "data" / "health_cases_detail_primary.csv.gz"),
        "burden": read_csv(source / "data" / "health_burden_detail_primary.csv.gz"),
        "hypertension": read_csv(source / "data" / "hypertension_detail_primary.csv.gz"),
        "pa": read_csv(source / "data" / "PA_trajectory_primary.csv.gz"),
        "case_projection": read_csv(source / "data" / "GBD_cases_projection_2025_2050.csv.gz"),
        "gbd_case_history": read_csv(source / "input" / "gbd_standardized" / "GBD_cases_components.csv.gz"),
        "population": read_csv(repo / "results" / "01_population_2025_2050.csv"),
        "pa_baseline": read_csv(repo / "results" / "02_PA_baseline_from_parent.csv"),
        "rr": read_csv(repo / "results" / "03_RR_three_level_bridge.csv"),
        "horizon": read_csv(repo / "results" / "05_primary_horizon_summary.csv"),
        "payer_cost": read_csv(repo / "results" / "19_policy_cost_payer_2025_2050.csv"),
        "societal_cost": read_csv(repo / "results" / "20_policy_cost_societal_2025_2050.csv"),
        "d4": read_csv(repo / "input" / "psa" / "D4_first_year_cost_parameters_v1.2.csv"),
        "formal_metrics": read_csv(repo / "results" / "tables" / "formal_psa_v1.4" / "02_metric_summary.csv"),
        "medical_params": read_csv(repo / "input" / "prepublication_extensions" / "medical_cost_parameters_2025cny.csv"),
        "macro_params": read_csv(repo / "input" / "prepublication_extensions" / "macro_and_payer_parameters.csv"),
        "rand": read_csv(repo / "input" / "prepublication_extensions" / "rand_china_gdp_benchmark.csv"),
        "lancet": read_csv(repo / "input" / "prepublication_extensions" / "lancet_china_benchmark.csv"),
    }


def make_four_disease_annual(data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    case = data["cases"].loc[data["cases"]["outcome_id"].isin(FOUR_OUTCOMES[:3])].copy()
    case = case.groupby(["scenario_id", "year", "outcome_id", "measure_short"], as_index=False)["avoided_value"].sum()
    burden = data["burden"].loc[data["burden"]["outcome_id"].isin(FOUR_OUTCOMES[:3])].copy()
    burden = burden.groupby(["scenario_id", "year", "outcome_id", "measure_short"], as_index=False)["avoided_value"].sum()
    health = pd.concat([case, burden], ignore_index=True)
    health = health.pivot_table(
        index=["scenario_id", "year", "outcome_id"],
        columns="measure_short",
        values="avoided_value",
        aggfunc="sum",
        fill_value=0.0,
    ).reset_index()
    htn = data["hypertension"].groupby(["scenario_id", "year"], as_index=False)["avoided_value"].sum()
    htn["outcome_id"] = "hypertension"
    htn = htn.rename(columns={"avoided_value": "Hypertension patient-years"})
    annual = pd.concat([health, htn], ignore_index=True, sort=False).fillna(0.0)
    for metric in ["Incidence", "Prevalence", "DALY", "Deaths", "YLD", "YLL", "Hypertension patient-years"]:
        if metric not in annual:
            annual[metric] = 0.0
    annual["outcome_name_cn"] = annual["outcome_id"].map(OUTCOME_CN)
    annual["discount_factor"] = 1 / 1.03 ** (annual["year"] - BASE_YEAR)
    annual["discounted_DALY"] = annual["DALY"] * annual["discount_factor"]
    annual["discounted_Deaths"] = annual["Deaths"] * annual["discount_factor"]
    return annual.sort_values(["scenario_id", "year", "outcome_id"]).reset_index(drop=True)


def summarise_four_diseases(annual: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    metrics = ["Incidence", "Prevalence", "DALY", "discounted_DALY", "Deaths", "discounted_Deaths", "YLD", "YLL", "Hypertension patient-years"]
    for horizon in HORIZONS:
        end_year = BASE_YEAR + horizon - 1
        grouped = annual.loc[annual["year"].le(end_year)].groupby(["scenario_id", "outcome_id", "outcome_name_cn"], as_index=False)[metrics].sum()
        grouped.insert(0, "horizon_years", horizon)
        grouped.insert(1, "end_year", end_year)
        rows.extend(grouped.to_dict("records"))
    return pd.DataFrame(rows)


def d4_event_cost_rows(data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    d4 = data["d4"].loc[data["d4"]["mean_2025_cny"].notna()].copy()
    d4["low_2025_cny"] = np.exp(d4["log_mu"] - 1.96 * d4["log_sigma"])
    d4["high_2025_cny"] = np.exp(d4["log_mu"] + 1.96 * d4["log_sigma"])
    inc = data["cases"].loc[data["cases"]["measure_short"].eq("Incidence")].groupby(
        ["scenario_id", "year", "outcome_id"], as_index=False
    )["avoided_value"].sum()
    inc = inc.merge(d4[["outcome_id", "parameter_id", "mean_2025_cny", "low_2025_cny", "high_2025_cny", "cost_boundary"]], on="outcome_id", validate="many_to_one")
    return pd.DataFrame({
        "scenario_id": inc["scenario_id"],
        "year": inc["year"],
        "outcome_id": inc["outcome_id"],
        "cost_stream": "direct_medical",
        "basis": "avoided_incident_case_first_year",
        "avoided_units": inc["avoided_value"],
        "unit_cost_main_2025_cny": inc["mean_2025_cny"],
        "unit_cost_low_2025_cny": inc["low_2025_cny"],
        "unit_cost_high_2025_cny": inc["high_2025_cny"],
        "parameter_id": inc["parameter_id"],
        "dedup_rule": "Event-specific first-year cost; no annual patient-year cost added for the same outcome",
    })


def four_disease_cost_rows(data: dict[str, pd.DataFrame], annual: pd.DataFrame) -> pd.DataFrame:
    params = data["medical_params"].loc[~data["medical_params"]["cost_stream"].eq("direct_medical_sensitivity")].copy()
    rows: list[pd.DataFrame] = []
    for p in params.itertuples(index=False):
        metric = "Hypertension patient-years" if p.outcome_id == "hypertension" else "Prevalence"
        x = annual.loc[annual["outcome_id"].eq(p.outcome_id), ["scenario_id", "year", "outcome_id", metric]].copy()
        x = x.rename(columns={metric: "avoided_units"})
        x["cost_stream"] = p.cost_stream
        x["basis"] = p.basis
        x["unit_cost_main_2025_cny"] = p.main_2025_cny
        x["unit_cost_low_2025_cny"] = p.low_2025_cny
        x["unit_cost_high_2025_cny"] = p.high_2025_cny
        x["parameter_id"] = p.parameter_id
        x["dedup_rule"] = p.dedup_rule
        rows.append(x)
    return pd.concat(rows, ignore_index=True)


def build_medical_savings(data: dict[str, pd.DataFrame], annual: pd.DataFrame, payer_share: float) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    detail = pd.concat([d4_event_cost_rows(data), four_disease_cost_rows(data, annual)], ignore_index=True, sort=False)
    for variant in ("main", "low", "high"):
        detail[f"savings_{variant}_2025_cny"] = detail["avoided_units"] * detail[f"unit_cost_{variant}_2025_cny"]
        detail[f"discounted_savings_{variant}_2025_cny"] = detail[f"savings_{variant}_2025_cny"] / 1.03 ** (detail["year"] - BASE_YEAR)
    direct = detail.loc[detail["cost_stream"].eq("direct_medical")].groupby(["scenario_id", "year"], as_index=False)[
        [f"savings_{v}_2025_cny" for v in ("main", "low", "high")]
    ].sum()
    direct = direct.rename(columns={f"savings_{v}_2025_cny": f"direct_medical_savings_{v}_2025_cny" for v in ("main", "low", "high")})
    care = detail.loc[detail["cost_stream"].eq("nonmedical_and_informal_care")].groupby(["scenario_id", "year"], as_index=False)[
        [f"savings_{v}_2025_cny" for v in ("main", "low", "high")]
    ].sum()
    care = care.rename(columns={f"savings_{v}_2025_cny": f"dementia_care_savings_{v}_2025_cny" for v in ("main", "low", "high")})
    aggregate = direct.merge(care, on=["scenario_id", "year"], how="left").fillna(0.0)
    aggregate["public_payer_share_2025_bridge"] = payer_share
    for v in ("main", "low", "high"):
        aggregate[f"public_payer_savings_{v}_2025_cny"] = aggregate[f"direct_medical_savings_{v}_2025_cny"] * payer_share
    summary_rows: list[dict[str, object]] = []
    value_cols = [c for c in aggregate.columns if c.endswith("_2025_cny")]
    for horizon in HORIZONS:
        end = BASE_YEAR + horizon - 1
        x = aggregate.loc[aggregate["year"].le(end)].copy()
        for col in value_cols:
            x[col] = x[col] / 1.03 ** (x["year"] - BASE_YEAR)
        g = x.groupby("scenario_id", as_index=False)[value_cols].sum()
        g.insert(0, "horizon_years", horizon)
        g.insert(1, "end_year", end)
        summary_rows.extend(g.to_dict("records"))
    return detail, aggregate, pd.DataFrame(summary_rows)


def cost_boundary_audit() -> pd.DataFrame:
    rows = [
        ("coronary_heart_disease", "incident-first-year", "included", "Do not add annual IHD patient-year cost"),
        ("stroke", "incident-first-year", "included", "All stroke subtypes share one composite event-cost stream"),
        ("type2_diabetes", "prevalence-patient-year", "included", "Use no-complication routine cost; exclude macrovascular complication cost"),
        ("depression", "prevalence-patient-year", "included", "No death/YLL stream; depression-index direct cost only"),
        ("dementia", "prevalence-patient-year", "included", "Direct medical and social care streams reported separately"),
        ("hypertension", "hypertension-patient-year", "included", "Hypertension-specific cost only; downstream CVD excluded"),
        ("cancers", "incident-first-year", "included", "Each cancer cost connected only to its own avoided incidence"),
        ("informal_care", "dementia-patient-year", "social-only", "Never treated as insurer or public payer saving"),
    ]
    return pd.DataFrame(rows, columns=["outcome_or_stream", "selected_basis", "status", "non_overlap_rule"])


def prepare_lancet_incidence(data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    history = data["gbd_case_history"].loc[
        data["gbd_case_history"]["measure_name"].eq("Incidence") & data["gbd_case_history"]["year"].between(2020, 2023)
    ].copy()
    history["age_group"] = history["age_name"].str.replace(" years", "", regex=False)
    history = history.rename(columns={"sex_name": "sex", "lancet_outcome_id": "outcome_id", "val": "cases"})
    component_map = {495: "ischemic_stroke", 496: "intracerebral_hemorrhage", 497: "subarachnoid_hemorrhage"}
    history["component_id"] = [component_map.get(int(c), str(o)) for c, o in zip(history["cause_id"], history["outcome_id"])]
    history = history[["year", "sex", "age_group", "outcome_id", "component_id", "cases"]]
    projection = data["case_projection"].loc[
        data["case_projection"]["measure_short"].eq("Incidence") & data["case_projection"]["year"].between(2025, 2030),
        ["year", "sex", "age_group", "outcome_id", "component_id", "projected_value"],
    ].rename(columns={"projected_value": "cases"})
    y2023 = history.loc[history["year"].eq(2023)].drop(columns="year")
    y2025 = projection.loc[projection["year"].eq(2025)].drop(columns="year")
    y2024 = y2023.merge(y2025, on=["sex", "age_group", "outcome_id", "component_id"], suffixes=("_2023", "_2025"), validate="one_to_one")
    y2024["cases"] = (y2024["cases_2023"] + y2024["cases_2025"]) / 2
    y2024["year"] = 2024
    y2024 = y2024[["year", "sex", "age_group", "outcome_id", "component_id", "cases"]]
    return pd.concat([history, y2024, projection], ignore_index=True)


def lancet_satellite(data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    incidence = prepare_lancet_incidence(data)
    incidence = incidence.merge(
        data["pa_baseline"][["sex", "age_group", "low_prev", "moderate_prev", "high_prev"]],
        on=["sex", "age_group"], validate="many_to_one"
    ).merge(
        data["rr"][["outcome_id", "component_id", "rr_low", "rr_moderate", "rr_high"]],
        on=["outcome_id", "component_id"], validate="many_to_one"
    )
    model_den = incidence["low_prev"] * incidence["rr_low"] + incidence["moderate_prev"] * incidence["rr_moderate"] + incidence["high_prev"] * incidence["rr_high"]
    incidence["paf_model_pa"] = (model_den - 1) / model_den
    inactive = incidence["sex"].map({"Male": 0.160, "Female": 0.122})
    calibrated_den = inactive * incidence["rr_low"] + (1 - inactive)
    incidence["paf_lancet_pa"] = (calibrated_den - 1) / calibrated_den
    rows: list[dict[str, object]] = []
    for calibration, paf_col in [("MODEL_PARENT_PA", "paf_model_pa"), ("LANCET_PA_CALIBRATED", "paf_lancet_pa")]:
        x = incidence.loc[incidence["outcome_id"].isin(set(LANCET_UNIT_COST_2020_USD))].copy()
        x["attributable_cases"] = x["cases"] * x[paf_col]
        x["direct_cost_2020_usd"] = x["attributable_cases"] * x["outcome_id"].map(LANCET_UNIT_COST_2020_USD)
        x["outcome_group"] = np.where(x["outcome_id"].isin(LANCET_CANCERS), "cancers", x["outcome_id"])
        grouped = x.groupby("outcome_group", as_index=False)[["attributable_cases", "direct_cost_2020_usd"]].sum()
        grouped["calibration"] = calibration
        rows.extend(grouped.to_dict("records"))
    result = pd.DataFrame(rows).merge(data["lancet"], on="outcome_group", how="outer")
    result["case_ratio_vs_lancet"] = result["attributable_cases"] / result["lancet_attributable_cases_2020_2030"]
    result["cost_ratio_vs_lancet"] = result["direct_cost_2020_usd"] / result["lancet_direct_cost_2020_usd"]
    result["comparison_status"] = np.where(result["attributable_cases"].notna(), "ESTIMATED", "NOT_ESTIMABLE_FROM_CURRENT_HYPERTENSION_INPUT")
    return result.sort_values(["calibration", "outcome_group"], na_position="last").reset_index(drop=True)


def lancet_gap_decomposition(lancet: pd.DataFrame) -> pd.DataFrame:
    """Multiplicatively split the model/Lancet gap into exposure and residual terms."""
    common = ["cancers", "coronary_heart_disease", "depression", "stroke", "type2_diabetes"]
    model = lancet.loc[
        lancet["calibration"].eq("MODEL_PARENT_PA") & lancet["outcome_group"].isin(common),
        ["outcome_group", "attributable_cases", "direct_cost_2020_usd"],
    ].rename(columns={
        "attributable_cases": "model_parent_pa_cases",
        "direct_cost_2020_usd": "model_parent_pa_cost_2020_usd",
    })
    calibrated = lancet.loc[
        lancet["calibration"].eq("LANCET_PA_CALIBRATED") & lancet["outcome_group"].isin(common),
        [
            "outcome_group",
            "attributable_cases",
            "direct_cost_2020_usd",
            "lancet_attributable_cases_2020_2030",
            "lancet_direct_cost_2020_usd",
        ],
    ].rename(columns={
        "attributable_cases": "lancet_pa_calibrated_cases",
        "direct_cost_2020_usd": "lancet_pa_calibrated_cost_2020_usd",
    })
    out = model.merge(calibrated, on="outcome_group", validate="one_to_one")
    out["case_total_ratio_model_vs_lancet"] = out["model_parent_pa_cases"] / out["lancet_attributable_cases_2020_2030"]
    out["case_exposure_multiplier"] = out["model_parent_pa_cases"] / out["lancet_pa_calibrated_cases"]
    out["case_residual_ratio_after_pa_calibration"] = out["lancet_pa_calibrated_cases"] / out["lancet_attributable_cases_2020_2030"]
    out["cost_total_ratio_model_vs_lancet"] = out["model_parent_pa_cost_2020_usd"] / out["lancet_direct_cost_2020_usd"]
    out["cost_exposure_multiplier"] = out["model_parent_pa_cost_2020_usd"] / out["lancet_pa_calibrated_cost_2020_usd"]
    out["cost_residual_ratio_after_pa_calibration"] = out["lancet_pa_calibrated_cost_2020_usd"] / out["lancet_direct_cost_2020_usd"]
    return out.sort_values("outcome_group").reset_index(drop=True)


def pa_with_population(data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    pop = data["population"][["year", "sex", "age_group", "population_model"]]
    pa = data["pa"].merge(pop, on=["year", "sex", "age_group"], validate="many_to_one")
    pa = pa.loc[pa["age_group"].ne("70+")].copy()
    pa["newly_active_equivalent_persons"] = (pa["low_s0"] - pa["low_policy"]).clip(lower=0) * pa["population_model"]
    return pa


def mortality_worker_stock(data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    deaths = data["burden"].loc[
        data["burden"]["measure_short"].eq("Deaths") & data["burden"]["age_group"].isin(AGE_MIDPOINT)
    ].groupby(["scenario_id", "year", "sex", "age_group"], as_index=False)["avoided_value"].sum()
    rows: list[dict[str, object]] = []
    for scenario in SCENARIOS:
        ds = deaths.loc[deaths["scenario_id"].eq(scenario)]
        for year in range(BASE_YEAR, END_YEAR + 1):
            eligible = ds.loc[ds["year"].le(year)].copy()
            eligible["attained_age"] = eligible["age_group"].map(AGE_MIDPOINT) + year - eligible["year"]
            rows.append({
                "scenario_id": scenario,
                "year": year,
                "retirement_bound_survivor_stock": eligible.loc[eligible["attained_age"].lt(70), "avoided_value"].sum(),
            })
    return pd.DataFrame(rows)


def gdp_mechanism(data: dict[str, pd.DataFrame], p: dict[str, float]) -> pd.DataFrame:
    pa = pa_with_population(data)
    work_pop_2025 = data["population"].loc[
        data["population"]["year"].eq(2025) & data["population"]["age_group"].isin(AGE_MIDPOINT), "population_model"
    ].sum()
    employment_ratio = min(0.95, p["CHINA_EMPLOYED_PERSONS"] / work_pop_2025)
    output_per_worker = p["CHINA_GDP"] / p["CHINA_EMPLOYED_PERSONS"]
    shifted = pa.groupby(["scenario_id", "year"], as_index=False).agg(
        newly_active_equivalent_persons=("newly_active_equivalent_persons", "sum"),
        population_20_69=("population_model", "sum"),
    )
    stock = mortality_worker_stock(data)
    out = shifted.merge(stock, on=["scenario_id", "year"], validate="one_to_one")
    out["employment_ratio_proxy"] = employment_ratio
    out["output_per_worker_2025_cny"] = output_per_worker
    variants = {
        "LOW": (p["RAND_ABSENCE_DAYS_LOW"] + p["RAND_PRESENTEEISM_DAYS_LOW"], p["LABOUR_OUTPUT_ELASTICITY_LOW"], p["MORTALITY_STOCK_FACTOR_LOW"], 0.90),
        "MAIN": ((p["RAND_ABSENCE_DAYS_LOW"] + p["RAND_PRESENTEEISM_DAYS_LOW"] + p["RAND_ABSENCE_DAYS_HIGH"] + p["RAND_PRESENTEEISM_DAYS_HIGH"]) / 2, p["LABOUR_OUTPUT_ELASTICITY_MAIN"], p["MORTALITY_STOCK_FACTOR_MAIN"], 1.00),
        "HIGH": (p["RAND_ABSENCE_DAYS_HIGH"] + p["RAND_PRESENTEEISM_DAYS_HIGH"], p["LABOUR_OUTPUT_ELASTICITY_HIGH"], p["MORTALITY_STOCK_FACTOR_HIGH"], 1.10),
    }
    long_rows: list[pd.DataFrame] = []
    for variant, (days, elasticity, stock_factor, employment_factor) in variants.items():
        x = out.copy()
        x["variant"] = variant
        x["days_saved_per_newly_active_worker"] = days
        x["labour_output_elasticity"] = elasticity
        x["mortality_stock_factor"] = stock_factor
        effective_employment = np.minimum(0.95, employment_ratio * employment_factor)
        x["activity_productivity_gain_2025_cny"] = (
            x["newly_active_equivalent_persons"] * effective_employment * days / p["WORKING_DAYS_PER_YEAR"] * output_per_worker * elasticity
        )
        x["mortality_labour_supply_gain_2025_cny"] = (
            x["retirement_bound_survivor_stock"] * effective_employment * output_per_worker * elasticity * stock_factor
        )
        x["gdp_equivalent_gain_2025_cny"] = x["activity_productivity_gain_2025_cny"] + x["mortality_labour_supply_gain_2025_cny"]
        x["discounted_gdp_equivalent_gain_2025_cny"] = x["gdp_equivalent_gain_2025_cny"] / 1.03 ** (x["year"] - BASE_YEAR)
        long_rows.append(x)
    return pd.concat(long_rows, ignore_index=True)


def rand_calibrated(data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    pa = pa_with_population(data)
    shifted = pa.groupby(["scenario_id", "year", "sex"], as_index=False).agg(
        shifted=("newly_active_equivalent_persons", "sum"), population=("population_model", "sum")
    )
    inactive_map = {"Male": 0.160, "Female": 0.122}
    shifted["rand_inactive_persons"] = shifted["population"] * shifted["sex"].map(inactive_map)
    shifted = shifted.groupby(["scenario_id", "year"], as_index=False)[["shifted", "population", "rand_inactive_persons"]].sum()
    shifted["policy_to_rand1_activity_shift_ratio"] = shifted["shifted"] / shifted["rand_inactive_persons"]
    benchmark = data["rand"].loc[data["rand"]["scenario"].eq("RAND1")].copy()
    rows: list[pd.DataFrame] = []
    for variant in ("LOW", "HIGH"):
        b = benchmark.loc[benchmark["variant"].eq(variant)].set_index("year")["annual_gdp_gain_2019_usd_bn"]
        annual = b.reindex(range(BASE_YEAR, END_YEAR + 1)).interpolate(method="linear").rename("rand1_annual_gdp_gain_2019_usd_bn").reset_index().rename(columns={"index": "year"})
        x = shifted.merge(annual, on="year", validate="many_to_one")
        x["variant"] = variant
        x["policy_rand_calibrated_annual_gain_2019_usd_bn"] = x["policy_to_rand1_activity_shift_ratio"] * x["rand1_annual_gdp_gain_2019_usd_bn"]
        x["policy_rand_calibrated_cumulative_2025_2050_2019_usd_bn"] = x.groupby("scenario_id")["policy_rand_calibrated_annual_gain_2019_usd_bn"].cumsum()
        rows.append(x)
    return pd.concat(rows, ignore_index=True)


def horizon_sum(annual: pd.DataFrame, value_col: str, variant: str | None = None) -> pd.DataFrame:
    data = annual if variant is None else annual.loc[annual["variant"].eq(variant)]
    rows = []
    for horizon in HORIZONS:
        end = BASE_YEAR + horizon - 1
        x = data.loc[data["year"].le(end)].groupby("scenario_id", as_index=False)[value_col].sum()
        x["horizon_years"] = horizon
        rows.append(x)
    return pd.concat(rows, ignore_index=True)


def return_on_investment(data: dict[str, pd.DataFrame], medical_summary: pd.DataFrame, medical_annual: pd.DataFrame, gdp: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    payer_cost = data["payer_cost"][["scenario_id", "year", "annual_programme_cost_2025_cny"]].rename(columns={"annual_programme_cost_2025_cny": "payer_programme_cost"})
    societal_cost = data["societal_cost"][["scenario_id", "year", "annual_programme_cost_2025_cny"]].rename(columns={"annual_programme_cost_2025_cny": "societal_programme_cost"})
    med = medical_annual[["scenario_id", "year", "public_payer_savings_main_2025_cny", "direct_medical_savings_main_2025_cny", "dementia_care_savings_main_2025_cny"]]
    gdpm = gdp.loc[gdp["variant"].eq("MAIN"), ["scenario_id", "year", "gdp_equivalent_gain_2025_cny"]]
    annual = payer_cost.merge(societal_cost, on=["scenario_id", "year"]).merge(med, on=["scenario_id", "year"]).merge(gdpm, on=["scenario_id", "year"])
    annual["public_benefits"] = annual["public_payer_savings_main_2025_cny"]
    annual["societal_benefits"] = annual["direct_medical_savings_main_2025_cny"] + annual["dementia_care_savings_main_2025_cny"] + annual["gdp_equivalent_gain_2025_cny"]
    annual["discount_factor"] = 1 / 1.03 ** (annual["year"] - BASE_YEAR)
    for c in ["payer_programme_cost", "societal_programme_cost", "public_benefits", "societal_benefits"]:
        annual[f"discounted_{c}"] = annual[c] * annual["discount_factor"]
    annual = annual.sort_values(["scenario_id", "year"])
    annual["cum_discounted_public_net"] = annual.groupby("scenario_id")["discounted_public_benefits"].cumsum() - annual.groupby("scenario_id")["discounted_payer_programme_cost"].cumsum()
    annual["cum_discounted_societal_net"] = annual.groupby("scenario_id")["discounted_societal_benefits"].cumsum() - annual.groupby("scenario_id")["discounted_societal_programme_cost"].cumsum()
    rows: list[dict[str, object]] = []
    for horizon in HORIZONS:
        end = BASE_YEAR + horizon - 1
        for sid, x in annual.loc[annual["year"].le(end)].groupby("scenario_id"):
            payer_cost_sum = x["discounted_payer_programme_cost"].sum()
            societal_cost_sum = x["discounted_societal_programme_cost"].sum()
            public_benefit = x["discounted_public_benefits"].sum()
            societal_benefit = x["discounted_societal_benefits"].sum()
            rows.append({
                "horizon_years": horizon,
                "end_year": end,
                "scenario_id": sid,
                "discounted_payer_programme_cost_2025_cny": payer_cost_sum,
                "discounted_public_payer_medical_savings_2025_cny": public_benefit,
                "public_payer_net_cost_2025_cny": payer_cost_sum - public_benefit,
                "public_payer_benefit_cost_ratio": public_benefit / payer_cost_sum if payer_cost_sum > 0 else np.nan,
                "discounted_societal_programme_cost_2025_cny": societal_cost_sum,
                "discounted_total_societal_benefits_2025_cny": societal_benefit,
                "societal_net_benefit_2025_cny": societal_benefit - societal_cost_sum,
                "societal_benefit_cost_ratio": societal_benefit / societal_cost_sum if societal_cost_sum > 0 else np.nan,
                "public_payback_year": x.loc[x["cum_discounted_public_net"].ge(0), "year"].min() if payer_cost_sum > 0 else np.nan,
                "societal_payback_year": x.loc[x["cum_discounted_societal_net"].ge(0), "year"].min() if societal_cost_sum > 0 else np.nan,
            })
    return annual, pd.DataFrame(rows)


def lognormal_draws(mean: float, sd: float, n: int, rng: np.random.Generator) -> np.ndarray:
    if mean <= 0 or sd <= 0:
        return np.full(n, max(mean, 0.0))
    sigma2 = math.log1p((sd / mean) ** 2)
    return rng.lognormal(math.log(mean) - sigma2 / 2, math.sqrt(sigma2), n)


def economic_satellite_uncertainty(
    data: dict[str, pd.DataFrame], medical_summary: pd.DataFrame, gdp: pd.DataFrame, p: dict[str, float], n: int, seed: int
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    metrics = data["formal_metrics"]
    gdp_sums = {v: horizon_sum(gdp, "discounted_gdp_equivalent_gain_2025_cny", v) for v in ("LOW", "MAIN", "HIGH")}
    payer_mean = weighted_payer_share(p)
    ess = p["PAYER_SHARE_EFFECTIVE_SAMPLE_SIZE"]
    payer_draw = rng.beta(payer_mean * ess, (1 - payer_mean) * ess, n)
    rows: list[dict[str, object]] = []
    for sid in ("S4", "S6"):
        for horizon in HORIZONS:
            med = medical_summary.loc[(medical_summary["scenario_id"].eq(sid)) & (medical_summary["horizon_years"].eq(horizon))].iloc[0]
            g_low = gdp_sums["LOW"].loc[(gdp_sums["LOW"]["scenario_id"].eq(sid)) & (gdp_sums["LOW"]["horizon_years"].eq(horizon)), "discounted_gdp_equivalent_gain_2025_cny"].iloc[0]
            g_main = gdp_sums["MAIN"].loc[(gdp_sums["MAIN"]["scenario_id"].eq(sid)) & (gdp_sums["MAIN"]["horizon_years"].eq(horizon)), "discounted_gdp_equivalent_gain_2025_cny"].iloc[0]
            g_high = gdp_sums["HIGH"].loc[(gdp_sums["HIGH"]["scenario_id"].eq(sid)) & (gdp_sums["HIGH"]["horizon_years"].eq(horizon)), "discounted_gdp_equivalent_gain_2025_cny"].iloc[0]
            effect_metric = metrics.loc[(metrics["scenario_id"].eq(sid)) & (metrics["horizon_years"].eq(horizon)) & metrics["metric"].eq("discounted_dalys_averted")].iloc[0]
            cost_metric = metrics.loc[(metrics["scenario_id"].eq(sid)) & (metrics["horizon_years"].eq(horizon)) & metrics["metric"].eq("discounted_programme_cost_2025_cny")].iloc[0]
            effect = lognormal_draws(float(effect_metric["mean"]), float(effect_metric["sd"]), n, rng) / float(effect_metric["mean"])
            programme_cost = lognormal_draws(float(cost_metric["mean"]), float(cost_metric["sd"]), n, rng)
            medical_cost_mult = rng.lognormal(-0.5 * math.log1p(0.35**2), math.sqrt(math.log1p(0.35**2)), n)
            direct = float(med["direct_medical_savings_main_2025_cny"]) * effect * medical_cost_mult
            care = float(med["dementia_care_savings_main_2025_cny"]) * effect * medical_cost_mult
            gdp_draw = rng.triangular(g_low, g_main, g_high, n) * effect
            public_savings = direct * payer_draw
            public_net = programme_cost - public_savings
            societal_benefit = direct + care + gdp_draw
            societal_bcr = societal_benefit / programme_cost
            outputs = {
                "public_payer_net_cost_2025_cny": public_net,
                "public_payer_medical_savings_2025_cny": public_savings,
                "societal_benefit_cost_ratio": societal_bcr,
                "societal_net_benefit_2025_cny": societal_benefit - programme_cost,
            }
            for metric_name, values in outputs.items():
                rows.append({
                    "scenario_id": sid,
                    "horizon_years": horizon,
                    "metric": metric_name,
                    "n_draws": n,
                    "mean": float(np.mean(values)),
                    "p2_5": float(np.quantile(values, 0.025)),
                    "median": float(np.median(values)),
                    "p97_5": float(np.quantile(values, 0.975)),
                    "probability_favourable": float(np.mean(values < 0)) if "net_cost" in metric_name else (float(np.mean(values > 0)) if "net_benefit" in metric_name else (float(np.mean(values > 1)) if "ratio" in metric_name else np.nan)),
                })
    return pd.DataFrame(rows)


def build_qc(
    four_annual: pd.DataFrame,
    medical_detail: pd.DataFrame,
    lancet: pd.DataFrame,
    lancet_decomposition: pd.DataFrame,
    gdp: pd.DataFrame,
    uncertainty: pd.DataFrame,
    payer_share: float,
    expected_draws: int,
) -> pd.DataFrame:
    checks: list[dict[str, object]] = []

    def add(check: str, passed: bool, observed: object, expected: object) -> None:
        checks.append({"check_id": check, "passed": bool(passed), "observed": observed, "expected": expected})

    add("FOUR_OUTCOMES_PRESENT", set(four_annual["outcome_id"]) == set(FOUR_OUTCOMES), sorted(four_annual["outcome_id"].unique()), sorted(FOUR_OUTCOMES))
    add("NO_NEGATIVE_HEALTH", (four_annual.select_dtypes("number") >= -1e-9).all().all(), float(four_annual.select_dtypes("number").min().min()), ">=-1e-9")
    add("D4_PLUS_FOUR_STREAMS", medical_detail["outcome_id"].nunique() == 13, medical_detail["outcome_id"].nunique(), 13)
    add("PAYER_SHARE_RANGE", 0 < payer_share < 1, payer_share, "(0,1)")
    calibrated = lancet.loc[lancet["calibration"].eq("LANCET_PA_CALIBRATED") & lancet["outcome_group"].isin(["cancers", "coronary_heart_disease", "depression", "stroke", "type2_diabetes"])]
    add("LANCET_CALIBRATED_CASE_RATIO", calibrated["case_ratio_vs_lancet"].between(0.75, 1.45).all(), f"{calibrated['case_ratio_vs_lancet'].min():.3f}-{calibrated['case_ratio_vs_lancet'].max():.3f}", "0.75-1.45")
    decomposition_error = (
        lancet_decomposition["case_total_ratio_model_vs_lancet"]
        - lancet_decomposition["case_exposure_multiplier"]
        * lancet_decomposition["case_residual_ratio_after_pa_calibration"]
    ).abs().max()
    add("LANCET_GAP_DECOMPOSITION_IDENTITY", decomposition_error < 1e-10, float(decomposition_error), "<1e-10")
    add("GDP_NONNEGATIVE", gdp["gdp_equivalent_gain_2025_cny"].ge(-1e-9).all(), float(gdp["gdp_equivalent_gain_2025_cny"].min()), ">=-1e-9")
    add("GDP_VARIANTS", set(gdp["variant"]) == {"LOW", "MAIN", "HIGH"}, sorted(gdp["variant"].unique()), ["HIGH", "LOW", "MAIN"])
    add(
        "UNCERTAINTY_DRAWS",
        uncertainty["n_draws"].min() == expected_draws,
        int(uncertainty["n_draws"].min()),
        expected_draws,
    )
    return pd.DataFrame(checks)


def main() -> None:
    args = parse_args()
    repo = args.repo_root.resolve()
    source = args.authorised_data_root.resolve()
    output = repo / "results" / "prepublication_v2"
    output.mkdir(parents=True, exist_ok=True)
    data = load_inputs(repo, source)
    p = param_dict(data["macro_params"])
    payer_share = weighted_payer_share(p)

    four_annual = make_four_disease_annual(data)
    four_summary = summarise_four_diseases(four_annual)
    medical_detail, medical_annual, medical_summary = build_medical_savings(data, four_annual, payer_share)
    audit = cost_boundary_audit()
    lancet = lancet_satellite(data)
    lancet_decomposition = lancet_gap_decomposition(lancet)
    gdp = gdp_mechanism(data, p)
    rand = rand_calibrated(data)
    roi_annual, roi_summary = return_on_investment(data, medical_summary, medical_annual, gdp)
    uncertainty = economic_satellite_uncertainty(data, medical_summary, gdp, p, args.draws, args.seed)
    qc = build_qc(
        four_annual,
        medical_detail,
        lancet,
        lancet_decomposition,
        gdp,
        uncertainty,
        payer_share,
        args.draws,
    )

    outputs = {
        "00_QC.csv": qc,
        "01_four_disease_annual_health.csv": four_annual,
        "02_four_disease_horizon_health.csv": four_summary,
        "03_medical_savings_detail.csv": medical_detail,
        "04_medical_savings_annual.csv": medical_annual,
        "05_medical_savings_horizon.csv": medical_summary,
        "06_cost_boundary_dedup_audit.csv": audit,
        "07_lancet_2020_2030_satellite.csv": lancet,
        "07b_lancet_gap_decomposition.csv": lancet_decomposition,
        "08_gdp_equivalent_mechanism_annual.csv": gdp,
        "09_rand_calibrated_gdp_annual.csv": rand,
        "10_return_on_investment_annual.csv": roi_annual,
        "11_return_on_investment_horizon.csv": roi_summary,
        "12_economic_satellite_uncertainty.csv": uncertainty,
    }
    for name, frame in outputs.items():
        frame.to_csv(output / name, index=False, encoding="utf-8-sig")
    metadata = {
        "analysis_version": "prepublication_v2.0",
        "authorised_data_root": "LOCAL_AUTHORISED_DATA_NOT_DISTRIBUTED",
        "public_payer_share_2025_bridge": payer_share,
        "economic_uncertainty_draws": args.draws,
        "economic_uncertainty_seed": args.seed,
        "strict_cge_completed": False,
        "gdp_label": "GDP-equivalent productivity benefit; mechanism-based and RAND-calibrated satellite estimates",
        "main_psa_replaced": False,
        "qc_passed": bool(qc["passed"].all()),
    }
    (output / "run_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(qc.to_string(index=False))
    print("OUTPUT", output)


if __name__ == "__main__":
    main()
