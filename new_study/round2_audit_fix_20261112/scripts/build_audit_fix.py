from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parents[1]
REG = OUT / "registers"
REPORT = OUT / "reports"
CHECK = OUT / "checks"
ROUND1 = ROOT / "new_study" / "round1_20261112"
TARGET = ROOT / "new_study" / "round2_target_prep_20261112"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(name: str, rows: list[dict[str, object]], fields: list[str] | None = None) -> None:
    path = REG / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = list(rows[0])
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def same_number(a: str, b: str) -> bool:
    try:
        return abs(float(a) - float(b)) < 1e-9
    except (TypeError, ValueError):
        return False


legacy_path = ROUND1 / "candidate_inputs" / "cost_legacy.csv"
evidence_path = ROUND1 / "handoff" / "continuation" / "registers" / "medical_cost_evidence_register.csv"
old_audit_path = TARGET / "registers" / "cost_admission_audit_v2.csv"
legacy = read_csv(legacy_path)
evidence = read_csv(evidence_path)
old_audit = {r["cost_id"]: r for r in read_csv(old_audit_path)}
evidence_by_id = {r["evidence_id"]: r for r in evidence}

# Explicit links only. A contextual link documents why fields must not be inherited.
links = {
    "DC-IHD-CN-2012": ("COST-IHD-VERIFY", "CANDIDATE_LINK"),
    "DC-STROKE-CN-2015": ("COST-STROKE-VERIFY", "EXACT_LINK"),
    "DC-T2D-NOCOMP-2007": ("COST-T2D-NOCOMP-VERIFY", "EXACT_LINK"),
    "DC-T2D-COMP-2007": ("", "NO_MATCHING_EVIDENCE"),
    "DC-T2D-ALL-2007": ("COST-T2D-MEAN-VERIFY", "EXACT_LINK"),
    "DC-DEP-CN-2015": ("COST-DEP-VERIFY", "EXACT_LINK"),
    "DC-DEM-CN-2015": ("COST-AD-TOTAL-VERIFY", "CONTEXT_ONLY"),
    "DC-COLON-2020": ("COST-CRC-NEW2014", "CONTEXT_ONLY"),
    "DC-DEM-CN-SOCIAL-2015": ("COST-AD-TOTAL-VERIFY", "EXACT_LINK"),
}

same_original_study_ids = {
    "DC-IHD-CN-2012",
    "DC-STROKE-CN-2015",
    "DC-T2D-NOCOMP-2007",
    "DC-T2D-ALL-2007",
    "DC-DEP-CN-2015",
    "DC-DEM-CN-2015",
    "DC-DEM-CN-SOCIAL-2015",
}

observation_period = {
    "COST-IHD-VERIFY": "2012 claims cohort; publication describes treated patients",
    "COST-STROKE-VERIFY": "2013-2016 pooled claims",
    "COST-DEP-VERIFY": "2013-2016 claims",
    "COST-T2D-NOCOMP-VERIFY": "",
    "COST-T2D-MEAN-VERIFY": "",
    "COST-T2D-NEW2019": "2019",
    "COST-CRC-NEW2014": "2012-2014 diagnosis-treatment course",
    "COST-AD-TOTAL-VERIFY": "2015 annual cost survey",
}

# Exact definition is deliberately conservative. A patient-year cannot silently inherit
# a treated-patient scope requiring annualisation.
def definition_match(cost: dict[str, str], ev: dict[str, str]) -> bool:
    cid = cost["cost_id"]
    return cid in {
        "DC-STROKE-CN-2015",
        "DC-T2D-NOCOMP-2007",
        "DC-T2D-ALL-2007",
        "DC-DEM-CN-SOCIAL-2015",
    }


link_rows: list[dict[str, object]] = []
corrected: list[dict[str, object]] = []
comparison: list[dict[str, object]] = []

for cost in legacy:
    evid, link_type = links.get(cost["cost_id"], ("", "NO_MATCHING_EVIDENCE"))
    ev = evidence_by_id.get(evid, {})
    # Study identity is explicit because one paper may have PubMed, PMC,
    # publisher PDF, and institutional-mirror URLs.
    source_match = bool(ev) and cost["cost_id"] in same_original_study_ids
    amount_match = bool(ev) and same_number(cost["source_value"], ev.get("source_value", ""))
    currency_match = bool(ev) and cost["source_currency"] == ev.get("currency", "")
    def_match = bool(ev) and definition_match(cost, ev)
    assignment_allowed = source_match and amount_match and currency_match and def_match
    if cost["cost_id"] == "DC-IHD-CN-2012":
        reason = "Same source and amount, but legacy annual patient-year is not identical to treated-patient scope requiring annualisation review."
    elif cost["cost_id"] == "DC-T2D-COMP-2007":
        reason = "No evidence row for 6056 CNY; no source-derived fields may be inherited."
    elif cost["cost_id"] == "DC-DEM-CN-2015":
        reason = "6225 USD is not an exact Jia Table 2 amount; 19144.36*32.51%=6223.83 only approximates it."
    elif cost["cost_id"] == "DC-COLON-2020":
        reason = "3447 USD and 61829 CNY are different studies, amounts, currencies and cost definitions."
    elif assignment_allowed:
        reason = "Same original study, exact amount, currency and cost definition; source fields may be carried without filling missing values."
    else:
        reason = "No explicit exact evidence match; source-derived fields remain blank."

    link_rows.append({
        "link_id": f"LINK-{cost['cost_id']}",
        "cost_id": cost["cost_id"],
        "evidence_id": evid,
        "outcome_id": cost["outcome_id"],
        "link_type": link_type,
        "same_original_study": str(source_match).upper(),
        "exact_amount_match": str(amount_match).upper(),
        "exact_currency_match": str(currency_match).upper(),
        "exact_cost_definition_match": str(def_match).upper(),
        "assignment_allowed": str(assignment_allowed).upper(),
        "link_reason": reason,
    })

    verified_year = ev.get("verified_price_year", "") if assignment_allowed else ""
    verified_period = observation_period.get(evid, "") if assignment_allowed else ""
    verified_amount = ev.get("source_value", "") if assignment_allowed else ""
    verified_currency = ev.get("currency", "") if assignment_allowed else ""
    verified_unit = ev.get("cost_unit", "") if assignment_allowed else ""
    status = ev.get("source_status", "") if assignment_allowed else (
        "NOT_VERIFIED_EXACT" if cost["cost_id"] == "DC-DEM-CN-2015" else "SOURCE_NOT_EXACTLY_LINKED"
    )
    corrected_row = {
        "cost_id": cost["cost_id"],
        "evidence_id": evid,
        "outcome_id": cost["outcome_id"],
        "candidate_amount": cost["source_value"],
        "candidate_currency": cost["source_currency"],
        "candidate_cost_unit": cost["cost_unit"],
        "candidate_cost_boundary": cost["cost_boundary"],
        "legacy_assumed_price_year": cost["price_year"],
        "source_verified_amount": verified_amount,
        "source_verified_currency": verified_currency,
        "source_verified_price_year": verified_year,
        "source_verified_observation_period": verified_period,
        "source_verified_cost_unit": verified_unit,
        "source_verification_status": status,
        "source_url": cost["source_url"],
        "assignment_allowed": str(assignment_allowed).upper(),
        "model_ready": "NO",
        "remaining_gap": reason + " Coverage, overlap and 2025 price conversion remain gated.",
    }
    corrected.append(corrected_row)
    before = old_audit.get(cost["cost_id"], {})
    changes = []
    for label, old, new in [
        ("price_year", before.get("original_verified_price_year", ""), verified_year),
        ("observation_period", before.get("original_observation_period", ""), verified_period),
        ("evidence_status", before.get("evidence_status", ""), status),
    ]:
        if old != new:
            changes.append(f"{label}:{old or '<blank>'}->{new or '<blank>'}")
    comparison.append({
        "cost_id": cost["cost_id"],
        "evidence_id_after": evid,
        "candidate_amount": cost["source_value"],
        "candidate_currency": cost["source_currency"],
        "before_verified_price_year": before.get("original_verified_price_year", ""),
        "after_verified_price_year": verified_year,
        "before_observation_period": before.get("original_observation_period", ""),
        "after_observation_period": verified_period,
        "before_evidence_status": before.get("evidence_status", ""),
        "after_evidence_status": status,
        "assignment_allowed_after": str(assignment_allowed).upper(),
        "field_changes": " | ".join(changes) or "NO_FIELD_CHANGE",
        "audit_conclusion": reason,
    })

# Keep newer, evidence-only values as distinct candidate records; do not attach them to legacy IDs.
for evid in ["COST-T2D-NEW2019", "COST-CRC-NEW2014"]:
    ev = evidence_by_id[evid]
    corrected.append({
        "cost_id": f"EVIDENCE-CANDIDATE-{evid}",
        "evidence_id": evid,
        "outcome_id": ev["outcome_id"],
        "candidate_amount": ev["source_value"],
        "candidate_currency": ev["currency"],
        "candidate_cost_unit": ev["cost_unit"],
        "candidate_cost_boundary": ev["cost_boundary"],
        "legacy_assumed_price_year": "",
        "source_verified_amount": ev["source_value"],
        "source_verified_currency": ev["currency"],
        "source_verified_price_year": ev["verified_price_year"],
        "source_verified_observation_period": observation_period[evid],
        "source_verified_cost_unit": ev["cost_unit"],
        "source_verification_status": ev["source_status"],
        "source_url": ev["source_url"],
        "assignment_allowed": "TRUE",
        "model_ready": "NO",
        "remaining_gap": "Standalone evidence candidate; treatment coverage, representativeness, overlap and 2025 conversion remain gated.",
    })
    comparison.append({
        "cost_id": f"EVIDENCE-CANDIDATE-{evid}",
        "evidence_id_after": evid,
        "candidate_amount": ev["source_value"],
        "candidate_currency": ev["currency"],
        "before_verified_price_year": ev["verified_price_year"],
        "after_verified_price_year": ev["verified_price_year"],
        "before_observation_period": "2019" if evid == "COST-T2D-NEW2019" else "2012-2014",
        "after_observation_period": observation_period[evid],
        "before_evidence_status": ev["source_status"],
        "after_evidence_status": ev["source_status"],
        "assignment_allowed_after": "TRUE",
        "field_changes": "observation_period clarified",
        "audit_conclusion": "Preserved as a standalone evidence candidate; not inherited by legacy same-disease rows.",
    })

write_csv("cost_evidence_links_v3.csv", link_rows)
write_csv("cost_admission_audit_v3.csv", corrected)
write_csv("cost_row_comparison_v2_to_v3.csv", comparison)

write_csv("audit_fix_log.csv", [
    {"fix_id": "AF-001", "area": "cost linkage", "prior_issue": "outcome_id last-row lookup cross-assigned evidence", "revision": "explicit cost_id/evidence_id link plus four exact-match gates", "status": "FIXED"},
    {"fix_id": "AF-002", "area": "T2D", "prior_issue": "3583/6056/10164 inherited 2019", "revision": "all three source-verified price years blank; 2019 record retained separately", "status": "FIXED"},
    {"fix_id": "AF-003", "area": "CRC", "prior_issue": "3447 USD inherited 2014 from 61829 CNY", "revision": "legacy verified year blank; 61829 CNY retained separately", "status": "FIXED"},
    {"fix_id": "AF-004", "area": "dementia", "prior_issue": "6225 USD treated as verified", "revision": "NOT_VERIFIED_EXACT; Jia-derived value is 6223.83", "status": "FIXED"},
    {"fix_id": "AF-005", "area": "validation", "prior_issue": "integrity and science gates mixed; rerun could duplicate checks", "revision": "separate deterministic/upsert JSON reports with unique check_id", "status": "FIXED"},
    {"fix_id": "AF-006", "area": "2010 target", "prior_issue": "gap wording implied joint sex-age table universally required", "revision": "CURRENT_COMPARISON_PATH_INCOMPATIBLE with multiple bridge options", "status": "FIXED"},
    {"fix_id": "AF-007", "area": "GBD", "prior_issue": "filter availability not separated", "revision": "confirmed archived, live unchecked, and study-unsupported states separated", "status": "FIXED"},
])

rand_rows = [
    {"trace_id": "DING-T2D", "disease": "type2_diabetes", "input_role": "average annual cost per case", "china_base_amount": "", "unit": "international dollars per prevalent case-year", "price_year": "2013 costing year; underlying IDF method inputs not extracted", "coverage": "health-care expenditure", "original_source": "IDF Diabetes Atlas 6th ed (2013); Zhang et al 2010", "construction": "IDF country estimate", "china_specific_original_study": "NO", "status": "PARTIAL_SUPPLEMENT_REQUIRED", "source_location": "Ding main text Step 6; refs 16-17; appendix p27 required"},
    {"trace_id": "DING-IHD", "disease": "coronary_heart_disease", "input_role": "average annual cost per case", "china_base_amount": "", "unit": "international dollars per prevalent case-year", "price_year": "2013 costing year", "coverage": "direct health-care cost", "original_source": "EU-27 cardiovascular cost data; Leal et al 2012", "construction": "EU cost/prevalence, extrapolated to China using health-expenditure-per-capita weighting", "china_specific_original_study": "NO", "status": "PARTIAL_SUPPLEMENT_REQUIRED", "source_location": "Ding main text Step 6; refs 19-21; appendix p27 required"},
    {"trace_id": "DING-STROKE", "disease": "stroke", "input_role": "average annual cost per case", "china_base_amount": "", "unit": "international dollars per prevalent case-year", "price_year": "2013 costing year", "coverage": "direct health-care cost", "original_source": "EU-27 cardiovascular cost data; Leal et al 2012", "construction": "EU cost/prevalence, extrapolated to China using health-expenditure-per-capita weighting", "china_specific_original_study": "NO", "status": "PARTIAL_SUPPLEMENT_REQUIRED", "source_location": "Ding main text Step 6; refs 19-21; appendix p27 required"},
    {"trace_id": "DING-BREAST", "disease": "breast_cancer", "input_role": "average annual cost per case", "china_base_amount": "", "unit": "international dollars per prevalent case-year", "price_year": "2013 costing year", "coverage": "direct health-care cost", "original_source": "EU-27 cancer cost data; Luengo-Fernandez et al 2013", "construction": "EU cost/prevalence, extrapolated to China using health-expenditure-per-capita weighting", "china_specific_original_study": "NO", "status": "PARTIAL_SUPPLEMENT_REQUIRED", "source_location": "Ding main text Step 6; refs 18,20-21; appendix p27 required"},
    {"trace_id": "DING-COLON", "disease": "colon_cancer", "input_role": "average annual cost per case", "china_base_amount": "", "unit": "international dollars per prevalent case-year", "price_year": "2013 costing year", "coverage": "direct health-care cost", "original_source": "EU-27 cancer cost data; Luengo-Fernandez et al 2013", "construction": "EU cost/prevalence, extrapolated to China using health-expenditure-per-capita weighting", "china_specific_original_study": "NO", "status": "PARTIAL_SUPPLEMENT_REQUIRED", "source_location": "Ding main text Step 6; refs 18,20-21; appendix p27 required"},
    {"trace_id": "DING-CHINA-OUTPUT", "disease": "five NCDs combined", "input_role": "published attributable cost output", "china_base_amount": "3075139", "unit": "thousand international dollars", "price_year": "2013", "coverage": "direct costs attributable to inactivity", "original_source": "Ding et al 2016 Table 1", "construction": "model output after PAF and overlap adjustment", "china_specific_original_study": "NO", "status": "EXTERNAL_REFERENCE_ONLY", "source_location": "Table 1; not a base unit cost"},
    {"trace_id": "ZHANG-CHINA-2013", "disease": "NCD aggregate", "input_role": "published China burden study", "china_base_amount": "", "unit": "annual medical/non-medical burden", "price_year": "not extracted", "coverage": "five inactivity-related NCDs", "original_source": "Zhang and Chaaban 2013; China BRFSS 2007 and NHSS 2003", "construction": "China national attributable burden study", "china_specific_original_study": "YES", "status": "EXTERNAL_REFERENCE_NOT_DING_UNIT_COST", "source_location": "PMID 23200874; disease-specific base costs/full text not acquired"},
]
for trace in rand_rows:
    trace["source_url"] = (
        "https://doi.org/10.1016/S0140-6736(16)30383-X"
        if trace["trace_id"].startswith("DING-")
        else "https://pubmed.ncbi.nlm.nih.gov/23200874/"
    )
write_csv("rand_ding_base_input_trace_v2.csv", rand_rows)

write_csv("unavailable_evidence_requirements.csv", [
    {"requirement_id": "UNAV-DING-SUPP", "artifact": "Ding et al 2016 online appendix", "exact_location": "appendix p27 disease/country annual costs per case; p31 disease/country attributable costs", "attempted_route": "public web search; publisher attachment search; ICSSPE main PDF mirror", "result": "Main paper available through indexed mirror; separate appendix URL/file not identified; direct mirror download returned 404 on 2026-11-12", "needed_from_user": "If available, download the article's online appendix from an authorized Lancet session and retain original filename", "completion_status": "OPEN"},
    {"requirement_id": "UNAV-ZHANG-FULL", "artifact": "Zhang and Chaaban 2013 full text/supplement", "exact_location": "disease-specific China input costs, source tables, currency and price year", "attempted_route": "PubMed and public web search", "result": "Abstract and citation found; detailed input table not acquired", "needed_from_user": "Public or authorized full text/supplement if available", "completion_status": "OPEN"},
])

write_csv("target_monitoring_analysis_bridge.csv", [
    {"bridge_id": "BRIDGE-WHO-18PLUS", "monitoring_series": "WHO modelled insufficient physical activity, adults 18+", "health_analysis_series": "CCDRFS-derived 20+ age-sex baseline", "data_available": "WHO overall/sex series may be obtained; 20+ baseline exists", "missing_for_path": "common-series calibration or explicit bridge assumption", "joint_2010_sex_age_required": "NO", "compatibility_status": "CURRENT_COMPARISON_PATH_INCOMPATIBLE", "work_decision": "Choose whether target monitoring remains a separate 18+ series"},
    {"bridge_id": "BRIDGE-CCDRFS-HARMONIZED", "monitoring_series": "CCDRFS 18+ survey trend", "health_analysis_series": "CCDRFS 20+ mapped baseline", "data_available": "2010 national/sex/separate age summaries and 2018 age-sex rates", "missing_for_path": "harmonized restandardization or microdata for a 20+ comparable estimate", "joint_2010_sex_age_required": "ONLY_IF_STRATUM_SPECIFIC_TARGETS_ARE_CHOSEN", "compatibility_status": "CURRENT_COMPARISON_PATH_INCOMPATIBLE", "work_decision": "Choose national-only versus stratum-specific bridge"},
    {"bridge_id": "BRIDGE-DUAL-TRACK", "monitoring_series": "18+ target-monitoring series", "health_analysis_series": "20+ health model", "data_available": "both series exist separately", "missing_for_path": "Work-approved transfer rule from national target ratio to 20+ baseline", "joint_2010_sex_age_required": "NO", "compatibility_status": "DECISION_REQUIRED", "work_decision": "Approve or reject a dual-track monitoring/application design"},
    {"bridge_id": "BRIDGE-COMMON-20PLUS", "monitoring_series": "reconstructed common 20+ 2010 series", "health_analysis_series": "20+ health model", "data_available": "not currently reconstructed", "missing_for_path": "age-specific or microdata inputs and common standardization", "joint_2010_sex_age_required": "YES_FOR_AGE_SEX_SPECIFIC_TARGETS; NOT_NECESSARILY_FOR_NATIONAL_TARGET", "compatibility_status": "DATA_GAP", "work_decision": "Use only if Work selects a common 20+ reconstruction"},
])

write_csv("target_scenario_pending_values.csv", [
    {"parameter_id": "p_reference_2010", "value": "", "unit": "probability", "status": "WORK_DECISION_PENDING", "reason": "comparison path not selected"},
    {"parameter_id": "p_target_2030", "value": "", "unit": "probability", "status": "WORK_DECISION_PENDING", "reason": "must equal 0.85*p_reference_2010 after comparable reference selected"},
    {"parameter_id": "attainment_gap_2025_to_2030", "value": "", "unit": "probability or relative change", "status": "WORK_DECISION_PENDING", "reason": "2025 start and target not on a selected common path"},
    {"parameter_id": "annual_attainment_path", "value": "", "unit": "rule", "status": "WORK_DECISION_PENDING", "reason": "linear/uniform path is not a WHO requirement"},
])

write_csv("gbd_filter_capability_v2.csv", [
    {"filter_id": "GBD-LOC-CHINA", "filter_dimension": "location", "requested_value": "6:China", "capability_status": "CONFIRMED_IN_ARCHIVED_EXPORT", "evidence": "round1 recovered GBD exports", "model_use_status": "ALLOWED", "action": "reconfirm only when making a new export"},
    {"filter_id": "GBD-POP-ALL", "filter_dimension": "population", "requested_value": "1:All Population", "capability_status": "CONFIRMED_IN_ARCHIVED_EXPORT", "evidence": "round1 recovered GBD exports", "model_use_status": "ALLOWED", "action": "reconfirm in authenticated menu"},
    {"filter_id": "GBD-SEX-MF", "filter_dimension": "sex", "requested_value": "Male|Female", "capability_status": "CONFIRMED_IN_ARCHIVED_EXPORT", "evidence": "round1 recovered direct matches", "model_use_status": "REQUIRED", "action": "do not add Both as third model input"},
    {"filter_id": "GBD-AGE-20-69", "filter_dimension": "age", "requested_value": "five-year groups 20-24 through 65-69", "capability_status": "CONFIRMED_IN_ARCHIVED_EXPORT", "evidence": "round1 recovered exports", "model_use_status": "REQUIRED", "action": "retain five-year groups"},
    {"filter_id": "GBD-AGE-70PLUS-FINE", "filter_dimension": "age", "requested_value": "70-74 through 100+", "capability_status": "NOT_CHECKED_IN_LIVE_TOOL", "evidence": "recovered files contain a 70+ aggregate in relevant paths", "model_use_status": "REQUIRED", "action": "user must confirm every fine-age menu item"},
    {"filter_id": "GBD-METRIC-NUMBER", "filter_dimension": "metric", "requested_value": "Number", "capability_status": "CONFIRMED_IN_ARCHIVED_EXPORT", "evidence": "round1 recovered exports", "model_use_status": "ALLOWED", "action": "download with complete query record"},
    {"filter_id": "GBD-METRIC-RATE", "filter_dimension": "metric", "requested_value": "Rate", "capability_status": "NOT_CHECKED_IN_LIVE_TOOL", "evidence": "not established by archived row matches", "model_use_status": "REQUIRED_FOR_CONSTANT_RATE_PROJECTION", "action": "confirm and export or document absence"},
    {"filter_id": "GBD-CAUSE-COLON", "filter_dimension": "cause", "requested_value": "colon cancer alone", "capability_status": "NOT_CHECKED_IN_LIVE_TOOL", "evidence": "legacy data use colon and rectum combined", "model_use_status": "UNSUPPORTED_FOR_REQUESTED_MODEL_IF_ONLY_COMBINED", "action": "confirm cause hierarchy; do not apply colon RR to combined burden"},
    {"filter_id": "GBD-CAUSE-IS", "filter_dimension": "cause", "requested_value": "ischemic stroke", "capability_status": "CONFIRMED_IN_ARCHIVED_EXPORT", "evidence": "132 incidence rows directly matched in round1", "model_use_status": "ALLOWED_FOR_ISCHEMIC_RR", "action": "other endpoints still require source verification"},
    {"filter_id": "GBD-CAUSE-ICH-SAH", "filter_dimension": "cause", "requested_value": "ICH|SAH", "capability_status": "NOT_CHECKED_IN_LIVE_TOOL", "evidence": "no subtype RR admitted", "model_use_status": "UNSUPPORTED_FOR_ISCHEMIC_RR", "action": "retain raw data only; no IS RR linkage"},
    {"filter_id": "GBD-DEP-DEATH-YLL", "filter_dimension": "measure", "requested_value": "depression Deaths|YLL", "capability_status": "NOT_APPLICABLE_TO_STUDY_PROTOCOL", "evidence": "Work decision", "model_use_status": "UNSUPPORTED_FOR_REQUESTED_MODEL", "action": "do not download as required model input; leave NOT_APPLICABLE"},
])

write_csv("gbd_authenticated_menu_checklist.csv", [
    {"step": "1", "menu_item": "Dataset/release", "selection_or_check": "GBD 2023 Results", "record": "screenshot and citation", "status": "USER_LOGIN_REQUIRED"},
    {"step": "2", "menu_item": "Location/population/sex/year", "selection_or_check": "China; All Population; Male and Female; 2023", "record": "complete filter screenshot", "status": "USER_LOGIN_REQUIRED"},
    {"step": "3", "menu_item": "Age", "selection_or_check": "each five-year age 20-24 through 100+", "record": "mark each selectable/not selectable", "status": "USER_LOGIN_REQUIRED"},
    {"step": "4", "menu_item": "Metric", "selection_or_check": "Rate and Number", "record": "mark each selectable/not selectable", "status": "USER_LOGIN_REQUIRED"},
    {"step": "5", "menu_item": "Cause/measure", "selection_or_check": "test every row in gbd_new_model_detailed_requests.csv; especially colon-only and subtype causes", "record": "exact menu labels/IDs and unavailable items", "status": "USER_LOGIN_REQUIRED"},
    {"step": "6", "menu_item": "Download", "selection_or_check": "split exports if needed", "record": "original ZIP/CSV, citation, query screenshot, download date, SHA256", "status": "USER_LOGIN_REQUIRED"},
])

prior_gbd_requests = read_csv(TARGET / "registers" / "gbd_new_model_detailed_requests.csv")
revised_gbd_requests = []
for request in prior_gbd_requests:
    outcome = request["outcome_id"]
    measure = request["GBD_measure"]
    if outcome == "depression" and measure in {"Deaths", "YLL"}:
        capability = "NOT_APPLICABLE_TO_STUDY_PROTOCOL"
        support = "UNSUPPORTED_FOR_REQUESTED_MODEL"
        action = "Do not download as a required input; preserve NOT_APPLICABLE, not zero."
    elif outcome in {"colon_cancer", "oesophageal_cancer", "gastric_cancer"}:
        capability = "CAUSE_LEVEL_NOT_CHECKED_IN_LIVE_TOOL"
        support = "UNSUPPORTED_IF_ONLY_BROADER_COMBINED_CAUSE_IS_AVAILABLE"
        action = "User must verify the exact subtype/cause menu item before export."
    elif outcome in {"intracerebral_hemorrhage", "subarachnoid_hemorrhage"}:
        capability = "NOT_CHECKED_IN_LIVE_TOOL"
        support = "UNSUPPORTED_FOR_ISCHEMIC_STROKE_RR"
        action = "Raw burden may be downloaded for archive, but may not use ischemic-stroke RR."
    elif outcome in {"coronary_heart_disease", "ischemic_stroke"} and measure == "Incidence":
        capability = "PARTIALLY_CONFIRMED_IN_ARCHIVED_EXPORT; RATE_AND_FINE_70PLUS_NOT_CHECKED"
        support = "CANDIDATE_AFTER_NEW_EXPORT_OR_ARCHIVED_SCOPE_MATCH"
        action = "Confirm Rate and fine ages 70+; retain original export/query artifacts."
    else:
        capability = "NOT_CHECKED_IN_LIVE_TOOL"
        support = "PENDING_SOURCE_AND_FILTER_GATE"
        action = "User must verify exact cause, measure, metric and fine-age selections."
    revised_gbd_requests.append({
        **request,
        "filter_capability_status_v2": capability,
        "requested_model_support_status": support,
        "manual_action_v2": action,
    })
write_csv("gbd_download_requests_audit_v2.csv", revised_gbd_requests)

write_csv("scientific_evidence_gates.csv", [
    {"check_id": "SCI-COST-EXACT-LINK", "gate": "Cost source fields only carried after exact source/amount/currency/definition match", "status": "PASS", "scope": "cost_admission_audit_v3.csv", "remaining_issue": "Most candidates remain not model-ready"},
    {"check_id": "SCI-DING-BASE-INPUT", "gate": "China disease-specific Ding base inputs recovered", "status": "FAIL", "scope": "Ding appendix pp27/31", "remaining_issue": "Supplement not acquired; per-case China values blank"},
    {"check_id": "SCI-TARGET-COMPARABILITY", "gate": "2010 target and 20+ model start on a selected comparable path", "status": "FAIL", "scope": "target bridge", "remaining_issue": "Work has not selected bridge path"},
    {"check_id": "SCI-GBD-LIVE-FILTERS", "gate": "All new-model GBD filters confirmed in authenticated live tool", "status": "NOT_CHECKED", "scope": "GBD 2023 menu", "remaining_issue": "User login required"},
    {"check_id": "SCI-FORMAL-MODEL", "gate": "Formal model run", "status": "NOT_APPLICABLE", "scope": "this audit-fix round", "remaining_issue": "Prohibited by task boundary"},
])

REPORT.mkdir(parents=True, exist_ok=True)
(OUT / "README.md").write_text("""# Round 2 audit fix (2026-11-12)\n\nThis directory is an additive correction based on commit `433143a50a8d49f6220157ceb3fa075d31af3638`, on branch `codex/data-round2-audit-fix-20261112`. It does not overwrite round 1 or round 2 target-preparation files and is not a formal model input freeze.\n\n## Entry points\n\n- `registers/cost_row_comparison_v2_to_v3.csv`: row-level before/after audit.\n- `registers/cost_evidence_links_v3.csv`: explicit `cost_id` to `evidence_id` links and exact-match gates.\n- `checks/file_integrity.json`: structural/file checks.\n- `checks/scientific_gates.json`: scientific evidence gates.\n- `reports/HANDOFF_AUDIT_FIX.md`: next-round handoff.\n\nMissing numeric values remain blank. No formal health model, cost aggregation, or PSA was run.\n""", encoding="utf-8")

(REPORT / "AUDIT_FIX_RECORD.md").write_text("""# Audit fix record\n\n## Cost linkage\n\nThe prior `outcome_id` lookup was removed from the corrected interface. Every carried source field now requires an explicit `cost_id`/`evidence_id` link and exact agreement on original study, amount, currency, and cost definition. The legacy assumed price year remains a separate provenance field and is never relabelled as source-verified.\n\n- T2D 3583, 6056 and 10164 CNY no longer inherit 2019. The separate 2092.87 USD/2019 evidence candidate remains intact.\n- CRC 3447 USD no longer inherits 2014. The separate 61829 CNY/2014 evidence candidate remains intact.\n- Dementia 6225 USD is `NOT_VERIFIED_EXACT`; Jia's published 19144.36 USD total and the approximate 6223.83 calculation remain distinguishable.\n\n## Validation\n\nFile/identifier integrity and scientific evidence gates are reported separately. The finalizer upserts checks by unique `check_id`, so repeated runs update rather than append.\n""", encoding="utf-8")

(REPORT / "RAND_DING_INPUT_TRACE.md").write_text("""# RAND/Ding base-input trace\n\nDing et al. estimated 2013 costs. T2D per-case costs came from IDF sources. IHD, stroke, breast cancer and colon cancer per-case costs were constructed from EU-27 costs divided by GBD prevalence and extrapolated to China with a health-expenditure-per-capita weight. These are modelled country inputs, not China disease-cost studies.\n\nChina's published 3,075,139 thousand INT$ attributable direct cost is retained only as an external model-output reference. Exact China disease-specific per-case inputs require the online appendix (p27; attributable outputs p31), which was not acquired publicly. This item remains open.\n""", encoding="utf-8")

(REPORT / "GBD_MANUAL_CHECKLIST.md").write_text("""# GBD authenticated menu and download checklist\n\nAfter the user signs in, select GBD 2023, China, All Population, 2023, Male and Female. Confirm every five-year age from 20-24 through 100+, and test both Rate and Number. Then test each requested cause/measure exactly as listed in the prior detailed request table, recording exact menu labels and IDs.\n\nDownload original ZIP/CSV plus citation and codebook. Save a full filter screenshot, download date and SHA256. Do not substitute combined colon-and-rectum burden for colon-only, or ICH/SAH for ischemic stroke.\n""", encoding="utf-8")

(REPORT / "HANDOFF_AUDIT_FIX.md").write_text("""# Handoff: round 2 audit fix\n\nBranch: `codex/data-round2-audit-fix-20261112`  \nBase commit: `433143a50a8d49f6220157ceb3fa075d31af3638`\n\n## Completed\n\n- Replaced disease-level evidence inheritance with explicit cost/evidence links.\n- Preserved 17 legacy cost values plus two newer standalone evidence candidates.\n- Added row-level before/after comparison and independent integrity/science checks.\n- Traced Ding's cost construction to IDF and EU-27 sources and classified published China attributable costs as external outputs.\n- Reframed the 2010 issue as current-path incompatibility and documented four possible 18+/20+ bridges without choosing one.\n- Split GBD filters into archived-confirmed, live-unchecked, and unsupported-for-requested-model states; added a user-login checklist.\n\n## Still open\n\n- Ding online appendix pp27/31 and Zhang/Chaaban detailed input tables were not acquired.\n- No comparable 2010-to-2025 path has been selected; target value, attainment gap and annual path remain blank.\n- Fine ages 70+ and Rate/cause details require an authenticated GBD menu check.\n- Cost coverage, overlap, treatment uptake and 2025 conversion remain unresolved; no cost total is admissible.\n\n## Boundary\n\nNo formal health model, cost aggregation, PSA, CEA or policy-cost module was run. This branch is an audit correction, not a model freeze.\n""", encoding="utf-8")

handoff_path = REPORT / "HANDOFF_AUDIT_FIX.md"
handoff_text = handoff_path.read_text(encoding="utf-8").replace(
    "Branch: `codex/data-round2-audit-fix-20261112`  \nBase commit:",
    "Branch: `codex/data-round2-audit-fix-20261112`\n\nBase commit:",
)
handoff_path.write_text(handoff_text, encoding="utf-8")

# Keep repository text hashes stable across Windows checkout and Git LF normalization.
for text_path in [OUT / "README.md", *sorted(REPORT.glob("*.md"))]:
    text_path.write_bytes(text_path.read_bytes().replace(b"\r\n", b"\n"))

print(f"Built audit-fix files in {OUT}")
