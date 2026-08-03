from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent.parent


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


gbd_qc = pd.read_csv(ROOT / "audit_gbd_update" / "00_GBD更新QC.csv", encoding="utf-8-sig")
det_qc = pd.read_csv(ROOT / "results" / "00_QC.csv", encoding="utf-8-sig")
smoke_qc = pd.read_csv(ROOT / "psa_smoke_recheck" / "merged" / "00_QC.csv", encoding="utf-8-sig")
smoke_manifest = json.loads((ROOT / "psa_smoke_recheck" / "merged" / "MERGED_MANIFEST.json").read_text(encoding="utf-8"))
psa_manifest = json.loads((ROOT / "input" / "psa" / "PSA_INPUT_MANIFEST_v1.2.json").read_text(encoding="utf-8"))
stage = json.loads((ROOT / "STAGE_STATUS.json").read_text(encoding="utf-8"))
formula_scan = (ROOT / "workbook_previews_v1.3" / "formula_errors.ndjson").read_text(encoding="utf-8")

notebook_paths = [
    ROOT / "notebooks" / "02_联合PSA烟雾测试审计_v1.3.ipynb",
    ROOT / "notebooks" / "03_正式10000次PSA运行_v1.3.ipynb",
]
for notebook_path in notebook_paths:
    notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
    assert notebook["nbformat"] == 4 and notebook["cells"], notebook_path

raw_zips = sorted((ROOT / "input" / "gbd_raw_2010_2017").glob("*.zip"))
for raw_zip in raw_zips:
    with zipfile.ZipFile(raw_zip) as archive:
        assert archive.testzip() is None, raw_zip

assert len(raw_zips) == 3
assert gbd_qc["status"].eq("PASS").all()
assert det_qc["passed"].astype(bool).all()
assert smoke_qc["status"].eq("PASS").all()
assert smoke_manifest["draws"] == 200 and not smoke_manifest["formal_psa_run"]
assert psa_manifest["gbd_status"] == "GBD_2010_2023_FINAL_HISTORY_LOCKED"
assert psa_manifest["formal_psa_status"] == "READY_FOR_USER_LOCAL_RUN_AFTER_SMOKE_QC"
assert stage["formal_psa_ready_after_smoke_qc"] is True
assert stage["workbook_refresh_required_after_local_model_rerun"] is False
assert "matched 0 entries" in formula_scan
assert (ROOT / "ALLdis_GBD2010_2023更新与正式PSA候选审计_v1.3.xlsx").exists()

manifest = {
    "bundle_version": "ALLdis_D1_D10_GBD2010_2023_formal_PSA_runner_v1.3",
    "gbd_history_window": "2010-2023",
    "gbd_raw_zip_count": len(raw_zips),
    "gbd_raw_rows": 19328,
    "gbd_qc_pass": int(gbd_qc["status"].eq("PASS").sum()),
    "gbd_qc_total": int(len(gbd_qc)),
    "deterministic_qc_pass": int(det_qc["passed"].astype(bool).sum()),
    "deterministic_qc_total": int(len(det_qc)),
    "smoke_draws": smoke_manifest["draws"],
    "smoke_batches": smoke_manifest["batches"],
    "smoke_qc_pass": int(smoke_qc["status"].eq("PASS").sum()),
    "smoke_qc_total": int(len(smoke_qc)),
    "formal_psa_run": False,
    "formal_psa_ready": True,
    "formal_plan": "20 batches x 500 draws",
    "main_formal_horizons": [5, 10],
    "extended_horizon_status": "INTERIM_STRUCTURAL_SENSITIVITY",
    "workbook_formula_error_scan": "PASS",
    "notebook_json_validation": "PASS",
    "raw_zip_integrity": "PASS",
    "reporting_lock": "Smoke-test intervals, CEAC and CEAF are technical outputs; formal probabilistic results require the 10,000-draw run",
}
(ROOT / "FINAL_QC_MANIFEST_v1.3.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

excluded = {"FILE_MANIFEST_v1.3.csv"}
rows = []
for path in sorted(p for p in ROOT.rglob("*") if p.is_file() and p.name not in excluded):
    rows.append({
        "relative_path": str(path.relative_to(ROOT)),
        "size_bytes": path.stat().st_size,
        "sha256": sha256(path),
    })
pd.DataFrame(rows).to_csv(ROOT / "FILE_MANIFEST_v1.3.csv", index=False, encoding="utf-8-sig")
print(json.dumps(manifest, ensure_ascii=False, indent=2))
