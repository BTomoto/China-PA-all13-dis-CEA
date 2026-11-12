"""Annual avoided-incidence cohort model. No burden endpoint is multiplied by PIF.

The model tracks the *difference* between control and intervention. Synthetic
parameters may exercise the software, but are never admitted scientific inputs.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
R3 = ROOT / "new_study" / "round3_health_model_pilot_20261112"
R4 = Path(__file__).resolve().parents[1]
RAW_ZIP = ROOT / "new_study" / "round1_20261112" / "handoff" / "continuation" / "source_data" / "gbd" / "IHME-GBD_2023_DATA-85af7c45-1.zip"
RAW_SHA = "64e613442f4269bb79ff36e26a7069ad5da36a1abc8de566be58f49c3aa6805e"
DISEASES = {"IHD", "IS"}


class InputBlocked(RuntimeError):
    pass


def read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path, rows, fields):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def verify_raw():
    if not RAW_ZIP.is_file():
        raise InputBlocked("BLOCKED_INPUT: GBD 2023 incidence ZIP missing")
    digest = hashlib.sha256(RAW_ZIP.read_bytes()).hexdigest()
    if digest != RAW_SHA:
        raise InputBlocked("BLOCKED_INPUT: GBD 2023 incidence ZIP SHA256 mismatch")
    return digest


def incidence_input():
    verify_raw()
    rows = read_csv(R3 / "results" / "incidence_age_sex_2025_2050.csv")
    if len(rows) != 1664:
        raise InputBlocked("BLOCKED_INPUT: frozen incidence detail count mismatch")
    seen = set()
    for row in rows:
        key = (row["year"], row["disease"], row["sex"], row["age_group"])
        if key in seen or row["disease"] not in DISEASES:
            raise InputBlocked("BLOCKED_INPUT: frozen incidence key mismatch")
        seen.add(key)
        if float(row["incident_cases_averted"]) > float(row["baseline_expected_incidence"]) + 1e-8:
            raise InputBlocked("BLOCKED_INPUT: avoided incidence exceeds control")
    return rows


def pif(p0, p1, rr):
    if not (0 <= p1 <= p0 <= 1 and rr >= 1):
        raise ValueError("invalid RR/exposure comparison")
    return (p0 - p1) * (rr - 1) / (1 + p0 * (rr - 1))


def multicategory_pif(control_shares, intervention_shares, category_risks):
    """Four-category PIF; requires observed, matched age-sex category shares.

    The caller supplies ordered shares for <600, 600-3999, 4000-7999, >=8000.
    No shares are estimated or imputed here.
    """
    if any(x is None for x in (control_shares, intervention_shares, category_risks)):
        raise InputBlocked("BLOCKED_INPUT: age-sex activity-category shares unavailable")
    if not all(len(x) == 4 for x in (control_shares, intervention_shares, category_risks)):
        raise ValueError("four-category shares and RRs required")
    if any(x < 0 for x in (*control_shares, *intervention_shares, *category_risks)):
        raise ValueError("negative category value")
    if not all(math.isclose(sum(x), 1, abs_tol=1e-9) for x in (control_shares, intervention_shares)):
        raise ValueError("category shares must sum to one")
    baseline = sum(p*r for p,r in zip(control_shares, category_risks))
    intervention = sum(p*r for p,r in zip(intervention_shares, category_risks))
    if baseline <= 0:
        raise ValueError("invalid baseline risk")
    return (baseline-intervention)/baseline


@dataclass(frozen=True)
class Transition:
    disease: str
    sex: str
    age_group: str
    duration: int
    disease_death_hazard: float
    other_death_hazard: float
    remission_hazard: float
    recurrence_hazard: float
    disability_weight: float
    standard_remaining_life_years: float
    provenance: str

    def validate(self):
        if self.disease not in DISEASES or self.sex not in {"Male", "Female"}:
            raise ValueError("disease/sex mismatch")
        for name in ("disease_death_hazard", "other_death_hazard", "remission_hazard", "recurrence_hazard"):
            value = getattr(self, name)
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"invalid {name}")
        if not 0 <= self.disability_weight <= 1 or self.standard_remaining_life_years < 0:
            raise ValueError("invalid disability/life-years")


def age_at(initial_age, years):
    floor = 95 if initial_age == "95+" else int(initial_age.split("-")[0])
    current = floor + years
    return "95+" if current >= 95 else f"{20 + 5 * ((current - 20)//5)}-{24 + 5 * ((current - 20)//5)}"


def competing_exits(count, hazards):
    total = sum(hazards)
    if total == 0:
        return tuple(0.0 for _ in hazards), count
    exits = count * (-math.expm1(-total))
    allocation = tuple(exits * h / total for h in hazards)
    return allocation, count - exits


def run_cohorts(incidence, parameter_lookup, *, allow_provisional=False):
    """Evolve each prevented incident cohort; require all age/duration parameters.

    A cured member remains in the off-disease state and can recur. Other-cause
    death competes in both states. Annual person-years use midpoint occupancy.
    """
    outputs = defaultdict(lambda: defaultdict(float))
    for source in incidence:
        disease, sex, age0 = source["disease"], source["sex"], source["age_group"]
        if disease not in DISEASES:
            raise ValueError("unapproved disease entered dynamic engine")
        start = int(source["year"])
        sick = float(source["incident_cases_averted"])
        if sick < 0:
            raise ValueError("negative prevented incidence")
        well = 0.0
        for year in range(start, 2051):
            duration = year - start
            age = age_at(age0, duration)
            param = parameter_lookup(disease, sex, age, duration)
            if param is None:
                raise InputBlocked(f"BLOCKED_DYNAMIC_PARAMETERS: {disease}/{sex}/{age}/duration={duration}")
            param.validate()
            if (param.disease, param.sex, param.age_group, param.duration) != (disease, sex, age, duration):
                raise ValueError("transition parameter key mismatch")
            if param.provenance == "SYNTHETIC_TEST_ONLY" and not allow_provisional:
                raise InputBlocked("BLOCKED_DYNAMIC_PARAMETERS: synthetic parameters barred from formal run")
            (disease_death, other_death_sick, remission), sick_survive = competing_exits(
                sick, (param.disease_death_hazard, param.other_death_hazard, param.remission_hazard))
            (other_death_well, recurrence), well_survive = competing_exits(
                well, (param.other_death_hazard, param.recurrence_hazard))
            patient_years = (sick + sick_survive) / 2
            yld = patient_years * param.disability_weight
            yll = disease_death * param.standard_remaining_life_years
            key = (year, disease, sex, age)
            bucket = outputs[key]
            bucket["incident_cases_averted"] += float(source["incident_cases_averted"]) if duration == 0 else 0.0
            bucket["prevalent_patient_years_averted"] += patient_years
            bucket["disease_deaths_averted"] += disease_death
            bucket["other_deaths_competing"] += other_death_sick + other_death_well
            bucket["YLD_averted"] += yld
            bucket["YLL_averted"] += yll
            bucket["DALY_averted"] += yld + yll
            sick, well = sick_survive + recurrence, well_survive + remission
    fields = ["year", "disease", "sex", "age_group", "scenario", "incident_cases_averted", "prevalent_patient_years_averted", "disease_deaths_averted", "other_deaths_competing", "YLD_averted", "YLL_averted", "DALY_averted", "parameter_status", "result_status"]
    result = []
    for key, values in sorted(outputs.items()):
        row = dict(zip(fields[:4], key))
        row.update(scenario="difference_vs_control", **values)
        row["parameter_status"] = "SYNTHETIC_TEST_ONLY" if allow_provisional else "ADMITTED"
        row["result_status"] = "DYNAMIC_PILOT_PROVISIONAL" if allow_provisional else "DYNAMIC_PILOT_COMPLETE"
        result.append(row)
    return result, fields


def summarize(rows):
    measures = ("incident_cases_averted", "prevalent_patient_years_averted", "disease_deaths_averted", "YLD_averted", "YLL_averted", "DALY_averted")
    out = defaultdict(lambda: defaultdict(float))
    for row in rows:
        for key in ((row["disease"], "2025-2050"), ("TOTAL", "2025-2050")):
            for measure in measures:
                out[key][measure] += float(row[measure])
    return [dict(disease=k[0], period=k[1], **v) for k, v in sorted(out.items())]


def missing_parameter(*_):
    return None


def synthetic_fixture(disease, sex, age, duration):
    """Software test values only; no epidemiological interpretation or admission."""
    return Transition(disease, sex, age, duration, .04, .02, .01, .005, .15, 20.0, "SYNTHETIC_TEST_ONLY")


def verify_rate_number_pairs():
    import io
    import zipfile
    verify_raw()
    with zipfile.ZipFile(RAW_ZIP) as archive:
        name = next(n for n in archive.namelist() if n.lower().endswith(".csv"))
        rows = list(csv.DictReader(io.TextIOWrapper(archive.open(name), encoding="utf-8-sig")))
    pairs = defaultdict(dict)
    for row in rows:
        if row["year"] == "2023" and row["age_name"] != "70+ years":
            key = tuple(row[k] for k in ("cause_name", "sex_name", "age_name", "measure_name"))
            pairs[key][row["metric_name"]] = float(row["val"])
    if len(pairs) != 64 or any(set(v) != {"Rate", "Number"} for v in pairs.values()):
        raise InputBlocked("BLOCKED_INPUT: Rate/Number pairs incomplete")
    implied = {key: value["Number"] / value["Rate"] * 100000 for key, value in pairs.items()}
    for sex in ("Male", "Female"):
        for age in {key[2] for key in implied}:
            ihd = implied[("Ischemic heart disease", sex, age, "Incidence")]
            stroke = implied[("Ischemic stroke", sex, age, "Incidence")]
            if not math.isclose(ihd, stroke, rel_tol=1e-8):
                raise InputBlocked("BLOCKED_INPUT: Rate/Number implied population disagrees across diseases")
    return implied
