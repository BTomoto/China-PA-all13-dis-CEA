from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


OUT = Path(__file__).resolve().parents[1]
ROOT = Path(__file__).resolve().parents[3]
REG = OUT / "registers"
CHECK = OUT / "checks"


def read_csv(name: str) -> list[dict[str, str]]:
    with (REG / name).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def upsert(path: Path, checks: list[dict[str, object]]) -> None:
    # Existing checks are keyed and replaced. Re-running never appends duplicate IDs.
    existing: dict[str, dict[str, object]] = {}
    if path.exists():
        old = json.loads(path.read_text(encoding="utf-8"))
        existing = {x["check_id"]: x for x in old.get("checks", [])}
    for check in checks:
        existing[str(check["check_id"])] = check
    ordered = [existing[k] for k in sorted(existing)]
    path.write_text(json.dumps({"checks": ordered, "summary": {
        status: sum(1 for x in ordered if x["status"] == status)
        for status in ["PASS", "FAIL", "NOT_CHECKED", "NOT_APPLICABLE"]
    }}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n"))


cost = read_csv("cost_admission_audit_v3.csv")
links = read_csv("cost_evidence_links_v3.csv")
comparison = read_csv("cost_row_comparison_v2_to_v3.csv")
science = read_csv("scientific_evidence_gates.csv")
with (ROOT / "new_study" / "round1_20261112" / "handoff" / "continuation" / "registers" / "medical_cost_evidence_register.csv").open("r", encoding="utf-8-sig", newline="") as handle:
    source_evidence = list(csv.DictReader(handle))
source_evidence_by_id = {x["evidence_id"]: x for x in source_evidence}


def unique(rows: list[dict[str, str]], key: str) -> bool:
    values = [r[key] for r in rows]
    return len(values) == len(set(values)) and all(values)


def no_cross_assignment() -> bool:
    for row in cost:
        if row["assignment_allowed"] != "TRUE":
            if any(row[x] for x in ["source_verified_amount", "source_verified_currency", "source_verified_price_year", "source_verified_observation_period", "source_verified_cost_unit"]):
                return False
    return True


def exact_flags_gate() -> bool:
    for row in links:
        if row["assignment_allowed"] == "TRUE":
            if not all(row[x] == "TRUE" for x in ["same_original_study", "exact_amount_match", "exact_currency_match", "exact_cost_definition_match"]):
                return False
    return True


def admitted_fields_equal_source() -> bool:
    for record in cost:
        if record["assignment_allowed"] != "TRUE" or record["cost_id"].startswith("EVIDENCE-CANDIDATE-"):
            continue
        source = source_evidence_by_id[record["evidence_id"]]
        if record["source_verified_amount"] != source["source_value"]:
            return False
        if record["source_verified_currency"] != source["currency"]:
            return False
        if record["source_verified_price_year"] != source["verified_price_year"]:
            return False
        if record["source_verified_cost_unit"] != source["cost_unit"]:
            return False
    return True


def row(cost_id: str) -> dict[str, str]:
    return next(x for x in cost if x["cost_id"] == cost_id)


file_checks = [
    {"check_id": "FILE-001", "description": "corrected cost_id values are unique", "status": "PASS" if unique(cost, "cost_id") else "FAIL", "evidence": str(len(cost))},
    {"check_id": "FILE-002", "description": "link_id values are unique", "status": "PASS" if unique(links, "link_id") else "FAIL", "evidence": str(len(links))},
    {"check_id": "FILE-003", "description": "comparison has one row per corrected cost candidate", "status": "PASS" if len(comparison) == len(cost) and unique(comparison, "cost_id") else "FAIL", "evidence": f"comparison={len(comparison)} cost={len(cost)}"},
    {"check_id": "FILE-004", "description": "non-admitted links carry no verified amount/currency/year/period/unit", "status": "PASS" if no_cross_assignment() else "FAIL", "evidence": "five source-derived fields checked"},
    {"check_id": "FILE-005", "description": "admitted assignments satisfy all four exact-match flags", "status": "PASS" if exact_flags_gate() else "FAIL", "evidence": "source, amount, currency, definition"},
    {"check_id": "FILE-006", "description": "legacy T2D values do not inherit 2019", "status": "PASS" if all(row(x)["source_verified_price_year"] == "" for x in ["DC-T2D-NOCOMP-2007", "DC-T2D-COMP-2007", "DC-T2D-ALL-2007"]) else "FAIL", "evidence": "3583/6056/10164 CNY"},
    {"check_id": "FILE-007", "description": "legacy CRC 3447 USD does not inherit 2014", "status": "PASS" if row("DC-COLON-2020")["source_verified_price_year"] == "" else "FAIL", "evidence": "DC-COLON-2020"},
    {"check_id": "FILE-008", "description": "dementia 6225 USD is not exact-verified", "status": "PASS" if row("DC-DEM-CN-2015")["source_verification_status"] == "NOT_VERIFIED_EXACT" and row("DC-DEM-CN-2015")["assignment_allowed"] == "FALSE" else "FAIL", "evidence": "Jia calculation=6223.83"},
    {"check_id": "FILE-009", "description": "17 legacy values plus 2 evidence-only candidates are preserved", "status": "PASS" if len(cost) == 19 else "FAIL", "evidence": str(len(cost))},
    {"check_id": "FILE-010", "description": "source evidence_id values are unique", "status": "PASS" if unique(source_evidence, "evidence_id") else "FAIL", "evidence": str(len(source_evidence))},
    {"check_id": "FILE-011", "description": "admitted amount, currency, price year and cost unit equal the linked evidence row", "status": "PASS" if admitted_fields_equal_source() else "FAIL", "evidence": "direct field-by-field comparison"},
    {"check_id": "FILE-012", "description": "formal model output absent by design", "status": "NOT_APPLICABLE", "evidence": "audit/data round only"},
]
upsert(CHECK / "file_integrity.json", file_checks)
upsert(CHECK / "scientific_gates.json", [
    {"check_id": x["check_id"], "description": x["gate"], "status": x["status"], "evidence": x["remaining_issue"]}
    for x in science
])

# Generate manifest last, excluding itself so it is stable across repeated runs.
manifest = []
for path in sorted(p for p in OUT.rglob("*") if p.is_file() and p.name != "file_manifest_sha256.csv"):
    manifest.append({"path": path.relative_to(OUT).as_posix(), "sha256": digest(path), "size_bytes": path.stat().st_size})
with (REG / "file_manifest_sha256.csv").open("w", encoding="utf-8-sig", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=["path", "sha256", "size_bytes"], lineterminator="\n")
    writer.writeheader()
    writer.writerows(manifest)

failed = [x for x in file_checks if x["status"] == "FAIL"]
print(json.dumps({"file_checks": len(file_checks), "failed": len(failed), "manifest_files": len(manifest)}, ensure_ascii=False))
if failed:
    raise SystemExit(1)
