"""Validation and descriptive calibration for the user-downloaded GBD 2023 export."""
from __future__ import annotations

import csv
import hashlib
import io
import math
import zipfile
from collections import defaultdict

from .dynamic_model import InputBlocked, R4

DYNAMIC_GBD_ZIP = R4 / "raw" / "IHME-GBD_2023_DATA-353a02a2-1.zip"
DYNAMIC_GBD_SHA = "9ba35729cab5994ad9ce05427228c71b127d8b4bf03db899681ef250b2a5e2b7"
ALL_CAUSE_GBD_ZIP = R4 / "raw" / "IHME-GBD_2023_DATA-52b38bf7-1.zip"
ALL_CAUSE_GBD_SHA = "dd38441e963a02f9f572afb56c8f2d4dfb39b58bc48b1c7ebff28d0c09fe835e"
DETAIL_AGES = [f"{age}-{age+4} years" for age in range(20, 95, 5)] + ["95+ years"]
AGGREGATE_AGES = {"70+ years", "75+ years", "80+ years", "85+ years"}
CAUSES = {"Ischemic heart disease": "IHD", "Ischemic stroke": "IS"}
MEASURES = {
    "Prevalence",
    "Deaths",
    "YLDs (Years Lived with Disability)",
    "YLLs (Years of Life Lost)",
    "DALYs (Disability-Adjusted Life Years)",
}


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalized_age(value):
    return value.removesuffix(" years")


def load_dynamic_gbd():
    """Return the 640 detailed rows and validated provenance metadata."""
    if not DYNAMIC_GBD_ZIP.is_file():
        raise InputBlocked("BLOCKED_INPUT: GBD 2023 dynamic endpoint ZIP missing")
    digest = sha256_file(DYNAMIC_GBD_ZIP)
    if digest != DYNAMIC_GBD_SHA:
        raise InputBlocked("BLOCKED_INPUT: GBD 2023 dynamic endpoint ZIP SHA256 mismatch")
    with zipfile.ZipFile(DYNAMIC_GBD_ZIP) as archive:
        csv_names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if len(csv_names) != 1 or "citation.txt" not in archive.namelist():
            raise InputBlocked("BLOCKED_INPUT: dynamic endpoint ZIP members invalid")
        rows = list(csv.DictReader(io.TextIOWrapper(archive.open(csv_names[0]), encoding="utf-8-sig")))
        citation = archive.read("citation.txt").decode("utf-8-sig").strip()
    if len(rows) != 800:
        raise InputBlocked(f"BLOCKED_INPUT: expected 800 dynamic endpoint rows, found {len(rows)}")
    expected_headers = {
        "population_group_id", "population_group_name", "measure_id", "measure_name",
        "location_id", "location_name", "sex_id", "sex_name", "age_id", "age_name",
        "cause_id", "cause_name", "metric_id", "metric_name", "year", "val", "upper", "lower",
    }
    if set(rows[0]) != expected_headers:
        raise InputBlocked("BLOCKED_INPUT: dynamic endpoint columns differ from expected GBD export")
    detailed, aggregate, keys = [], [], set()
    for row in rows:
        if row["population_group_name"] != "All Population" or row["location_name"] != "China":
            raise InputBlocked("BLOCKED_INPUT: dynamic endpoint population/location mismatch")
        if row["year"] != "2023" or row["sex_name"] not in {"Male", "Female"}:
            raise InputBlocked("BLOCKED_INPUT: dynamic endpoint year/sex mismatch")
        if row["cause_name"] not in CAUSES or row["measure_name"] not in MEASURES:
            raise InputBlocked("BLOCKED_INPUT: dynamic endpoint cause/measure mismatch")
        if row["metric_name"] not in {"Rate", "Number"}:
            raise InputBlocked("BLOCKED_INPUT: dynamic endpoint metric mismatch")
        key = tuple(row[field] for field in (
            "measure_name", "metric_name", "cause_name", "location_name",
            "sex_name", "age_name", "year", "population_group_name",
        ))
        if key in keys:
            raise InputBlocked("BLOCKED_INPUT: duplicate dynamic endpoint key")
        keys.add(key)
        lower, point, upper = (float(row[field]) for field in ("lower", "val", "upper"))
        if lower < 0 or not lower <= point <= upper:
            raise InputBlocked("BLOCKED_INPUT: invalid dynamic endpoint point/UI")
        if row["age_name"] in DETAIL_AGES:
            detailed.append(row)
        elif row["age_name"] in AGGREGATE_AGES:
            aggregate.append(row)
        else:
            raise InputBlocked("BLOCKED_INPUT: unexpected dynamic endpoint age")
    if len(detailed) != 640 or len(aggregate) != 160:
        raise InputBlocked("BLOCKED_INPUT: detailed/aggregate dynamic endpoint row count mismatch")
    dimensions = {
        "cause": {row["cause_name"] for row in detailed},
        "measure": {row["measure_name"] for row in detailed},
        "metric": {row["metric_name"] for row in detailed},
        "sex": {row["sex_name"] for row in detailed},
        "age": {row["age_name"] for row in detailed},
    }
    expected = {
        "cause": set(CAUSES), "measure": MEASURES, "metric": {"Rate", "Number"},
        "sex": {"Male", "Female"}, "age": set(DETAIL_AGES),
    }
    if dimensions != expected:
        raise InputBlocked("BLOCKED_INPUT: detailed dynamic endpoint dimensions incomplete")
    pairs = defaultdict(dict)
    for row in detailed:
        key = (row["cause_name"], row["sex_name"], row["age_name"], row["measure_name"])
        pairs[key][row["metric_name"]] = row
    if len(pairs) != 320 or any(set(pair) != {"Rate", "Number"} for pair in pairs.values()):
        raise InputBlocked("BLOCKED_INPUT: dynamic endpoint Rate/Number pairs incomplete")
    implied = {}
    for key, pair in pairs.items():
        rate, number = float(pair["Rate"]["val"]), float(pair["Number"]["val"])
        if rate <= 0:
            raise InputBlocked("BLOCKED_INPUT: nonpositive rate prevents population reconciliation")
        implied[key] = number / rate * 100000
    for sex in ("Male", "Female"):
        for age in DETAIL_AGES:
            values = [
                value for (cause, pair_sex, pair_age, measure), value in implied.items()
                if pair_sex == sex and pair_age == age
            ]
            if len(values) != 10 or not math.isclose(min(values), max(values), rel_tol=1e-8):
                raise InputBlocked("BLOCKED_INPUT: dynamic endpoint implied population mismatch")
    rates = {
        (CAUSES[row["cause_name"]], row["sex_name"], normalized_age(row["age_name"]), row["measure_name"]):
        tuple(float(row[field]) for field in ("val", "lower", "upper"))
        for row in detailed if row["metric_name"] == "Rate"
    }
    for disease in ("IHD", "IS"):
        for sex in ("Male", "Female"):
            for age in [normalized_age(value) for value in DETAIL_AGES]:
                yld = rates[(disease, sex, age, "YLDs (Years Lived with Disability)")][0]
                yll = rates[(disease, sex, age, "YLLs (Years of Life Lost)")][0]
                daly = rates[(disease, sex, age, "DALYs (Disability-Adjusted Life Years)")][0]
                if not math.isclose(daly, yld + yll, rel_tol=1e-9, abs_tol=1e-9):
                    raise InputBlocked("BLOCKED_INPUT: GBD DALY point does not equal YLD plus YLL")
    metadata = {
        "filename": DYNAMIC_GBD_ZIP.name,
        "sha256": digest,
        "internal_csv": csv_names[0],
        "obtained_date": "2026-11-12",
        "gbd_version": "GBD 2023",
        "location": ["China"],
        "population_group": ["All Population"],
        "year": [2023],
        "sex": ["Male", "Female"],
        "cause": sorted(CAUSES),
        "measure": sorted(MEASURES),
        "metric": ["Number", "Rate"],
        "detailed_age": DETAIL_AGES,
        "aggregate_age_excluded": sorted(AGGREGATE_AGES),
        "raw_rows": len(rows),
        "detailed_rows": len(detailed),
        "aggregate_rows_excluded": len(aggregate),
        "rate_number_pairs": len(pairs),
        "citation": citation,
        "query_screenshot_status": "COMPLETE_QUERY_SCREENSHOT_NOT_PROVIDED",
        "all_cause_mortality_status": "MISSING_SEPARATE_EXPORT",
    }
    return detailed, rates, implied, metadata


def descriptive_calibration_rows(incidence_2025, burden_rates):
    """Point ratios only; UI bounds stay blank because draws/covariance are unavailable."""
    incidence = {
        (row["disease"], row["sex"], row["age_group"]): float(row["baseline_rate_per_100k"])
        for row in incidence_2025
    }
    output = []
    definitions = (
        ("Prevalence/Incidence", "Prevalence", "Incidence"),
        ("Deaths/Prevalence", "Deaths", "Prevalence"),
        ("YLD/Prevalence", "YLD", "Prevalence"),
        ("YLL/Deaths", "YLL", "Deaths"),
    )
    measure_names = {
        "Prevalence": "Prevalence",
        "Deaths": "Deaths",
        "YLD": "YLDs (Years Lived with Disability)",
        "YLL": "YLLs (Years of Life Lost)",
    }
    for disease, sex, age in sorted(incidence):
        available = {
            label: burden_rates[(disease, sex, age, source_name)][0]
            for label, source_name in measure_names.items()
        }
        available["Incidence"] = incidence[(disease, sex, age)]
        for ratio, numerator, denominator in definitions:
            output.append({
                "disease": disease, "sex": sex, "age": age, "ratio": ratio,
                "numerator_rate_per_100k": available[numerator],
                "denominator_rate_per_100k": available[denominator],
                "point": available[numerator] / available[denominator],
                "lower": "", "upper": "",
                "status": "DESCRIPTIVE_CALIBRATION_TARGET",
                "interpretation": "Not an annual transition probability; UI not derived without joint draws/covariance",
                "source_file": DYNAMIC_GBD_ZIP.name,
            })
    return output


def load_all_cause_gbd():
    """Validate the all-cause export and return detailed Deaths rate targets."""
    if not ALL_CAUSE_GBD_ZIP.is_file():
        raise InputBlocked("BLOCKED_INPUT: GBD 2023 all-cause ZIP missing")
    digest = sha256_file(ALL_CAUSE_GBD_ZIP)
    if digest != ALL_CAUSE_GBD_SHA:
        raise InputBlocked("BLOCKED_INPUT: GBD 2023 all-cause ZIP SHA256 mismatch")
    with zipfile.ZipFile(ALL_CAUSE_GBD_ZIP) as archive:
        csv_names = [name for name in archive.namelist() if name.lower().endswith('.csv')]
        if len(csv_names) != 1 or 'citation.txt' not in archive.namelist():
            raise InputBlocked("BLOCKED_INPUT: all-cause ZIP members invalid")
        rows = list(csv.DictReader(io.TextIOWrapper(archive.open(csv_names[0]), encoding='utf-8-sig')))
        citation = archive.read('citation.txt').decode('utf-8-sig').strip()
    if len(rows) != 400:
        raise InputBlocked(f"BLOCKED_INPUT: expected 400 all-cause rows, found {len(rows)}")
    detailed, aggregate, keys = [], [], set()
    for row in rows:
        if (row['population_group_name'], row['location_name'], row['year'], row['cause_name']) != ('All Population', 'China', '2023', 'All causes'):
            raise InputBlocked("BLOCKED_INPUT: all-cause query scope mismatch")
        if row['sex_name'] not in {'Male', 'Female'} or row['measure_name'] not in MEASURES or row['metric_name'] not in {'Rate', 'Number'}:
            raise InputBlocked("BLOCKED_INPUT: all-cause dimensions invalid")
        key = tuple(row[field] for field in ('measure_name','metric_name','sex_name','age_name','year'))
        if key in keys:
            raise InputBlocked("BLOCKED_INPUT: duplicate all-cause key")
        keys.add(key)
        lower, point, upper = (float(row[field]) for field in ('lower','val','upper'))
        if lower < 0 or not lower <= point <= upper:
            raise InputBlocked("BLOCKED_INPUT: invalid all-cause point/UI")
        if row['age_name'] in DETAIL_AGES:
            detailed.append(row)
        elif row['age_name'] in AGGREGATE_AGES:
            aggregate.append(row)
        else:
            raise InputBlocked("BLOCKED_INPUT: unexpected all-cause age")
    if len(detailed) != 320 or len(aggregate) != 80:
        raise InputBlocked("BLOCKED_INPUT: detailed/aggregate all-cause row count mismatch")
    if ({row['measure_name'] for row in detailed}, {row['metric_name'] for row in detailed},
        {row['sex_name'] for row in detailed}, {row['age_name'] for row in detailed}) != (
        MEASURES, {'Rate','Number'}, {'Male','Female'}, set(DETAIL_AGES)):
        raise InputBlocked("BLOCKED_INPUT: detailed all-cause dimensions incomplete")
    pairs = defaultdict(dict)
    for row in detailed:
        key = (row['sex_name'], row['age_name'], row['measure_name'])
        pairs[key][row['metric_name']] = row
    if len(pairs) != 160 or any(set(pair) != {'Rate','Number'} for pair in pairs.values()):
        raise InputBlocked("BLOCKED_INPUT: all-cause Rate/Number pairs incomplete")
    implied = {}
    for key, pair in pairs.items():
        rate, number = float(pair['Rate']['val']), float(pair['Number']['val'])
        if rate <= 0:
            raise InputBlocked("BLOCKED_INPUT: nonpositive all-cause rate")
        implied[key] = number / rate * 100000
    for sex in ('Male','Female'):
        for age in DETAIL_AGES:
            values = [value for (pair_sex,pair_age,measure),value in implied.items() if pair_sex==sex and pair_age==age]
            if len(values) != 5 or not math.isclose(min(values),max(values),rel_tol=1e-8):
                raise InputBlocked("BLOCKED_INPUT: all-cause implied population mismatch")
    death_rates = {
        (row['sex_name'], normalized_age(row['age_name'])):
        tuple(float(row[field]) for field in ('val','lower','upper'))
        for row in detailed if row['measure_name']=='Deaths' and row['metric_name']=='Rate'
    }
    if len(death_rates) != 32:
        raise InputBlocked("BLOCKED_INPUT: all-cause detailed Deaths rates incomplete")
    metadata = {
        'filename': ALL_CAUSE_GBD_ZIP.name, 'sha256': digest, 'internal_csv': csv_names[0],
        'obtained_date': '2026-11-12', 'gbd_version': 'GBD 2023', 'location': ['China'],
        'population_group': ['All Population'], 'year': [2023], 'sex': ['Male','Female'],
        'cause': ['All causes'], 'measure': sorted(MEASURES), 'metric': ['Number','Rate'],
        'detailed_age': DETAIL_AGES, 'aggregate_age_excluded': sorted(AGGREGATE_AGES),
        'raw_rows': len(rows), 'detailed_rows': len(detailed), 'aggregate_rows_excluded': len(aggregate),
        'rate_number_pairs': len(pairs), 'detailed_deaths_rate_rows': len(death_rates),
        'citation': citation, 'query_screenshot_status': 'COMPLETE_QUERY_SCREENSHOT_NOT_PROVIDED',
        'model_role': 'CALIBRATION_TARGET; hazard conversion and other-cause decomposition not admitted',
    }
    return detailed, death_rates, implied, metadata
