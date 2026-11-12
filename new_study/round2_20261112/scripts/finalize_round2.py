"""Finish second-round integrity manifest and preservation gate; no model code."""
import csv
import hashlib
import json
import subprocess
from pathlib import Path

root=Path(__file__).resolve().parents[3]
round2=root/'new_study/round2_20261112'
report_path=round2/'checks/validation_round2.json'
report=json.loads(report_path.read_text(encoding='utf-8'))
git=subprocess.run(['git','diff','--name-only','94e893ab90bfab75866eeff19d501afdf76739b4','--','new_study/round1_20261112','data','src','code','results'],cwd=root,text=True,capture_output=True,check=True)
report['checks']['round1_and_legacy_paths_unchanged']=(git.stdout.strip()=='')
needed=['README.md','reports/HANDOFF_ROUND2.md','reports/WORK_DECISIONS_IMPLEMENTATION.md','registers/work_decisions.csv','registers/population_input_whitelist_v1.csv','registers/pa_age_crosswalk_v1.csv','registers/pa_2025_model_baseline_v1.csv','registers/pa_scenario_protocol_v1.csv','registers/rr_admission_work_v1.csv','registers/disease_endpoint_admission_work_v1.csv','registers/gbd_input_whitelist_v1.csv','registers/gbd_endpoint_source_gate_v1.csv','registers/gbd_download_requirements_v2.csv','registers/hypertension_module_protocol.csv','registers/cost_health_quantity_linkage_v1.csv','registers/cost_overlap_rules_v1.csv','registers/treatment_coverage_requirements.csv','registers/price_conversion_requirements.csv','registers/round2_actionable_gaps.csv','checks/validation_round2.json']
report['checks']['required_files_present']=all((round2/p).is_file() for p in needed)
report['passed']=sum(report['checks'].values());report['total']=len(report['checks'])
with report_path.open('w',encoding='utf-8',newline='\n') as f:f.write(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
manifest=round2/'registers/file_manifest_sha256_v2.csv'
with manifest.open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.DictWriter(f,fieldnames=['path','bytes','sha256'],lineterminator='\n');w.writeheader()
 for p in sorted(round2.rglob('*')):
  if p.is_file() and p!=manifest:
   w.writerow(dict(path=p.relative_to(root).as_posix(),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
print(f"{report['passed']}/{report['total']} checks; {sum(1 for _ in csv.DictReader(manifest.open(encoding='utf-8-sig')))} files hashed")
if report['passed']!=report['total']:raise SystemExit(1)
