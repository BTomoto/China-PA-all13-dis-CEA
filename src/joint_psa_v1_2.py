from __future__ import annotations

import argparse
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "input"
PSA_INPUT = INPUT / "psa"
YEARS = np.arange(2025, 2051, dtype=int)
HORIZONS = [5, 10, 26]
WTP_VALUES = [50000.0, 100000.0, 150000.0]
HEALTH_DISCOUNT = 0.03
COST_DISCOUNT = 0.03
FRONTIER_SCENARIOS = [f"S{i}" for i in range(7)]


def trend_exposure() -> np.ndarray:
    values = []
    total = 1.0
    for year in YEARS:
        if year <= 2034:
            multiplier = 1.0
        else:
            multiplier = max(0.0, (2040 - int(year)) / 6.0)
        total += multiplier
        values.append(total)
    return np.asarray(values, dtype=float)


def s0_damping(year: int) -> float:
    if year <= 2034:
        return 1.0
    return max(0.0, (2040 - int(year)) / 6.0)


def trend_correction(slope: np.ndarray, se: np.ndarray, exposure: np.ndarray, lower: float = -0.10, upper: float = 0.10, nodes: int = 32) -> np.ndarray:
    x, w = np.polynomial.hermite.hermgauss(nodes)
    z = np.sqrt(2.0) * x
    w = w / np.sqrt(np.pi)
    sampled = np.clip(slope[:, None] + se[:, None] * z[None, :], lower, upper)
    delta = sampled - slope[:, None]
    correction = (np.exp(delta[:, None, :] * exposure[None, :, None]) * w[None, None, :]).sum(axis=2)
    return np.maximum(correction, 1e-300)


@dataclass
class GBDParameterSampler:
    params: pd.DataFrame
    population: pd.DataFrame
    component_index: dict[str, int]
    stratum_index: dict[tuple[str, str], int]

    def __post_init__(self) -> None:
        self.params = self.params.reset_index(drop=True).copy()
        pop_lookup = self.population.set_index(["year", "sex", "age_group"])["population_model"].to_dict()
        self.population_matrix = np.empty((len(self.params), len(YEARS)), dtype=float)
        self.component_target = np.empty(len(self.params), dtype=int)
        self.stratum_target = np.empty(len(self.params), dtype=int)
        for i, row in self.params.iterrows():
            self.component_target[i] = self.component_index[str(row["component_id"])]
            self.stratum_target[i] = self.stratum_index[(str(row["sex"]), str(row["age_group"]))]
            for yi, year in enumerate(YEARS):
                self.population_matrix[i, yi] = float(pop_lookup[(int(year), str(row["sex"]), str(row["age_group"]))])
        self.anchor_rate = self.params["anchor_rate"].to_numpy(float)
        self.sigma = self.params["baseline_log_sigma"].fillna(0.0).to_numpy(float)
        self.slope = self.params["trend_slope"].fillna(0.0).to_numpy(float)
        self.slope_se = self.params["trend_slope_se"].fillna(0.0).to_numpy(float)
        self.exposure = trend_exposure()
        self.correction = trend_correction(self.slope, self.slope_se, self.exposure)

    def sample(self, rng: np.random.Generator) -> tuple[np.ndarray, dict[str, float]]:
        z_base = rng.normal(size=len(self.params))
        z_trend = rng.normal(size=len(self.params))
        baseline = np.where(
            self.anchor_rate > 0,
            self.anchor_rate * np.exp(-0.5 * self.sigma**2 + self.sigma * z_base),
            0.0,
        )
        raw_slope = self.slope + self.slope_se * z_trend
        slope_draw = np.clip(raw_slope, -0.10, 0.10)
        values = (
            baseline[:, None]
            * np.exp(self.slope[:, None] * self.exposure[None, :])
            * np.exp((slope_draw - self.slope)[:, None] * self.exposure[None, :])
            / self.correction
            * self.population_matrix
        )
        audit = {
            "baseline_multiplier_mean": float(np.mean(np.divide(baseline, self.anchor_rate, out=np.ones_like(baseline), where=self.anchor_rate > 0))),
            "raw_slope_outside_cap_fraction": float(np.mean((raw_slope < -0.10) | (raw_slope > 0.10))),
        }
        return values, audit


class JointPSAEngine:
    def __init__(self) -> None:
        self.pa = pd.read_csv(PSA_INPUT / "pa_dirichlet_parameters_v1.2.csv", encoding="utf-8-sig")
        self.rr = pd.read_csv(PSA_INPUT / "rr_component_parameters_v1.2.csv", encoding="utf-8-sig")
        self.policy = pd.read_csv(PSA_INPUT / "policy_effect_parameters_v1.2.csv", encoding="utf-8-sig")
        self.cost_params = pd.read_csv(PSA_INPUT / "programme_cost_parameters_v1.2.csv", encoding="utf-8-sig")
        self.d4 = pd.read_csv(PSA_INPUT / "D4_first_year_cost_parameters_v1.2.csv", encoding="utf-8-sig")
        self.d5 = pd.read_csv(PSA_INPUT / "D5_public_payer_share_v1.2.csv", encoding="utf-8-sig").iloc[0]
        self.gbd_burden = pd.read_csv(PSA_INPUT / "gbd_burden_psa_parameters_v1.2.csv.gz", encoding="utf-8-sig")
        self.gbd_incidence = pd.read_csv(PSA_INPUT / "gbd_incidence_psa_parameters_v1.2.csv.gz", encoding="utf-8-sig")
        self.population = pd.read_csv(ROOT / "results" / "01_population_2025_2050.csv", encoding="utf-8-sig")
        self.cost_schedule = pd.read_csv(INPUT / "policy_costs_long_term" / "policy_cost_2025_2050_D9_main_interim.csv", encoding="utf-8-sig")
        self.scenarios = self.policy["scenario_id"].astype(str).tolist()
        self.scenario_index = {s: i for i, s in enumerate(self.scenarios)}
        self.strata = list(zip(self.pa["sex"].astype(str), self.pa["age_group"].astype(str)))
        self.stratum_index = {key: i for i, key in enumerate(self.strata)}
        self.components = self.rr["component_id"].astype(str).tolist()
        self.component_index = {c: i for i, c in enumerate(self.components)}
        self.outcomes = sorted(self.gbd_incidence["outcome_id"].astype(str).unique().tolist())
        self.outcome_index = {o: i for i, o in enumerate(self.outcomes)}

        self.pa_alpha = self.pa[["dirichlet_alpha_low", "dirichlet_alpha_moderate", "dirichlet_alpha_high"]].to_numpy(float)
        self.rr_mean = self.rr[["rr_low_mean", "rr_moderate_mean"]].to_numpy(float)
        self.rr_sigma = self.rr[["log_sigma_low", "log_sigma_moderate"]].fillna(0.0).to_numpy(float)
        self.rr_corr = self.rr["low_moderate_log_correlation"].fillna(0.0).to_numpy(float)
        self.policy_theta_mean = self.policy["theta_mean"].to_numpy(float)
        self.policy_coverage = self.policy["coverage_mean"].to_numpy(float)
        self.policy_ramp = self.policy["ramp_years"].to_numpy(float)
        self.policy_alpha = self.policy["beta_alpha"].to_numpy(float)
        self.policy_beta = self.policy["beta_beta"].to_numpy(float)
        self.policy_dist = self.policy["psa_distribution"].astype(str).str.lower().to_numpy()

        lag = pd.read_excel(INPUT / "parent" / "中国20岁以上成年人身体活动不足13结局综合政策CEA父数据库_v1.xlsx", sheet_name="lag_assumptions", header=2).dropna(how="all")
        self.lag = self._build_lag(lag)
        self.burden_sampler = GBDParameterSampler(self.gbd_burden, self.population, self.component_index, self.stratum_index)
        self.incidence_sampler = GBDParameterSampler(self.gbd_incidence, self.population, self.component_index, self.stratum_index)
        self.health_discount = 1.0 / np.power(1.0 + HEALTH_DISCOUNT, YEARS - 2025)
        self.cost_discount = 1.0 / np.power(1.0 + COST_DISCOUNT, YEARS - 2025)
        self.programme_cost_base = self._build_programme_cost_matrix()
        self.cost_multiplier = self.cost_params.set_index("scenario_id").to_dict("index")

    def _build_lag(self, lag: pd.DataFrame) -> np.ndarray:
        lookup = lag.loc[lag["analysis_role"].eq("main_structural")].set_index("lag_group")
        output = np.zeros((len(YEARS), len(self.components)), dtype=float)
        for ci, row in self.rr.iterrows():
            outcome = str(row["outcome_id"])
            if outcome in {"hypertension", "depression"}:
                group = "fast"
            elif outcome in {"coronary_heart_disease", "stroke", "type2_diabetes"}:
                group = "medium"
            elif outcome in {"bladder_cancer", "breast_cancer", "colon_cancer", "endometrial_cancer", "oesophageal_cancer", "gastric_cancer", "renal_cancer"}:
                group = "cancer"
            elif outcome == "dementia":
                group = "dementia"
            else:
                raise KeyError(outcome)
            delay = float(lookup.loc[group, "start_delay_years"])
            full = float(lookup.loc[group, "time_to_full"])
            for yi, year in enumerate(YEARS):
                elapsed = int(year) - 2025 + 1
                if elapsed <= delay:
                    value = 0.0
                elif full <= delay:
                    value = 1.0
                else:
                    value = float(np.clip((elapsed - delay) / (full - delay), 0.0, 1.0))
                output[yi, ci] = value
        return output

    def _build_programme_cost_matrix(self) -> np.ndarray:
        table = self.cost_schedule.loc[
            self.cost_schedule["perspective"].eq("payer")
            & self.cost_schedule["cost_structure_scenario"].eq("STRUCTURAL_ANCHOR")
            & self.cost_schedule["maintenance_scenario"].eq("D9_MAIN_FULL_MAINTENANCE")
        ].copy()
        pivot = table.pivot(index="scenario_id", columns="year", values="annual_programme_cost_2025_cny")
        return pivot.reindex(index=self.scenarios, columns=YEARS).to_numpy(float)

    def sample_pa(self, rng: np.random.Generator) -> np.ndarray:
        return np.vstack([rng.dirichlet(alpha) for alpha in self.pa_alpha])

    def sample_rr(self, rng: np.random.Generator) -> np.ndarray:
        out = np.ones((len(self.components), 3), dtype=float)
        for i in range(len(self.components)):
            rho = float(np.clip(self.rr_corr[i], -0.999, 0.999))
            z1, z2 = rng.normal(size=2)
            z_mod = rho * z1 + math.sqrt(1.0 - rho * rho) * z2
            out[i, 0] = self.rr_mean[i, 0] * math.exp(-0.5 * self.rr_sigma[i, 0] ** 2 + self.rr_sigma[i, 0] * z1)
            out[i, 1] = self.rr_mean[i, 1] * math.exp(-0.5 * self.rr_sigma[i, 1] ** 2 + self.rr_sigma[i, 1] * z_mod)
        return out

    def sample_theta(self, rng: np.random.Generator) -> np.ndarray:
        out = self.policy_theta_mean.copy()
        for i, dist in enumerate(self.policy_dist):
            if dist == "beta" and np.isfinite(self.policy_alpha[i]) and np.isfinite(self.policy_beta[i]):
                out[i] = rng.beta(self.policy_alpha[i], self.policy_beta[i])
        return out

    def build_pa_and_pif(self, pa_draw: np.ndarray, rr_draw: np.ndarray, theta_draw: np.ndarray, s0_trend: float) -> tuple[np.ndarray, float]:
        n_s, n_y, n_c, n_t = len(self.scenarios), len(YEARS), len(self.components), len(self.strata)
        pif = np.zeros((n_s, n_y, n_c, n_t), dtype=float)
        max_prob_error = 0.0
        for ti in range(n_t):
            low, moderate, high = pa_draw[ti]
            nonlow = max(moderate + high, 1e-15)
            mod_ratio, high_ratio = moderate / nonlow, high / nonlow
            for yi, year in enumerate(YEARS):
                if year > 2025:
                    low = min(0.999, low * (1.0 + s0_trend * s0_damping(int(year))))
                active = 1.0 - low
                mod_s0, high_s0 = active * mod_ratio, active * high_ratio
                risk0 = low * rr_draw[:, 0] + mod_s0 * rr_draw[:, 1] + high_s0
                for si, sid in enumerate(self.scenarios):
                    if sid == "S0":
                        realised = 0.0
                    else:
                        uptake = float(np.clip((int(year) - 2025 + 0.5) / max(self.policy_ramp[si], 1.0), 0.0, 1.0))
                        realised = theta_draw[si] * self.policy_coverage[si] * uptake
                    movers = low * realised
                    low_pol = low - movers
                    mod_pol = mod_s0 + movers * 0.8
                    high_pol = high_s0 + movers * 0.2
                    max_prob_error = max(max_prob_error, abs(low_pol + mod_pol + high_pol - 1.0))
                    risk_pol = low_pol * rr_draw[:, 0] + mod_pol * rr_draw[:, 1] + high_pol
                    raw = np.divide(risk0 - risk_pol, risk0, out=np.zeros_like(risk0), where=risk0 != 0)
                    pif[si, yi, :, ti] = raw * self.lag[yi]
        return pif, max_prob_error

    @staticmethod
    def aggregate_measure(values: np.ndarray, params: pd.DataFrame, sampler: GBDParameterSampler, pif: np.ndarray, measure: str) -> np.ndarray:
        mask = params["measure_short"].eq(measure).to_numpy()
        if not mask.any():
            return np.zeros((pif.shape[0], pif.shape[1]), dtype=float)
        comp = sampler.component_target[mask]
        strata = sampler.stratum_target[mask]
        selected_pif = pif[:, :, comp, strata]
        selected_values = values[mask].T
        return np.sum(selected_pif * selected_values[None, :, :], axis=2)

    def aggregate_incidence_by_outcome(self, values: np.ndarray, pif: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        total = np.zeros((len(self.scenarios), len(YEARS)), dtype=float)
        by_outcome = np.zeros((len(self.scenarios), len(YEARS), len(self.outcomes)), dtype=float)
        for outcome, oi in self.outcome_index.items():
            mask = self.gbd_incidence["outcome_id"].eq(outcome).to_numpy()
            comp = self.incidence_sampler.component_target[mask]
            strata = self.incidence_sampler.stratum_target[mask]
            x = np.sum(pif[:, :, comp, strata] * values[mask].T[None, :, :], axis=2)
            by_outcome[:, :, oi] = x
            total += x
        return total, by_outcome

    def sample_programme_cost(self, rng: np.random.Generator) -> tuple[np.ndarray, dict[str, float]]:
        out = self.programme_cost_base.copy()
        audit = {}
        for sid in self.scenarios:
            si = self.scenario_index[sid]
            if sid in self.cost_multiplier:
                p = self.cost_multiplier[sid]
                multiplier = math.exp(float(p["log_mu"]) + float(p["log_sigma"]) * rng.normal())
                multiplier = float(np.clip(multiplier, float(p["lower_truncation"]), float(p["upper_truncation"])))
                out[si] = out[si] * multiplier
                audit[f"programme_cost_multiplier_{sid}"] = multiplier
        return out, audit

    def sample_d4_costs(self, rng: np.random.Generator) -> tuple[np.ndarray, dict[str, float]]:
        costs = np.full(len(self.outcomes), np.nan, dtype=float)
        audit = {}
        d4_idx = self.d4.set_index("outcome_id")
        for outcome, oi in self.outcome_index.items():
            if outcome not in d4_idx.index:
                continue
            row = d4_idx.loc[outcome]
            if pd.notna(row["mean_2025_cny"]) and str(row["included_in_partial_payer_net"]) == "YES":
                draw = math.exp(float(row["log_mu"]) + float(row["log_sigma"]) * rng.normal())
                costs[oi] = draw
                audit[f"d4_cost_{outcome}"] = draw
        return costs, audit

    def run_batch(self, draws: int, seed: int, batch_id: int, draw_offset: int, output_dir: Path, formal_run: bool = False) -> dict[str, object]:
        output_dir.mkdir(parents=True, exist_ok=True)
        rng = np.random.default_rng(int(seed))
        cea_rows: list[dict[str, object]] = []
        audit_rows: list[dict[str, object]] = []
        start = time.perf_counter()
        for local_draw in range(1, int(draws) + 1):
            draw_id = int(draw_offset) + local_draw
            pa_draw = self.sample_pa(rng)
            rr_draw = self.sample_rr(rng)
            theta_draw = self.sample_theta(rng)
            s0_trend = float(rng.triangular(0.0042, 0.0084, 0.0126))
            pif, max_pa_error = self.build_pa_and_pif(pa_draw, rr_draw, theta_draw, s0_trend)
            burden_values, burden_audit = self.burden_sampler.sample(rng)
            incidence_values, incidence_audit = self.incidence_sampler.sample(rng)
            deaths = self.aggregate_measure(burden_values, self.gbd_burden, self.burden_sampler, pif, "Deaths")
            yll = self.aggregate_measure(burden_values, self.gbd_burden, self.burden_sampler, pif, "YLL")
            yld = self.aggregate_measure(burden_values, self.gbd_burden, self.burden_sampler, pif, "YLD")
            daly = yll + yld
            incidence, incidence_by_outcome = self.aggregate_incidence_by_outcome(incidence_values, pif)
            programme_cost, cost_audit = self.sample_programme_cost(rng)
            d4_cost, d4_audit = self.sample_d4_costs(rng)
            payer_share = float(rng.beta(float(self.d5["beta_alpha"]), float(self.d5["beta_beta"])))
            covered = np.isfinite(d4_cost)
            medical_savings = np.sum(incidence_by_outcome[:, :, covered] * d4_cost[covered][None, None, :], axis=2)

            for horizon in HORIZONS:
                n = int(horizon)
                d_daly = np.sum(daly[:, :n] * self.health_discount[:n][None, :], axis=1)
                d_deaths = np.sum(deaths[:, :n] * self.health_discount[:n][None, :], axis=1)
                undisc_daly = np.sum(daly[:, :n], axis=1)
                undisc_inc = np.sum(incidence[:, :n], axis=1)
                p_cost = np.nansum(programme_cost[:, :n] * self.cost_discount[:n][None, :], axis=1)
                p_cost[np.isnan(programme_cost[:, :n]).all(axis=1)] = np.nan
                med_save = np.sum(medical_savings[:, :n] * self.cost_discount[:n][None, :], axis=1)
                payer_save = med_save * payer_share
                partial_net = p_cost - payer_save
                for si, sid in enumerate(self.scenarios):
                    row = {
                        "draw_id": draw_id,
                        "batch_id": int(batch_id),
                        "horizon_years": horizon,
                        "end_year": 2025 + horizon - 1,
                        "scenario_id": sid,
                        "discounted_dalys_averted": float(d_daly[si]),
                        "undiscounted_dalys_averted": float(undisc_daly[si]),
                        "discounted_deaths_averted": float(d_deaths[si]),
                        "undiscounted_incidence_averted": float(undisc_inc[si]),
                        "discounted_programme_cost_2025_cny": float(p_cost[si]) if np.isfinite(p_cost[si]) else np.nan,
                        "discounted_partial_direct_medical_savings_2025_cny": float(med_save[si]),
                        "public_payer_share": payer_share,
                        "discounted_partial_public_payer_savings_2025_cny": float(payer_save[si]),
                        "discounted_partial_public_payer_net_cost_2025_cny": float(partial_net[si]) if np.isfinite(partial_net[si]) else np.nan,
                        "frontier_eligible": sid in FRONTIER_SCENARIOS,
                        "formal_horizon_ready": horizon in {5, 10},
                        "result_status": "FORMAL_PSA" if formal_run else "SMOKE_ONLY_NOT_FORMAL_PSA",
                        "d4_coverage_status": "PARTIAL",
                        "d5_status": "INTERIM_NATIONAL_BRIDGE",
                        "d9_status": "FORMAL_PARENT" if horizon in {5, 10} else "INTERIM_LONG_TERM",
                    }
                    row["programme_only_icer_cny_per_daly"] = row["discounted_programme_cost_2025_cny"] / row["discounted_dalys_averted"] if np.isfinite(row["discounted_programme_cost_2025_cny"]) and row["discounted_dalys_averted"] > 0 else np.nan
                    row["partial_payer_icer_cny_per_daly"] = row["discounted_partial_public_payer_net_cost_2025_cny"] / row["discounted_dalys_averted"] if np.isfinite(row["discounted_partial_public_payer_net_cost_2025_cny"]) and row["discounted_dalys_averted"] > 0 else np.nan
                    for wtp in WTP_VALUES:
                        tag = int(wtp)
                        row[f"nmb_programme_only_wtp_{tag}"] = row["discounted_dalys_averted"] * wtp - row["discounted_programme_cost_2025_cny"] if np.isfinite(row["discounted_programme_cost_2025_cny"]) else np.nan
                        row[f"nmb_partial_payer_wtp_{tag}"] = row["discounted_dalys_averted"] * wtp - row["discounted_partial_public_payer_net_cost_2025_cny"] if np.isfinite(row["discounted_partial_public_payer_net_cost_2025_cny"]) else np.nan
                    cea_rows.append(row)

            audit = {
                "draw_id": draw_id,
                "batch_id": int(batch_id),
                "s0_trend_rate": s0_trend,
                "public_payer_share": payer_share,
                "max_pa_probability_sum_error": max_pa_error,
                "gbd_total_daly_averted_s6_2025": float(daly[self.scenario_index["S6"], 0]),
                "gbd_total_daly_averted_s6_2050": float(daly[self.scenario_index["S6"], -1]),
                "burden_baseline_multiplier_mean": burden_audit["baseline_multiplier_mean"],
                "burden_raw_slope_outside_cap_fraction": burden_audit["raw_slope_outside_cap_fraction"],
                "incidence_baseline_multiplier_mean": incidence_audit["baseline_multiplier_mean"],
                "incidence_raw_slope_outside_cap_fraction": incidence_audit["raw_slope_outside_cap_fraction"],
            }
            for ci, component in enumerate(self.components):
                audit[f"rr_low_{component}"] = float(rr_draw[ci, 0])
            for si, sid in enumerate(self.scenarios):
                audit[f"theta_{sid}"] = float(theta_draw[si])
            audit.update(cost_audit)
            audit.update(d4_audit)
            audit_rows.append(audit)

        cea = pd.DataFrame(cea_rows)
        audit = pd.DataFrame(audit_rows)
        cea.to_csv(output_dir / "01_joint_PSA_draws.csv.gz", index=False, encoding="utf-8-sig", compression="gzip")
        audit.to_csv(output_dir / "01B_draw_audit.csv.gz", index=False, encoding="utf-8-sig", compression="gzip")
        elapsed = time.perf_counter() - start
        qc = {
            "status": "PASS",
            "run_type": "FORMAL_BATCH" if formal_run else "SMOKE",
            "formal_psa_run": bool(formal_run),
            "batch_id": int(batch_id),
            "draws_requested": int(draws),
            "draws_completed": int(audit["draw_id"].nunique()),
            "draw_id_min": int(audit["draw_id"].min()),
            "draw_id_max": int(audit["draw_id"].max()),
            "cea_rows": int(len(cea)),
            "elapsed_seconds": elapsed,
            "daly_identity": "DALY=YLL+YLD enforced",
            "three_level_pa": True,
            "max_pa_probability_sum_error": float(audit["max_pa_probability_sum_error"].max()),
            "gbd_input_status": "GBD_2010_2023_FINAL_HISTORY_LOCKED",
            "d4_status": "PARTIAL",
            "d5_status": "INTERIM_NATIONAL_BRIDGE",
            "d9_26y_status": "INTERIM_STRUCTURAL_SENSITIVITY",
        }
        pd.DataFrame([qc]).to_csv(output_dir / "00_QC.csv", index=False, encoding="utf-8-sig")
        (output_dir / "run_manifest.json").write_text(json.dumps(qc, ensure_ascii=False, indent=2), encoding="utf-8")
        return qc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="ALLdis D1-D10 joint PSA batch runner v1.3 (v1.2-compatible file interface)")
    parser.add_argument("--draws", type=int, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--batch-id", type=int, required=True)
    parser.add_argument("--draw-offset", type=int, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--formal-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    engine = JointPSAEngine()
    qc = engine.run_batch(args.draws, args.seed, args.batch_id, args.draw_offset, args.output_dir, formal_run=args.formal_run)
    print(json.dumps(qc, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
