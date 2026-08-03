from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
WTP_VALUES = [50000, 100000, 150000]
PERSPECTIVES = {
    "PROGRAMME_ONLY": "nmb_programme_only_wtp_{wtp}",
    "PARTIAL_PUBLIC_PAYER": "nmb_partial_payer_wtp_{wtp}",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-root", type=Path, default=ROOT / "psa_smoke")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "psa_smoke" / "merged")
    parser.add_argument("--formal", action="store_true")
    return parser.parse_args()


def summarize(draws: pd.DataFrame) -> pd.DataFrame:
    metrics = [
        "discounted_dalys_averted",
        "undiscounted_dalys_averted",
        "discounted_deaths_averted",
        "undiscounted_incidence_averted",
        "discounted_programme_cost_2025_cny",
        "discounted_partial_direct_medical_savings_2025_cny",
        "discounted_partial_public_payer_net_cost_2025_cny",
        "programme_only_icer_cny_per_daly",
        "partial_payer_icer_cny_per_daly",
    ]
    rows = []
    for (horizon, sid), g in draws.groupby(["horizon_years", "scenario_id"], sort=False):
        for metric in metrics:
            x = pd.to_numeric(g[metric], errors="coerce").dropna()
            if x.empty:
                continue
            rows.append({
                "horizon_years": int(horizon),
                "scenario_id": sid,
                "metric": metric,
                "n_draws": int(len(x)),
                "mean": float(x.mean()),
                "sd": float(x.std(ddof=1)),
                "p2_5": float(x.quantile(0.025)),
                "median": float(x.quantile(0.5)),
                "p97_5": float(x.quantile(0.975)),
                "result_status": "FORMAL" if str(g["result_status"].iloc[0]).startswith("FORMAL") else "SMOKE_ONLY_NOT_FORMAL_PSA",
            })
    return pd.DataFrame(rows)


def build_ceac(draws: pd.DataFrame, formal: bool) -> tuple[pd.DataFrame, pd.DataFrame]:
    eligible = draws.loc[draws["frontier_eligible"].astype(bool)].copy()
    ceac_rows = []
    ceaf_rows = []
    for horizon in sorted(eligible["horizon_years"].unique()):
        h = eligible.loc[eligible["horizon_years"].eq(horizon)].copy()
        for perspective, pattern in PERSPECTIVES.items():
            for wtp in WTP_VALUES:
                col = pattern.format(wtp=wtp)
                pivot = h.pivot(index="draw_id", columns="scenario_id", values=col)
                best = pivot.idxmax(axis=1)
                expected = pivot.mean(axis=0)
                ceaf_sid = str(expected.idxmax())
                for sid in sorted(pivot.columns):
                    ceac_rows.append({
                        "horizon_years": int(horizon),
                        "perspective": perspective,
                        "wtp_cny_per_daly": int(wtp),
                        "scenario_id": sid,
                        "probability_cost_effective": float((best == sid).mean()),
                        "expected_nmb_2025_cny": float(expected[sid]),
                        "n_draws": int(len(best)),
                        "result_status": "FORMAL_PSA" if formal else "SMOKE_ONLY_NOT_FORMAL_PSA",
                    })
                ceaf_rows.append({
                    "horizon_years": int(horizon),
                    "perspective": perspective,
                    "wtp_cny_per_daly": int(wtp),
                    "ceaf_scenario_id": ceaf_sid,
                    "ceaf_probability": float((best == ceaf_sid).mean()),
                    "maximum_expected_nmb_2025_cny": float(expected[ceaf_sid]),
                    "n_draws": int(len(best)),
                    "result_status": "FORMAL_PSA" if formal else "SMOKE_ONLY_NOT_FORMAL_PSA",
                })
    return pd.DataFrame(ceac_rows), pd.DataFrame(ceaf_rows)


def batch_stability(draws: pd.DataFrame) -> pd.DataFrame:
    metrics = ["discounted_dalys_averted", "discounted_programme_cost_2025_cny", "discounted_partial_public_payer_net_cost_2025_cny"]
    focus = draws.loc[draws["scenario_id"].eq("S6") & draws["horizon_years"].isin([5, 10])].copy()
    rows = []
    for horizon in [5, 10]:
        g = focus.loc[focus["horizon_years"].eq(horizon)]
        for metric in metrics:
            overall = float(g[metric].mean())
            for batch, bg in g.groupby("batch_id"):
                value = float(bg[metric].mean())
                rows.append({
                    "horizon_years": horizon,
                    "scenario_id": "S6",
                    "metric": metric,
                    "batch_id": int(batch),
                    "batch_mean": value,
                    "overall_mean": overall,
                    "relative_difference": (value - overall) / overall if overall != 0 else np.nan,
                    "n_draws": int(bg["draw_id"].nunique()),
                })
    return pd.DataFrame(rows)


def deterministic_reconciliation(draws: pd.DataFrame) -> pd.DataFrame:
    det = pd.read_csv(ROOT / "results" / "05_primary_horizon_summary.csv", encoding="utf-8-sig")
    focus = draws.loc[draws["scenario_id"].eq("S6")].copy()
    rows = []
    mapping = {
        "discounted_dalys_averted": "discounted_dalys_averted",
        "undiscounted_incidence_averted": "cumulative_avoided_incidence",
        "discounted_programme_cost_2025_cny": "discounted_programme_cost_2025_cny",
    }
    for horizon in [5, 10, 26]:
        drow = det.loc[det["scenario_id"].eq("S6") & det["horizon_years"].eq(horizon)].iloc[0]
        g = focus.loc[focus["horizon_years"].eq(horizon)]
        for psa_col, det_col in mapping.items():
            psa_mean = float(g[psa_col].mean())
            deterministic = float(drow[det_col])
            rows.append({
                "horizon_years": horizon,
                "scenario_id": "S6",
                "metric": psa_col,
                "psa_smoke_mean": psa_mean,
                "deterministic_value": deterministic,
                "mean_to_deterministic_ratio": psa_mean / deterministic if deterministic else np.nan,
                "relative_difference": (psa_mean - deterministic) / deterministic if deterministic else np.nan,
                "tolerance": 0.15,
                "qc_status": "PASS" if deterministic and abs(psa_mean / deterministic - 1.0) <= 0.15 else "FAIL",
            })
    return pd.DataFrame(rows)


def convergence(draws: pd.DataFrame, formal: bool) -> pd.DataFrame:
    focus = draws.loc[draws["scenario_id"].eq("S6") & draws["horizon_years"].eq(10)].sort_values("draw_id")
    checkpoints = [25, 50, 100, 150, 200]
    if formal:
        checkpoints += [500, 1000, 2000, 5000, 10000]
    checkpoints = [x for x in checkpoints if x <= len(focus)]
    rows = []
    metrics = ["discounted_dalys_averted", "discounted_programme_cost_2025_cny", "discounted_partial_public_payer_net_cost_2025_cny"]
    for n in checkpoints:
        g = focus.iloc[:n]
        for metric in metrics:
            mean = float(g[metric].mean())
            sd = float(g[metric].std(ddof=1))
            rows.append({
                "checkpoint_draws": n,
                "scenario_id": "S6",
                "horizon_years": 10,
                "metric": metric,
                "cumulative_mean": mean,
                "cumulative_sd": sd,
                "standard_error": sd / np.sqrt(n),
                "relative_standard_error": (sd / np.sqrt(n)) / abs(mean) if mean else np.nan,
            })
    return pd.DataFrame(rows)


def build_qc(draws: pd.DataFrame, batch_qc: pd.DataFrame, recon: pd.DataFrame, stability: pd.DataFrame, formal: bool) -> pd.DataFrame:
    expected_draws = int(batch_qc["draws_requested"].sum())
    expected_rows = expected_draws * 8 * 3
    checks = []

    def add(check_id: str, condition: bool, observed: object, expected: object, note: str = "") -> None:
        checks.append({"check_id": check_id, "status": "PASS" if condition else "FAIL", "observed": observed, "expected": expected, "note": note})

    add("DRAW_COUNT", draws["draw_id"].nunique() == expected_draws, int(draws["draw_id"].nunique()), expected_draws)
    add("DRAW_ID_UNIQUE_ACROSS_BATCHES", draws[["draw_id", "batch_id"]].drop_duplicates()["draw_id"].is_unique, int(draws[["draw_id", "batch_id"]].drop_duplicates()["draw_id"].nunique()), expected_draws)
    add("CEA_ROW_COUNT", len(draws) == expected_rows, len(draws), expected_rows)
    add("SCENARIO_COUNT", draws["scenario_id"].nunique() == 8, int(draws["scenario_id"].nunique()), 8)
    add("HORIZON_SET", set(draws["horizon_years"].unique()) == {5, 10, 26}, sorted(draws["horizon_years"].unique()), [5, 10, 26])
    add("S0_HEALTH_ZERO", np.allclose(draws.loc[draws["scenario_id"].eq("S0"), "discounted_dalys_averted"], 0.0), float(draws.loc[draws["scenario_id"].eq("S0"), "discounted_dalys_averted"].abs().max()), 0)
    add("S0_COST_ZERO", np.allclose(draws.loc[draws["scenario_id"].eq("S0"), "discounted_programme_cost_2025_cny"], 0.0), float(draws.loc[draws["scenario_id"].eq("S0"), "discounted_programme_cost_2025_cny"].abs().max()), 0)
    add("S7_COST_MISSING", draws.loc[draws["scenario_id"].eq("S7"), "discounted_programme_cost_2025_cny"].isna().all(), int(draws.loc[draws["scenario_id"].eq("S7"), "discounted_programme_cost_2025_cny"].notna().sum()), 0)
    add("ELIGIBLE_HEALTH_COMPLETE", draws.loc[draws["scenario_id"].isin([f"S{i}" for i in range(7)]), "discounted_dalys_averted"].notna().all(), int(draws.loc[draws["scenario_id"].isin([f"S{i}" for i in range(7)]), "discounted_dalys_averted"].isna().sum()), 0)
    add("ELIGIBLE_COST_COMPLETE", draws.loc[draws["scenario_id"].isin([f"S{i}" for i in range(7)]), "discounted_programme_cost_2025_cny"].notna().all(), int(draws.loc[draws["scenario_id"].isin([f"S{i}" for i in range(7)]), "discounted_programme_cost_2025_cny"].isna().sum()), 0)
    add("PAYER_SHARE_RANGE", draws["public_payer_share"].between(0, 1).all(), [float(draws["public_payer_share"].min()), float(draws["public_payer_share"].max())], "[0,1]")
    add("D4_SAVINGS_NONNEGATIVE", (draws["discounted_partial_direct_medical_savings_2025_cny"] >= -1e-8).all(), float(draws["discounted_partial_direct_medical_savings_2025_cny"].min()), ">=0")
    add("DETERMINISTIC_RECONCILIATION", recon["qc_status"].eq("PASS").all(), int(recon["qc_status"].eq("PASS").sum()), len(recon), "15% smoke-mean tolerance")
    add("BATCH_STABILITY", stability["relative_difference"].abs().max() <= 0.15, float(stability["relative_difference"].abs().max()), "<=0.15")
    add("BATCH_QC_PASS", batch_qc["status"].eq("PASS").all(), int(batch_qc["status"].eq("PASS").sum()), len(batch_qc))
    add("PA_PROBABILITY", float(batch_qc["max_pa_probability_sum_error"].max()) < 1e-12, float(batch_qc["max_pa_probability_sum_error"].max()), "<1e-12")
    add("D4_BOUNDARY", draws["d4_coverage_status"].eq("PARTIAL").all(), draws["d4_coverage_status"].unique().tolist(), ["PARTIAL"])
    add("D5_BOUNDARY", draws["d5_status"].eq("INTERIM_NATIONAL_BRIDGE").all(), draws["d5_status"].unique().tolist(), ["INTERIM_NATIONAL_BRIDGE"])
    add("D9_LONG_BOUNDARY", draws.loc[draws["horizon_years"].eq(26), "d9_status"].eq("INTERIM_LONG_TERM").all(), draws.loc[draws["horizon_years"].eq(26), "d9_status"].unique().tolist(), ["INTERIM_LONG_TERM"])
    add("FORMAL_RUN_FLAG", formal == draws["result_status"].astype(str).str.startswith("FORMAL").all(), bool(formal), bool(draws["result_status"].astype(str).str.startswith("FORMAL").all()))
    return pd.DataFrame(checks)


def main() -> None:
    args = parse_args()
    files = sorted(args.input_root.glob("batch_*/01_joint_PSA_draws.csv.gz"))
    if not files:
        raise FileNotFoundError(f"No PSA batch files found under {args.input_root}")
    draws = pd.concat([pd.read_csv(p, encoding="utf-8-sig") for p in files], ignore_index=True)
    qc_files = sorted(args.input_root.glob("batch_*/00_QC.csv"))
    batch_qc = pd.concat([pd.read_csv(p, encoding="utf-8-sig") for p in qc_files], ignore_index=True)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    summary = summarize(draws)
    ceac, ceaf = build_ceac(draws, args.formal)
    stability = batch_stability(draws)
    recon = deterministic_reconciliation(draws)
    conv = convergence(draws, args.formal)
    qc = build_qc(draws, batch_qc, recon, stability, args.formal)
    draws.to_csv(args.output_dir / "01_joint_PSA_draws_merged.csv.gz", index=False, encoding="utf-8-sig", compression="gzip")
    summary.to_csv(args.output_dir / "02_PSA_summary.csv", index=False, encoding="utf-8-sig")
    ceac.to_csv(args.output_dir / "03_CEAC.csv", index=False, encoding="utf-8-sig")
    ceaf.to_csv(args.output_dir / "04_CEAF.csv", index=False, encoding="utf-8-sig")
    stability.to_csv(args.output_dir / "05_batch_stability.csv", index=False, encoding="utf-8-sig")
    recon.to_csv(args.output_dir / "06_deterministic_reconciliation.csv", index=False, encoding="utf-8-sig")
    conv.to_csv(args.output_dir / "07_convergence_smoke.csv", index=False, encoding="utf-8-sig")
    qc.to_csv(args.output_dir / "00_QC.csv", index=False, encoding="utf-8-sig")
    manifest = {
        "status": "PASS" if qc["status"].eq("PASS").all() else "FAIL",
        "formal_psa_run": bool(args.formal),
        "draws": int(draws["draw_id"].nunique()),
        "batches": int(draws["batch_id"].nunique()),
        "cea_rows": int(len(draws)),
        "qc_pass": int(qc["status"].eq("PASS").sum()),
        "qc_total": int(len(qc)),
        "interpretation": "Technical smoke test only; do not report probabilistic intervals as formal results" if not args.formal else "Formal run",
    }
    (args.output_dir / "MERGED_MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
