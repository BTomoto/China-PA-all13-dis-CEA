"""Reproducible IHD and ischemic-stroke incidence PIF pilot."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import shutil
import zipfile
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
R2 = ROOT / "new_study" / "round2_20261112" / "registers"
R2A = ROOT / "new_study" / "round2_audit_fix_20261112" / "registers"
SOURCE_ZIP = ROOT / "new_study" / "round1_20261112" / "handoff" / "continuation" / "source_data" / "gbd" / "IHME-GBD_2023_DATA-85af7c45-1.zip"
EXPECTED_SHA256 = "64e613442f4269bb79ff36e26a7069ad5da36a1abc8de566be58f49c3aa6805e"
RR = {
    "IHD": ("Ischemic heart disease", 493, 1.19474313, 1.128668172, 1.264222503),
    "IS": ("Ischemic stroke", 495, 1.18623962, 1.089324619, 1.283697047),
}
AGES = [f"{x}-{x+4}" for x in range(20, 95, 5)] + ["95+"]
PATH = {2025: 1.00, 2026: .97, 2027: .94, 2028: .91, 2029: .88}


def read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, fields=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields or list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1048576), b""):
            h.update(block)
    return h.hexdigest()


def reduction_factor(year):
    return PATH.get(year, .85)


def pif(p0, p1, rr):
    if not (0 <= p1 <= p0 <= 1 and rr >= 1):
        raise ValueError("Invalid prevalence or RR for beneficial intervention")
    return (p0 - p1) * (rr - 1) / (1 + p0 * (rr - 1))


def scenario_rows():
    pop = read_csv(R2 / "population_input_whitelist_v1.csv")
    exposure = read_csv(R2 / "pa_2025_model_baseline_v1.csv")
    exposure_map = {(r["sex"], r["age_group"]): float(r["p_inactive"]) for r in exposure}
    assert len(exposure_map) == 34
    output = []
    for r in pop:
        year, sex, age = int(r["year"]), r["sex"], r["age_group"]
        p0 = exposure_map[(sex, age)]
        factor = reduction_factor(year)
        n = int(r["population_persons"])
        output.append(dict(year=year, sex=sex, age_group=age, population=n,
                           p_inactive_baseline=p0, p_inactive_intervention=p0*factor,
                           relative_reduction=1-factor,
                           inactive_persons_baseline=n*p0,
                           inactive_persons_intervention=n*p0*factor))
    assert len(output) == 26*34
    return output


def grouped_scenario(rows):
    result = []
    for year in range(2025, 2051):
        for sex in ("Male", "Female"):
            source = [r for r in rows if int(r["year"]) == year and r["sex"] == sex]
            byage = {r["age_group"]: r for r in source}
            assert len(byage) == 17
            for age in AGES:
                selected = [byage[age]] if age != "95+" else [byage["95-99"], byage["100+"]]
                n = sum(int(r["population"]) for r in selected)
                inactive0 = sum(float(r["inactive_persons_baseline"]) for r in selected)
                inactive1 = sum(float(r["inactive_persons_intervention"]) for r in selected)
                result.append(dict(year=year, sex=sex, age_group=age, population=n,
                                   p_inactive_baseline=inactive0/n,
                                   p_inactive_intervention=inactive1/n,
                                   relative_reduction=1-reduction_factor(year),
                                   inactive_persons_baseline=inactive0,
                                   inactive_persons_intervention=inactive1))
    return result


def raw_gbd(zip_path=SOURCE_ZIP):
    if not Path(zip_path).is_file():
        raise FileNotFoundError("BLOCKED_GBD_RATE_INPUT: original GBD ZIP absent")
    if sha256(zip_path) != EXPECTED_SHA256:
        raise ValueError("BLOCKED_GBD_RATE_INPUT: GBD ZIP SHA256 mismatch")
    with zipfile.ZipFile(zip_path) as z:
        names = z.namelist()
        assert len([n for n in names if n.endswith(".csv")]) == 1 and "citation.txt" in names
        csv_name = next(n for n in names if n.endswith(".csv"))
        rows = list(csv.DictReader(io.TextIOWrapper(z.open(csv_name), encoding="utf-8-sig")))
        citation = z.read("citation.txt").decode("utf-8-sig")
    return rows, csv_name, citation


def validated_rates(raw):
    rates, numbers = {}, {}
    selected = [r for r in raw if r["year"] == "2023" and r["cause_name"] in {v[0] for v in RR.values()}
                and r["sex_name"] in ("Male", "Female") and r["measure_name"] == "Incidence"
                and r["age_name"] != "70+ years"]
    expected = 2*2*len(AGES)*2
    if len(selected) != expected:
        raise ValueError(f"BLOCKED_GBD_RATE_INPUT: expected {expected} point/UI rows, found {len(selected)}")
    for r in selected:
        if r["population_group_name"] != "All Population" or r["location_name"] != "China":
            raise ValueError("BLOCKED_GBD_RATE_INPUT: query scope mismatch")
        disease = next(k for k,v in RR.items() if v[0] == r["cause_name"])
        if int(r["cause_id"]) != RR[disease][1]:
            raise ValueError("BLOCKED_GBD_RATE_INPUT: cause ID mismatch")
        age = r["age_name"].replace(" years", "")
        if age not in AGES:
            raise ValueError("BLOCKED_GBD_RATE_INPUT: age mismatch")
        triple = tuple(float(r[k]) for k in ("val", "lower", "upper"))
        if not (0 <= triple[1] <= triple[0] <= triple[2]):
            raise ValueError("BLOCKED_GBD_RATE_INPUT: invalid point/UI")
        key = disease, r["sex_name"], age
        target = rates if r["metric_name"] == "Rate" and r["metric_id"] == "3" else numbers if r["metric_name"] == "Number" and r["metric_id"] == "1" else None
        if target is None or key in target:
            raise ValueError("BLOCKED_GBD_RATE_INPUT: metric or duplicate mismatch")
        target[key] = triple
    if len(rates) != expected//2 or len(numbers) != expected//2:
        raise ValueError("BLOCKED_GBD_RATE_INPUT: incomplete Rate/Number pairs")
    return rates, numbers, selected


def incidence_rows(scenario, rates):
    output = []
    for row in grouped_scenario(scenario):
        y, sex, age = int(row["year"]), row["sex"], row["age_group"]
        for disease in RR:
            rate, low, high = rates[(disease,sex,age)]
            n = int(row["population"])
            p0, p1 = float(row["p_inactive_baseline"]), float(row["p_inactive_intervention"])
            rr = RR[disease][2]
            baseline = n*rate/100000
            effect = pif(p0,p1,rr)
            output.append(dict(year=y, disease=disease, cause_name=RR[disease][0], sex=sex, age_group=age,
                               population=n, baseline_rate_per_100k=rate, baseline_rate_lower=low,
                               baseline_rate_upper=high, baseline_expected_incidence=baseline,
                               p_inactive_baseline=p0, p_inactive_intervention=p1,
                               rr_inactive_vs_low_active=rr, pif=effect,
                               incident_cases_averted=baseline*effect,
                               intervention_expected_incidence=baseline*(1-effect),
                               gbd_rate_year=2023, projection="constant_2023_age_sex_incidence_rate"))
    return output


def summaries(detail):
    groups = defaultdict(lambda: [0.,0.])
    for r in detail:
        y, d = int(r["year"]), r["disease"]
        for key in [("annual",str(y),d), ("cumulative_2025_2030","2025-2030",d),
                    ("cumulative_2025_2034","2025-2034",d), ("cumulative_2025_2050","2025-2050",d)]:
            if key[0] == "annual" or y <= int(key[1][-4:]):
                groups[key][0] += float(r["baseline_expected_incidence"])
                groups[key][1] += float(r["incident_cases_averted"])
    return [dict(period_type=k[0],period=k[1],disease=k[2],baseline_expected_incidence=v[0],
                 incident_cases_averted=v[1]) for k,v in sorted(groups.items())]


def copy_and_describe_raw():
    raw, name, citation = raw_gbd()
    dest = HERE / "raw" / SOURCE_ZIP.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SOURCE_ZIP,dest)
    assert sha256(dest) == EXPECTED_SHA256
    fields = ["year","location_name","population_group_name","sex_name","age_name","cause_name","measure_name","metric_name"]
    metadata = {"original_filename": SOURCE_ZIP.name, "internal_csv_filename": name,
                "sha256": EXPECTED_SHA256, "rows": len(raw), "recovered_date": "2026-11-12",
                "original_download_date": None, "gbd_version": "GBD 2023", "citation": citation.strip(),
                "query_condition_text": "GBD 2023 Results; All Population; China; Male/Female; Ischemic heart disease/Ischemic stroke; Incidence; Number/Rate; ages 20-24 through 90-94, 95+, plus 70+ aggregate; years 1990-2023. Reconstructed from all original CSV rows; original UI screenshot/log unavailable.",
                "unique_values": {k: sorted({r[k] for r in raw}) for k in fields},
                "source_path": str(SOURCE_ZIP.relative_to(ROOT)).replace('\\','/')}
    (HERE / "raw" / "GBD_2023_query_provenance.json").write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return raw


def cost_link_semantics():
    links = read_csv(R2A / "cost_evidence_links_v3.csv")
    for r in links:
        if r["cost_id"] == "DC-DEP-CN-2015":
            assert r["exact_cost_definition_match"] == "FALSE" and r["assignment_allowed"] == "FALSE"
            r["link_type"] = "CANDIDATE_LINK"
    write_csv(HERE / "frozen_cost_link_semantic_fix.csv",links)


def main():
    scenario = scenario_rows()
    write_csv(HERE / "inputs" / "scenario_age_sex_2025_2050.csv",scenario)
    cost_link_semantics()
    raw = copy_and_describe_raw()
    rates, numbers, selected = validated_rates(raw)
    detail = incidence_rows(scenario,rates)
    write_csv(HERE / "results" / "incidence_age_sex_2025_2050.csv",detail)
    write_csv(HERE / "results" / "incidence_summary.csv",summaries(detail))
    return detail

if __name__ == "__main__":
    print(f"pilot_rows={len(main())}")
