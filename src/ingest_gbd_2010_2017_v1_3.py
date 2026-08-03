from __future__ import annotations

import hashlib
import json
import math
import shutil
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "input"
AUDIT = ROOT / "audit_gbd_update"
RAW_DEST = INPUT / "gbd_raw_2010_2017"

WPP_URL = (
    "https://population.un.org/wpp/assets/Excel%20Files/"
    "1_Indicator%20(Standard)/CSV_FILES/"
    "WPP2024_PopulationByAge5GroupSex_Medium.csv.gz"
)

AGE_GROUPS = [
    "20-24",
    "25-29",
    "30-34",
    "35-39",
    "40-44",
    "45-49",
    "50-54",
    "55-59",
    "60-64",
    "65-69",
    "70+",
]
GBD_OLDER_AGES = {
    "70-74 years",
    "75-79 years",
    "80-84 years",
    "85-89 years",
    "90-94 years",
    "95+ years",
}
WPP_OLDER_AGES = {
    "70-74",
    "75-79",
    "80-84",
    "85-89",
    "90-94",
    "95-99",
    "100+",
}
EXPECTED_CAUSES = {
    "Alzheimer's disease and other dementias",
    "Bladder cancer",
    "Breast cancer",
    "Colon and rectum cancer",
    "Depressive disorders",
    "Diabetes mellitus type 2",
    "Esophageal cancer",
    "Intracerebral hemorrhage",
    "Ischemic heart disease",
    "Ischemic stroke",
    "Kidney cancer",
    "Stomach cancer",
    "Subarachnoid hemorrhage",
    "Uterine cancer",
}
BURDEN_MEASURES = {
    "Deaths",
    "YLLs (Years of Life Lost)",
    "YLDs (Years Lived with Disability)",
    "DALYs (Disability-Adjusted Life Years)",
}
CASE_MEASURES = {"Incidence", "Prevalence"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_gbd_zip(path: Path) -> pd.DataFrame:
    with zipfile.ZipFile(path) as archive:
        csv_names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if len(csv_names) != 1:
            raise ValueError(f"{path.name}: expected one CSV, found {csv_names}")
        with archive.open(csv_names[0]) as handle:
            out = pd.read_csv(handle)
    out["source_file"] = path.name
    return out


def aggregate_gbd_ages(df: pd.DataFrame) -> pd.DataFrame:
    keep = df.loc[~df["age_name"].isin(GBD_OLDER_AGES)].copy()
    older = df.loc[df["age_name"].isin(GBD_OLDER_AGES)].copy()
    if older.empty:
        raise ValueError("No 70+ component ages found in the GBD files")
    group_cols = [
        col
        for col in df.columns
        if col not in {"age_id", "age_name", "val", "lower", "upper"}
    ]
    older = (
        older.groupby(group_cols, dropna=False, as_index=False)[["val", "lower", "upper"]]
        .sum(min_count=1)
    )
    older["age_id"] = 26
    older["age_name"] = "70+ years"
    columns = list(df.columns)
    return pd.concat([keep[columns], older[columns]], ignore_index=True)


def add_mapping(df: pd.DataFrame, old_burden: pd.DataFrame, old_cases: pd.DataFrame) -> pd.DataFrame:
    mapping_cols = [
        "cause_id",
        "cause_name",
        "sex_name",
        "lancet_outcome_id",
        "lancet_outcome_name",
        "mapping_status",
        "model_sex_use",
    ]
    mapping = (
        pd.concat([old_burden[mapping_cols], old_cases[mapping_cols]], ignore_index=True)
        .drop_duplicates()
    )
    if mapping.duplicated(["cause_id", "cause_name", "sex_name"]).any():
        raise ValueError("Existing standardized GBD mapping is not unique")
    out = df.merge(
        mapping,
        on=["cause_id", "cause_name", "sex_name"],
        how="left",
        validate="many_to_one",
    )
    if out["lancet_outcome_id"].isna().any():
        missing = sorted(out.loc[out["lancet_outcome_id"].isna(), "cause_name"].unique())
        raise ValueError(f"Missing disease mappings: {missing}")
    out["uncertainty_note"] = np.where(
        out["age_name"].eq("70+ years"),
        "70+ constructed by summing GBD 70-74 through 95+; lower/upper summed component-wise",
        "",
    )
    return out


def build_wpp_history(existing_history: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    raw = pd.read_csv(WPP_URL, compression="gzip", low_memory=False)
    raw = raw.loc[
        raw["LocID"].eq(156)
        & raw["Variant"].eq("Medium")
        & raw["Time"].between(2010, 2023)
        & raw["AgeGrp"].isin(set(AGE_GROUPS[:-1]) | WPP_OLDER_AGES)
    ].copy()
    if raw.empty:
        raise ValueError("China was not found in the official WPP 2024 file")
    rows: list[dict[str, object]] = []
    for year in range(2010, 2024):
        year_rows = raw.loc[raw["Time"].eq(year)]
        for sex, value_col in [("Female", "PopFemale"), ("Male", "PopMale")]:
            for age_group in AGE_GROUPS:
                selected = WPP_OLDER_AGES if age_group == "70+" else {age_group}
                population = float(year_rows.loc[year_rows["AgeGrp"].isin(selected), value_col].sum()) * 1000.0
                rows.append(
                    {
                        "year": year,
                        "sex": sex,
                        "age_group": age_group,
                        "population": population,
                        "source": "United Nations, DESA, Population Division, World Population Prospects 2024",
                        "variant": "Historical estimate",
                        "unit": "persons",
                        "time_reference": "mid-year (1 July)",
                        "age_aggregation": "official 5-year groups; 70+ sums 70-74 through 100+",
                        "source_dataset": "WPP2024_PopulationByAge5GroupSex_Medium.csv.gz",
                        "source_url": WPP_URL,
                    }
                )
    out = pd.DataFrame(rows)
    expected = 14 * 2 * len(AGE_GROUPS)
    if len(out) != expected or out["population"].le(0).any():
        raise AssertionError(f"WPP output invalid: rows={len(out)}, expected={expected}")
    keys = ["year", "sex", "age_group"]
    overlap = existing_history.loc[
        existing_history["year"].between(2018, 2023), keys + ["population"]
    ].merge(
        out[keys + ["population"]], on=keys, suffixes=("_old", "_official")
    )
    overlap["absolute_difference_persons"] = (
        overlap["population_official"] - overlap["population_old"]
    ).abs()
    overlap["relative_difference"] = (
        overlap["absolute_difference_persons"] / overlap["population_old"]
    )
    return out.sort_values(keys).reset_index(drop=True), overlap


def verify_splice(combined: pd.DataFrame, population: pd.DataFrame, domain: str) -> pd.DataFrame:
    df = combined.copy()
    female_only = df["lancet_outcome_id"].isin(["breast_cancer", "endometrial_cancer"])
    df = df.loc[~female_only | df["sex_name"].eq("Female")].copy()
    df["age_group"] = df["age_name"].str.replace(" years", "", regex=False)
    df["sex"] = df["sex_name"]
    df = df.merge(
        population[["year", "sex", "age_group", "population"]],
        on=["year", "sex", "age_group"],
        validate="many_to_one",
    )
    df["rate"] = df["val"] / df["population"]
    keys = ["lancet_outcome_id", "cause_id", "cause_name", "sex", "age_group", "measure_name"]
    a = df.loc[df["year"].eq(2017), keys + ["rate"]].rename(columns={"rate": "rate_2017"})
    b = df.loc[df["year"].eq(2018), keys + ["rate"]].rename(columns={"rate": "rate_2018"})
    out = a.merge(b, on=keys, how="outer", indicator=True)
    out["log_rate_change_2017_2018"] = np.log(out["rate_2018"] / out["rate_2017"])
    out.insert(0, "value_domain", domain)
    return out


def update_provenance(zip_paths: list[Path], burden_path: Path, cases_path: Path, population_path: Path) -> None:
    provenance_path = INPUT / "INPUT_PROVENANCE.json"
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    provenance.update(
        {
            "bundle_version": "v1.3",
            "current_gbd_window": "2010-2023",
            "current_gbd_source": "user-supplied IHME GBD 2023 ZIPs for 2010-2017 plus parent database v1 for 2018-2023",
            "formal_psa_included": False,
            "formal_psa_status": "READY_FOR_USER_LOCAL_RUN_AFTER_V1_3_SMOKE_QC",
            "wpp_history_source": WPP_URL,
            "gbd_raw_zip_sha256": {path.name: sha256(path) for path in zip_paths},
        }
    )
    tracked = {
        burden_path.relative_to(ROOT).as_posix(),
        cases_path.relative_to(ROOT).as_posix(),
        population_path.relative_to(ROOT).as_posix(),
    }
    provenance["input_files"] = [
        item for item in provenance.get("input_files", []) if item["relative_path"] not in tracked
    ]
    for path in [burden_path, cases_path, population_path, *[RAW_DEST / p.name for p in zip_paths]]:
        provenance["input_files"].append(
            {
                "relative_path": path.relative_to(ROOT).as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )
    provenance_path.write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8")


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        raise SystemExit("usage: ingest_gbd_2010_2017_v1_3.py ZIP_A ZIP_B ZIP_C")
    zip_paths = [Path(value).resolve() for value in argv[1:]]
    for path in zip_paths:
        if not path.exists():
            raise FileNotFoundError(path)

    AUDIT.mkdir(parents=True, exist_ok=True)
    RAW_DEST.mkdir(parents=True, exist_ok=True)
    for path in zip_paths:
        shutil.copy2(path, RAW_DEST / path.name)

    gbd_new = pd.concat([load_gbd_zip(path) for path in zip_paths], ignore_index=True)
    if set(gbd_new["year"].unique()) != set(range(2010, 2018)):
        raise ValueError("GBD years are not exactly 2010-2017")
    if set(gbd_new["cause_name"].unique()) != EXPECTED_CAUSES:
        raise ValueError("GBD cause set differs from the locked request")
    if set(gbd_new["metric_name"].unique()) != {"Number"}:
        raise ValueError("GBD metric must be Number")
    if not ((gbd_new["lower"] <= gbd_new["val"]) & (gbd_new["val"] <= gbd_new["upper"])).all():
        raise ValueError("GBD lower/val/upper ordering failed")

    burden_path = INPUT / "gbd_standardized" / "GBD_burden_components.csv.gz"
    cases_path = INPUT / "gbd_standardized" / "GBD_cases_components.csv.gz"
    old_burden = pd.read_csv(burden_path, encoding="utf-8-sig")
    old_cases = pd.read_csv(cases_path, encoding="utf-8-sig")
    old_burden = old_burden.loc[pd.to_numeric(old_burden["year"]).ge(2018)].copy()
    old_cases = old_cases.loc[pd.to_numeric(old_cases["year"]).ge(2018)].copy()

    aggregated = aggregate_gbd_ages(gbd_new)
    mapped = add_mapping(aggregated, old_burden, old_cases)
    columns = list(old_burden.columns)
    new_burden = mapped.loc[mapped["measure_name"].isin(BURDEN_MEASURES), columns].copy()
    new_cases = mapped.loc[mapped["measure_name"].isin(CASE_MEASURES), columns].copy()
    combined_burden = pd.concat([new_burden, old_burden], ignore_index=True)
    combined_cases = pd.concat([new_cases, old_cases], ignore_index=True)
    key = ["location_name", "sex_name", "age_name", "cause_name", "measure_name", "metric_name", "year"]
    if combined_burden.duplicated(key).any() or combined_cases.duplicated(key).any():
        raise ValueError("Duplicate GBD keys after 2010-2023 splice")
    combined_burden = combined_burden.sort_values(["year", "cause_id", "measure_id", "sex_id", "age_id"])
    combined_cases = combined_cases.sort_values(["year", "cause_id", "measure_id", "sex_id", "age_id"])
    combined_burden.to_csv(burden_path, index=False, encoding="utf-8-sig", compression="gzip")
    combined_cases.to_csv(cases_path, index=False, encoding="utf-8-sig", compression="gzip")

    population_path = INPUT / "population" / "WPP2024_China_age_sex_history.csv"
    old_population = pd.read_csv(population_path, encoding="utf-8-sig")
    population, population_overlap = build_wpp_history(old_population)
    population.to_csv(population_path, index=False, encoding="utf-8-sig")

    splice_burden = verify_splice(combined_burden, population, "burden")
    splice_cases = verify_splice(combined_cases, population, "cases")
    population_overlap.to_csv(AUDIT / "01_WPP2018_2023重叠核对.csv", index=False, encoding="utf-8-sig")
    splice_burden.to_csv(AUDIT / "02_GBD负担2017_2018拼接核对.csv", index=False, encoding="utf-8-sig")
    splice_cases.to_csv(AUDIT / "03_GBD病例2017_2018拼接核对.csv", index=False, encoding="utf-8-sig")

    qc_rows = [
        ["GBD_ZIP_COUNT", len(zip_paths) == 3, len(zip_paths), 3],
        ["GBD_YEARS", set(gbd_new["year"].unique()) == set(range(2010, 2018)), "2010-2017", "2010-2017"],
        ["GBD_CAUSES", set(gbd_new["cause_name"].unique()) == EXPECTED_CAUSES, gbd_new["cause_name"].nunique(), len(EXPECTED_CAUSES)],
        ["GBD_NUMBER_ONLY", set(gbd_new["metric_name"].unique()) == {"Number"}, ",".join(sorted(gbd_new["metric_name"].unique())), "Number"],
        ["GBD_NO_DUPLICATES", not gbd_new.duplicated(key).any(), int(gbd_new.duplicated(key).sum()), 0],
        ["GBD_INTERVAL_ORDER", bool(((gbd_new["lower"] <= gbd_new["val"]) & (gbd_new["val"] <= gbd_new["upper"])).all()), True, True],
        ["GBD_COMBINED_BURDEN_YEARS", combined_burden["year"].nunique() == 14, combined_burden["year"].nunique(), 14],
        ["GBD_COMBINED_CASES_YEARS", combined_cases["year"].nunique() == 14, combined_cases["year"].nunique(), 14],
        ["WPP_ROWS", len(population) == 308, len(population), 308],
        ["WPP_POSITIVE", bool(population["population"].gt(0).all()), True, True],
        ["WPP_OVERLAP_MAX_REL_DIFF", float(population_overlap["relative_difference"].max()) < 1e-4, float(population_overlap["relative_difference"].max()), "<0.0001"],
        ["SPLICE_BURDEN_MATCHED", bool(splice_burden["_merge"].eq("both").all()), int(splice_burden["_merge"].eq("both").sum()), len(splice_burden)],
        ["SPLICE_CASES_MATCHED", bool(splice_cases["_merge"].eq("both").all()), int(splice_cases["_merge"].eq("both").sum()), len(splice_cases)],
    ]
    qc = pd.DataFrame(qc_rows, columns=["check_id", "passed", "observed", "expected"])
    qc["status"] = np.where(qc["passed"], "PASS", "FAIL")
    qc.to_csv(AUDIT / "00_GBD更新QC.csv", index=False, encoding="utf-8-sig")
    if not qc["passed"].all():
        raise AssertionError(qc.loc[~qc["passed"]].to_dict(orient="records"))

    update_provenance(zip_paths, burden_path, cases_path, population_path)
    summary = {
        "version": "v1.3",
        "gbd_new_rows_raw": int(len(gbd_new)),
        "gbd_burden_rows_2010_2023": int(len(combined_burden)),
        "gbd_cases_rows_2010_2023": int(len(combined_cases)),
        "wpp_rows_2010_2023": int(len(population)),
        "wpp_overlap_max_absolute_difference_persons": float(population_overlap["absolute_difference_persons"].max()),
        "wpp_overlap_max_relative_difference": float(population_overlap["relative_difference"].max()),
        "burden_splice_median_abs_log_rate_change": float(splice_burden["log_rate_change_2017_2018"].abs().median()),
        "cases_splice_median_abs_log_rate_change": float(splice_cases["log_rate_change_2017_2018"].abs().median()),
        "all_qc_passed": bool(qc["passed"].all()),
    }
    (AUDIT / "GBD_UPDATE_SUMMARY.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
