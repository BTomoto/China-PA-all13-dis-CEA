from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "input"
PSA_INPUT = INPUT / "psa"
PARENT_DB = INPUT / "parent" / "中国20岁以上成年人身体活动不足13结局综合政策CEA父数据库_v1.xlsx"

AGE_GROUPS = ["20-24", "25-29", "30-34", "35-39", "40-44", "45-49", "50-54", "55-59", "60-64", "65-69", "70+"]
SEXES = ["Female", "Male"]
YEARS = list(range(2025, 2051))
COMPONENT_NAMES = {495: "ischemic_stroke", 496: "intracerebral_hemorrhage", 497: "subarachnoid_hemorrhage"}


def read_parent(sheet: str) -> pd.DataFrame:
    return pd.read_excel(PARENT_DB, sheet_name=sheet, header=2).dropna(how="all").reset_index(drop=True)


def normalize_age(value: object) -> str:
    return str(value).strip().replace(" years", "").replace(" year", "")


def cpi_factor(source_year: int) -> float:
    annual = {
        2015: 0.014,
        2016: 0.020,
        2017: 0.016,
        2018: 0.021,
        2019: 0.029,
        2020: 0.025,
        2021: 0.009,
        2022: 0.020,
        2023: 0.002,
        2024: 0.002,
        2025: 0.000,
    }
    out = 1.0
    for year in range(int(source_year) + 1, 2026):
        out *= 1.0 + annual[year]
    return out


def fit_log_rate(year: np.ndarray, rate: np.ndarray) -> tuple[float, float, int]:
    ok = np.isfinite(year) & np.isfinite(rate) & (rate > 0)
    x = year[ok].astype(float)
    y = np.log(rate[ok].astype(float))
    n = len(x)
    if n < 2:
        return 0.0, 0.0, n
    x0 = x - x.mean()
    denom = float(np.square(x0).sum())
    raw_slope = float((x0 * (y - y.mean())).sum() / denom) if denom > 0 else 0.0
    fitted = y.mean() + raw_slope * x0
    if n > 2 and denom > 0:
        residual_var = float(np.square(y - fitted).sum() / (n - 2))
        slope_se = math.sqrt(max(residual_var, 0.0) / denom)
    else:
        slope_se = 0.0
    return float(np.clip(raw_slope, -0.10, 0.10)), float(slope_se), n


def build_gbd_parameters(source_file: str, domain: str, measures: set[str]) -> pd.DataFrame:
    raw = pd.read_csv(INPUT / "gbd_standardized" / source_file, encoding="utf-8-sig")
    hist_pop = pd.read_csv(INPUT / "population" / "WPP2024_China_age_sex_history.csv", encoding="utf-8-sig")
    raw["year"] = pd.to_numeric(raw["year"], errors="raise").astype(int)
    raw["cause_id"] = pd.to_numeric(raw["cause_id"], errors="raise").astype(int)
    raw["age_group"] = raw["age_name"].map(normalize_age)
    raw["sex"] = raw["sex_name"].astype(str)
    raw["outcome_id"] = raw["lancet_outcome_id"].astype(str)
    raw["component_id"] = [COMPONENT_NAMES.get(int(c), str(o)) for c, o in zip(raw["cause_id"], raw["outcome_id"])]
    raw = raw.loc[
        raw["year"].between(2010, 2023)
        & raw["age_group"].isin(AGE_GROUPS)
        & raw["sex"].isin(SEXES)
        & raw["measure_name"].isin(measures)
    ].copy()
    female_only = raw["outcome_id"].isin(["breast_cancer", "endometrial_cancer"])
    raw = raw.loc[~female_only | raw["sex"].eq("Female")].copy()
    raw = raw.merge(hist_pop[["year", "sex", "age_group", "population"]], on=["year", "sex", "age_group"], validate="many_to_one")
    raw["rate"] = pd.to_numeric(raw["val"], errors="coerce") / pd.to_numeric(raw["population"], errors="coerce")

    groups = ["outcome_id", "component_id", "cause_id", "cause_name", "sex", "age_group", "measure_name"]
    rows: list[dict[str, object]] = []
    for keys, g in raw.groupby(groups, sort=False, dropna=False):
        g = g.sort_values("year")
        slope, slope_se, n = fit_log_rate(g["year"].to_numpy(float), g["rate"].to_numpy(float))
        anchor = g.loc[g["year"].eq(2023)].iloc[-1]
        anchor_rate = float(anchor["rate"])
        val = float(anchor["val"])
        lower = float(anchor["lower"]) if pd.notna(anchor["lower"]) else math.nan
        upper = float(anchor["upper"]) if pd.notna(anchor["upper"]) else math.nan
        if val > 0 and lower > 0 and upper > lower:
            sigma = float((math.log(upper) - math.log(lower)) / (2.0 * 1.96))
        else:
            sigma = 0.0
        measure_short = {
            "Deaths": "Deaths",
            "YLLs (Years of Life Lost)": "YLL",
            "YLDs (Years Lived with Disability)": "YLD",
            "Incidence": "Incidence",
        }[str(keys[6])]
        rows.append({
            "parameter_id": f"{domain}|{keys[1]}|{keys[4]}|{keys[5]}|{measure_short}",
            "value_domain": domain,
            "outcome_id": keys[0],
            "component_id": keys[1],
            "cause_id": int(keys[2]),
            "cause_name": keys[3],
            "sex": keys[4],
            "age_group": keys[5],
            "measure_short": measure_short,
            "anchor_year": 2023,
            "anchor_value": val,
            "anchor_lower": lower,
            "anchor_upper": upper,
            "anchor_rate": anchor_rate,
            "baseline_log_sigma": sigma,
            "trend_slope": slope,
            "trend_slope_se": slope_se,
            "history_years": n,
            "trend_lower_cap": -0.10,
            "trend_upper_cap": 0.10,
            "baseline_distribution": "mean_preserving_lognormal",
            "trend_distribution": "normal_slope_capped_with_GH_mean_correction",
            "d3_main_rule": "2010-2023 log-rate trend; damp after 2034; zero by 2040",
            "data_status": "GBD_2010_2023_FINAL_HISTORY",
        })
    out = pd.DataFrame(rows).sort_values(["component_id", "sex", "age_group", "measure_short"]).reset_index(drop=True)
    return out


def build_pa_parameters() -> pd.DataFrame:
    pa = read_parent("PA_binary_20plus")
    cols = ["sex", "age_group", "n", "alpha_inactive", "alpha_moderate", "alpha_high", "source_variant", "parameter_status"]
    out = pa[cols].copy().rename(columns={
        "alpha_inactive": "dirichlet_alpha_low",
        "alpha_moderate": "dirichlet_alpha_moderate",
        "alpha_high": "dirichlet_alpha_high",
    })
    out.insert(0, "parameter_id", [f"PA|{s}|{a}" for s, a in zip(out["sex"], out["age_group"])])
    out["distribution"] = "Dirichlet"
    out["correlation_rule"] = "three PA levels sampled jointly within age-sex stratum"
    return out


def build_rr_parameters() -> pd.DataFrame:
    parent = read_parent("RR_main").set_index("outcome_id")
    cvd = pd.read_csv(INPUT / "cvd_v16_core" / "rr_3level_ihd_is.csv", encoding="utf-8-sig").set_index("disease_id")
    rows: list[dict[str, object]] = []
    for outcome, row in parent.iterrows():
        if outcome == "stroke":
            components = ["ischemic_stroke", "intracerebral_hemorrhage", "subarachnoid_hemorrhage"]
        else:
            components = [outcome]
        for component in components:
            if component == "coronary_heart_disease":
                x = cvd.loc["IHD"]
                low, mod = float(x["rr_low"]), float(x["rr_moderate"])
                sig_low, sig_mod = float(x["log_sigma_low"]), float(x["log_sigma_moderate"])
                source = "CVD v16 three-level Kyu RR"
                corr = 0.5
            elif component == "ischemic_stroke":
                x = cvd.loc["IS"]
                low, mod = float(x["rr_low"]), float(x["rr_moderate"])
                sig_low, sig_mod = float(x["log_sigma_low"]), float(x["log_sigma_moderate"])
                source = "CVD v16 three-level Kyu RR"
                corr = 0.5
            else:
                low, mod = float(row["rr_inactive_vs_active"]), 1.0
                sig_low, sig_mod = float(row["log_sigma"]), 0.0
                source = "Parent binary RR; moderate bridged to RR=1"
                corr = 0.0
            rows.append({
                "parameter_id": f"RR|{component}",
                "outcome_id": outcome,
                "component_id": component,
                "rr_low_mean": low,
                "rr_moderate_mean": mod,
                "rr_high": 1.0,
                "log_sigma_low": sig_low,
                "log_sigma_moderate": sig_mod,
                "low_moderate_log_correlation": corr,
                "distribution": "mean_preserving_lognormal",
                "sex_use": row["sex_use"],
                "source": source,
                "parameter_status": row["parameter_status"],
                "no_truncation_note": "CI crossing 1 is retained; no risk-protective draw truncation",
            })
    return pd.DataFrame(rows)


def build_policy_parameters() -> pd.DataFrame:
    out = pd.read_csv(INPUT / "cvd_v16_core" / "policy_scenarios.csv", encoding="utf-8-sig")
    keep = ["scenario_id", "scenario_name_cn", "theta_mean", "theta_low", "theta_high", "psa_distribution", "beta_alpha", "beta_beta", "coverage_mean", "ramp_years", "frontier_eligible", "cost_eligible", "evidence_status"]
    out = out[keep].copy()
    out.insert(0, "parameter_id", "THETA_" + out["scenario_id"].astype(str))
    out["coverage_distribution"] = "fixed_in_current_PSA"
    out["effect_cost_independence"] = "independent pending empirical covariance"
    return out


def build_cost_parameters() -> pd.DataFrame:
    cv = {"S1": 0.35, "S2": 0.20, "S3": 0.30, "S4": 0.30, "S5": 0.40, "S6": 0.30}
    rows = []
    for sid, value in cv.items():
        sigma = math.sqrt(math.log1p(value * value))
        rows.append({
            "parameter_id": f"COST_MULT_{sid}",
            "scenario_id": sid,
            "distribution": "mean_preserving_lognormal_multiplier",
            "mean": 1.0,
            "cv": value,
            "log_mu": -0.5 * sigma * sigma,
            "log_sigma": sigma,
            "lower_truncation": 0.25,
            "upper_truncation": 4.0,
            "temporal_correlation": "perfect within draw across years",
            "evidence_basis": "CVD v16 v1.4 FINAL_MODEL_BASED",
        })
    return pd.DataFrame(rows)


def build_d4_parameters() -> pd.DataFrame:
    cpi_2014 = cpi_factor(2014)
    cpi_2017 = cpi_factor(2017)
    usd_to_cny_2014 = 1.0 / 0.163
    current = pd.read_csv(ROOT / "results" / "13_D4_cost_interface.csv", encoding="utf-8-sig").set_index("outcome_id")
    rows = [
        ("coronary_heart_disease", 19633.0 * cpi_2017, 0.45, "CHINA_INCIDENT_MI_IMMEDIATE_PROXY", "China claims: incident MI immediate-quarter incremental direct medical cost; T2D cohort", 2017, "https://pmc.ncbi.nlm.nih.gov/articles/PMC7843809/", "LOWER_BOUND_PROXY_NOT_FULL_FIRST_YEAR"),
        ("stroke", 26612.67 * cpi_2017, 24373.40 / 26612.67, "CHINA_FIRST_ISCHAEMIC_STROKE_ONE_YEAR", "CNSR-III first-ever ischaemic stroke, index plus one-year follow-up direct medical cost", 2017, "https://www.ispor.org/docs/default-source/euro2022/poster-stroke-burden1020clean-pdf.pdf", "CHINA_FIRST_YEAR_IS_PROXY_FOR_ALL_STROKE_SUBTYPES"),
        ("bladder_cancer", float(current.loc["bladder_cancer", "cost_2025_cny"]), 0.50, "INTERNATIONAL_PROXY_BLADDER", "International first-year event proxy retained", 2025, "", "INTERNATIONAL_PROXY"),
        ("breast_cancer", 7527.0 * usd_to_cny_2014 * cpi_2014, 0.35, "CHINA_BREAST_NEW_DIAGNOSIS_COURSE", "13-province multicentre newly diagnosed course medical expenditure", 2014, "https://pubmed.ncbi.nlm.nih.gov/28670694/", "CHINA_FIRST_YEAR_EQUIVALENT"),
        ("colon_cancer", 61829.0 * cpi_2014, 0.35, "CHINA_CRC_NEW_DIAGNOSIS_COURSE", "13-province multicentre newly diagnosed course direct medical expenditure", 2014, "https://pmc.ncbi.nlm.nih.gov/articles/PMC5410077/", "CHINA_FIRST_YEAR_EQUIVALENT"),
        ("endometrial_cancer", float(current.loc["endometrial_cancer", "cost_2025_cny"]), 0.50, "INTERNATIONAL_PROXY_ENDOMETRIAL", "International first-year event proxy retained; GBD uterine crosswalk", 2025, "", "INTERNATIONAL_PROXY"),
        ("oesophageal_cancer", 10506.0 * 0.907 * usd_to_cny_2014 * cpi_2014, 0.40, "CHINA_OESOPHAGEAL_NEW_DIAGNOSIS_DERIVED", "Newly diagnosed course total direct expenditure; medical share derived from common-cancer study", 2014, "https://www.sciencedirect.com/science/article/abs/pii/S0140673616319377", "CHINA_DERIVED_MEDICAL_SHARE"),
        ("gastric_cancer", 9899.0 * 0.912 * usd_to_cny_2014 * cpi_2014, 0.35, "CHINA_GASTRIC_NEW_DIAGNOSIS_COURSE", "37-hospital newly diagnosed course; medical share 91.2%", 2014, "https://www.frontiersin.org/journals/public-health/articles/10.3389/fpubh.2020.00310/full", "CHINA_FIRST_YEAR_EQUIVALENT"),
        ("renal_cancer", float(current.loc["renal_cancer", "cost_2025_cny"]), 0.50, "INTERNATIONAL_PROXY_RENAL", "International first-year event proxy retained", 2025, "", "INTERNATIONAL_PROXY"),
    ]
    missing = {
        "type2_diabetes": "MISSING_STRICT_FIRST_YEAR_COST",
        "hypertension": "NO_INCIDENCE_LINK; D10 uses avoided patient-years",
        "dementia": "MISSING_STRICT_FIRST_YEAR_COST",
        "depression": "MISSING_STRICT_FIRST_YEAR_COST",
    }
    output = []
    for outcome, mean, cv, pid, boundary, source_year, url, status in rows:
        sigma = math.sqrt(math.log1p(cv * cv))
        output.append({
            "parameter_id": pid,
            "outcome_id": outcome,
            "mean_2025_cny": mean,
            "cv": cv,
            "log_mu": math.log(mean) - 0.5 * sigma * sigma,
            "log_sigma": sigma,
            "distribution": "mean_preserving_lognormal",
            "cost_boundary": "incident case first-year direct medical cost",
            "evidence_boundary": boundary,
            "source_price_year": source_year,
            "source_url": url,
            "d4_status": status,
            "included_in_partial_payer_net": "YES",
        })
    for outcome, status in missing.items():
        output.append({
            "parameter_id": f"D4_MISSING_{outcome}",
            "outcome_id": outcome,
            "mean_2025_cny": math.nan,
            "cv": math.nan,
            "log_mu": math.nan,
            "log_sigma": math.nan,
            "distribution": "missing",
            "cost_boundary": "incident case first-year direct medical cost",
            "evidence_boundary": "Not imputed from patient-year cost",
            "source_price_year": math.nan,
            "source_url": "",
            "d4_status": status,
            "included_in_partial_payer_net": "NO",
        })
    return pd.DataFrame(output)


def build_d5_parameter() -> pd.DataFrame:
    employee_n = 37948.34
    resident_n = 94713.73
    employee_share = 0.848
    resident_share = 0.686
    weighted = (employee_n * employee_share + resident_n * resident_share) / (employee_n + resident_n)
    concentration = 60.0
    return pd.DataFrame([{
        "parameter_id": "D5_PUBLIC_PAYER_SHARE_NATIONAL_BRIDGE",
        "mean": weighted,
        "distribution": "Beta",
        "beta_alpha": weighted * concentration,
        "beta_beta": (1.0 - weighted) * concentration,
        "approx_95_lower": weighted - 1.96 * math.sqrt(weighted * (1.0 - weighted) / (concentration + 1.0)),
        "approx_95_upper": weighted + 1.96 * math.sqrt(weighted * (1.0 - weighted) / (concentration + 1.0)),
        "employee_enrolment_10k": employee_n,
        "resident_enrolment_10k": resident_n,
        "employee_inpatient_directory_fund_share": employee_share,
        "resident_inpatient_directory_fund_share": resident_share,
        "source_year": 2024,
        "source_url": "https://www.nhsa.gov.cn/art/2025/7/14/art_7_17248.html",
        "status": "INTERIM_NATIONAL_BRIDGE_NOT_DISEASE_SPECIFIC",
        "use_rule": "Common draw across diseases; applies only to covered D4 direct medical savings",
    }])


def build_d9_rules() -> pd.DataFrame:
    return pd.DataFrame([
        ["D9-5Y", 5, "FORMAL_PSA_READY", "2025-2029", "CVD v16 final programme cost; no post-2034 renewal dependency", "Main formal health-economic PSA"],
        ["D9-10Y", 10, "FORMAL_PSA_READY", "2025-2034", "CVD v16 final programme cost; no post-2034 renewal dependency", "Main formal health-economic PSA"],
        ["D9-26Y", 26, "INTERIM_STRUCTURAL_SENSITIVITY", "2025-2050", "2035-2050 holds 2034 steady-state; S3/S4/S5/S6 renewal gaps unresolved", "Extended result; not paper headline until renewal audit closes"],
        ["D9-S5-SW", 26, "PARTIAL_EVIDENCE", "S5 software", "8-year annualization exists in S5 lock; hardware replacement still conditional", "Do not add software cash plus annuity"],
        ["D9-S3-CAP", 26, "OPEN_GAP", "S3 capital", "Cash and EAC are mutually exclusive; lifetime/replacement share not nationally closed", "Retain structural sensitivity"],
        ["D9-S4-EQP", 26, "OPEN_GAP", "S4 equipment", "Equipment economic annualization exists; explicit national replacement timing not separated", "Retain structural sensitivity"],
        ["D9-S6-DEDUP", 26, "OPEN_GAP", "S6 composite", "Renewal ownership and shared-pool deduplication unresolved", "Never sum S1-S5 raw modules into S6"],
    ], columns=["rule_id", "horizon_years", "status", "scope", "evidence", "model_use"])


def build_registry(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = [
        ["GBD_BASELINE", "D3", "Burden/cases by component-age-sex", "Lognormal", "GBD 2023 lower/upper", "READY", "2023 anchor from parent database GBD 2023"],
        ["GBD_TREND", "D3", "2010-2023 log-rate slope", "Capped Normal", "History residual SE", "READY", "Damped after 2034; recent-window structural sensitivity deterministic only"],
        ["PA_BASELINE", "D2", "Three PA levels by age-sex", "Dirichlet", "Parent microdata counts", "READY", "Joint probabilities sum to one"],
        ["RR", "D1/health", "Outcome/component RR", "Lognormal", "Published 95% CI", "READY", "No truncation when CI crosses 1"],
        ["POLICY_EFFECT", "Policy", "Theta by strategy", "Beta", "Locked policy prior", "READY", "Coverage fixed in current PSA"],
        ["S0_TREND", "D2", "Low-PA annual trend", "Triangular", "0.0042/0.0084/0.0126", "READY", "Damped after 2034"],
        ["PROGRAMME_COST", "D9", "Strategy aggregate multiplier", "Lognormal", "CVD v16 cost CV", "READY_5Y_10Y", "Perfect temporal correlation"],
        ["D4_FIRST_YEAR_COST", "D4", "Covered outcome cost", "Lognormal", "China evidence plus explicit proxies", "PARTIAL", "Missing outcomes not imputed"],
        ["D5_PAYER_SHARE", "D5", "National bridge", "Beta", "NHSA 2024", "INTERIM", "Not disease-specific"],
        ["LAG", "D1", "Group-specific latency", "Structural", "Locked D1 rule", "READY_STRUCTURAL", "Not randomized in PSA"],
        ["CAPITAL_RENEWAL", "D9", "2035-2050 renewal", "Structural", "S3-S6 gap register", "OPEN", "Long horizon not headline"],
    ]
    return pd.DataFrame(rows, columns=["parameter_family", "decision", "unit", "distribution", "evidence", "status", "correlation_or_rule"])


def main() -> None:
    PSA_INPUT.mkdir(parents=True, exist_ok=True)
    tables = {
        "gbd_burden": build_gbd_parameters("GBD_burden_components.csv.gz", "burden", {"Deaths", "YLLs (Years of Life Lost)", "YLDs (Years Lived with Disability)"}),
        "gbd_incidence": build_gbd_parameters("GBD_cases_components.csv.gz", "cases", {"Incidence"}),
        "pa": build_pa_parameters(),
        "rr": build_rr_parameters(),
        "policy": build_policy_parameters(),
        "programme_cost": build_cost_parameters(),
        "d4": build_d4_parameters(),
        "d5": build_d5_parameter(),
        "d9": build_d9_rules(),
    }
    tables["registry"] = build_registry(tables)
    file_map = {
        "gbd_burden": "gbd_burden_psa_parameters_v1.2.csv.gz",
        "gbd_incidence": "gbd_incidence_psa_parameters_v1.2.csv.gz",
        "pa": "pa_dirichlet_parameters_v1.2.csv",
        "rr": "rr_component_parameters_v1.2.csv",
        "policy": "policy_effect_parameters_v1.2.csv",
        "programme_cost": "programme_cost_parameters_v1.2.csv",
        "d4": "D4_first_year_cost_parameters_v1.2.csv",
        "d5": "D5_public_payer_share_v1.2.csv",
        "d9": "D9_horizon_and_renewal_rules_v1.2.csv",
        "registry": "PSA_parameter_registry_v1.2.csv",
    }
    for key, filename in file_map.items():
        compression = "gzip" if filename.endswith(".gz") else None
        tables[key].to_csv(PSA_INPUT / filename, index=False, encoding="utf-8-sig", compression=compression)

    plan = pd.DataFrame([
        [1, 100, 2026080201, 0, "SMOKE", "executed_in_delivery"],
        [2, 100, 2026080202, 100, "SMOKE", "executed_in_delivery"],
        *[[i, 500, 2026081000 + i, (i - 1) * 500, "FORMAL", "ready_after_v1_3_smoke_qc"] for i in range(1, 21)],
    ], columns=["batch_id", "draws", "seed", "draw_offset", "run_type", "status"])
    plan.to_csv(PSA_INPUT / "PSA_batch_plan_v1.2.csv", index=False, encoding="utf-8-sig")

    manifest = {
        "model_version": "ALLdis_D1_D10_joint_PSA_v1.3_GBD2010_2023",
        "formal_psa_run": False,
        "smoke_draws_planned": 200,
        "formal_draws_planned": 10000,
        "formal_batch_plan": "20 batches x 500 draws",
        "main_formal_horizons_when_unlocked": [5, 10],
        "extended_horizon_status": "INTERIM_STRUCTURAL_SENSITIVITY",
        "gbd_status": "GBD_2010_2023_FINAL_HISTORY_LOCKED",
        "formal_psa_status": "READY_FOR_USER_LOCAL_RUN_AFTER_SMOKE_QC",
        "d4_status": "PARTIAL",
        "d5_status": "INTERIM_NATIONAL_BRIDGE",
    }
    (PSA_INPUT / "PSA_INPUT_MANIFEST_v1.2.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: len(v) for k, v in tables.items()}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
