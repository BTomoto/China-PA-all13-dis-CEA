"""Check files and base preservation, then write SHA256 manifest."""
import csv,hashlib,json,subprocess
from collections import Counter
from pathlib import Path
root=Path(__file__).resolve().parents[3]
out=root/'new_study/round2_target_prep_20261112'
base='67addc23590666461ea065294c382da5a72e7287'
report_path=out/'checks/validation_target_prep.json'
report=json.loads(report_path.read_text(encoding='utf-8'))
def check(name,passed,evidence):return dict(id=name,status='PASS' if passed else 'FAIL',evidence=evidence)
for c in report['checks']:
 if c['id']=='branch_base':
  p=subprocess.run(['git','rev-parse','--abbrev-ref','HEAD'],cwd=root,text=True,capture_output=True,check=True)
  b=subprocess.run(['git','merge-base','HEAD',base],cwd=root,text=True,capture_output=True,check=True)
  c.update(status='PASS' if p.stdout.strip()==report['branch'] and b.stdout.strip()==base else 'FAIL',evidence=f"branch={p.stdout.strip()}; merge_base={b.stdout.strip()}")
 if c['id']=='prior_round_files_preserved':
  p=subprocess.run(['git','diff','--name-only',base,'--','new_study/round1_20261112','new_study/round2_20261112'],cwd=root,text=True,capture_output=True,check=True)
  c.update(status='PASS' if not p.stdout.strip() else 'FAIL',evidence='No tracked path differences in first/second round' if not p.stdout.strip() else p.stdout.strip())
needed=['README.md','reports/AUDIT_REVISION.md','reports/EVIDENCE_EXTRACTION.md','reports/HANDOFF_TARGET_PREP.md','raw/Jia2018_fulltext.pdf','registers/audit_revision_log.csv','registers/who_policy_indicator_evidence.csv','registers/pa_2010_reference_evidence.csv','registers/target_baseline_comparability.csv','registers/scenario_interface_v1.csv','registers/work_pending_target_decisions.csv','registers/exposure_crosswalk_ci_v2.csv','registers/population_provenance_v2.csv','registers/rr_admission_audit_v2.csv','registers/endpoint_admission_audit_v2.csv','registers/cost_admission_audit_v2.csv','registers/gbd_old_value_reconstruction_requests.csv','registers/gbd_new_model_download_requests.csv','registers/gbd_new_model_detailed_requests.csv','registers/rand_ding_evidence.csv','registers/ding_china_published_outputs.csv','registers/jia_cost_verification.csv','registers/incidence_to_other_outcomes_requirements.csv','checks/validation_target_prep.json']
report['checks'].append(check('required_files_exist',all((out/x).is_file() for x in needed),f'{len(needed)} required paths'))
pdf=(out/'raw/Jia2018_fulltext.pdf').read_bytes()
report['checks'].append(check('Jia_pdf_signature',pdf.startswith(b'%PDF-') and len(pdf)>100000,f'PDF signature; {len(pdf)} bytes'))
def rd(name):
 with (out/'registers'/name).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
pop=rd('population_provenance_v2.csv');cross=rd('exposure_crosswalk_ci_v2.csv');scenario=rd('scenario_interface_v1.csv');rr=rd('rr_admission_audit_v2.csv');ep=rd('endpoint_admission_audit_v2.csv')
report['checks'].append(check('population_2025_total',sum(int(x['population_persons']) for x in pop if x['year']=='2025')==1113252964,'2025 20+ sex-age sum = 1,113,252,964'))
report['checks'].append(check('population_source_columns',len(pop)==884 and all(x['source_population_column']==('PopMale' if x['sex']=='Male' else 'PopFemale') for x in pop),'884 rows mapped to official sex column'))
report['checks'].append(check('exposure_CI_and_shared_id',len(cross)==34 and all(x['lower_95'] and x['upper_95'] and x['shared_parameter_id'] for x in cross) and len(set(x['shared_parameter_id'] for x in cross))==12,'34 mapped cells share 12 sex/coarse-age source parameters'))
report['checks'].append(check('no_numeric_target_released',all(not x['numeric_target'] and not x['attainment_gap'] for x in scenario),'Target numeric cells and attainment gaps empty'))
report['checks'].append(check('no_model_ready',all(x['model_ready']=='NO' for x in rr) and all(x['model_ready'] in ('NO','NOT_APPLICABLE') for x in ep),'No RR or endpoint model_ready'))
report['checks'].append(check('hypertension_four_NA',{x['endpoint'] for x in ep if x['component_id']=='hypertension' and x['model_ready']=='NOT_APPLICABLE'}=={'Deaths','YLL','YLD','DALY'},'Hypertension death/YLL/YLD/DALY N/A'))
report['status_counts']=dict(Counter(x['status'] for x in report['checks']))
with report_path.open('w',encoding='utf-8',newline='\n') as f:f.write(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
manifest=out/'registers/file_manifest_sha256.csv'
with manifest.open('w',encoding='utf-8-sig',newline='\n') as f:
 w=csv.DictWriter(f,fieldnames=['path','bytes','sha256'],lineterminator='\n');w.writeheader()
 for p in sorted(out.rglob('*')):
  if p.is_file() and p!=manifest:
   w.writerow(dict(path=p.relative_to(root).as_posix(),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
print(report['status_counts'], 'files_hashed',sum(1 for _ in csv.DictReader(manifest.open(encoding='utf-8-sig'))))
if any(c['status']=='FAIL' for c in report['checks'] if c['id'] in ('branch_base','prior_round_files_preserved','required_files_exist','Jia_pdf_signature','population_2025_total','population_source_columns','exposure_CI_and_shared_id','no_numeric_target_released','no_model_ready','hypertension_four_NA')):raise SystemExit(1)
