"""Measured completion log, separate clinical gates, reproducibility manifest."""
import json,platform,subprocess,sys,xml.etree.ElementTree as ET
from datetime import datetime,timezone
from src.common import R6,ROOT,read_csv,write_csv,write_json,sha,config,verify_old_inputs

test=json.loads((R6/'logs/test_results.json').read_text(encoding='utf-8'))
notebooks=json.loads((R6/'logs/notebook_execution.json').read_text(encoding='utf-8'))
report=json.loads((R6/'results/model_validation_report.json').read_text(encoding='utf-8'))
if test['status']!='PASS' or len(notebooks)!=5 or any(n['status']!='PASS' for n in notebooks):raise SystemExit('software checks failed')
locks=verify_old_inputs()
changed=subprocess.check_output(['git','diff','--name-only',config()['baseline_commit'],'--','new_study'],cwd=ROOT,text=True).splitlines()
old_changes=[p for p in changed if not p.startswith('new_study/round6_multiscenario_cra/')]
if old_changes:raise SystemExit('old round files changed')
register=read_csv(R6/'inputs/parameter_register.csv')
if len({r['parameter_id'] for r in register})!=len(register):raise SystemExit('duplicate parameter ID')
for name in ['incidence_age_sex_year_scenario.csv','pif_age_sex_disease_scenario.csv']:
    rows=read_csv(R6/'results'/name)
    keys=[tuple(r[k] for k in ['year','sex','age','disease','scenario','path']) for r in rows]
    if len(keys)!=len(set(keys)):raise SystemExit('duplicate output keys')
untracked=subprocess.check_output(['git','ls-files','--others','--exclude-standard'],cwd=ROOT,text=True).splitlines()
unrelated=[p for p in untracked if not p.startswith('new_study/round6_multiscenario_cra/')]
raw=[]
for p in sorted((R6/'raw').glob('*')):
    if not p.is_file():continue
    valid=True
    if p.suffix=='.xml':
        try:ET.parse(p)
        except ET.ParseError:valid=False
    if p.suffix=='.pdf':valid=p.read_bytes().startswith(b'%PDF-')
    raw.append(dict(path=str(p),bytes=p.stat().st_size,sha256=sha(p),validation='PASS' if valid else 'FAIL',git_policy='LOCAL_ONLY_PUBLIC_SOURCE' if p.suffix in ['.xml','.pdf','.html'] else 'COMMIT_METADATA_ONLY'))
if any(r['validation']=='FAIL' for r in raw):raise SystemExit('invalid local source artifact')
checks=[dict(check_id='locked_prior_inputs',category='FILE_INTEGRITY',status='PASS',evidence=f'{len(locks)} SHA checks'),dict(check_id='old_rounds_unchanged',category='FILE_INTEGRITY',status='PASS',evidence=old_changes),dict(check_id='parameter_and_output_key_uniqueness',category='FILE_INTEGRITY',status='PASS',evidence='Unique IDs/Cartesian output keys checked'),dict(check_id='current_cra_software',category='SOFTWARE',status='PASS',evidence=f"{test['tests_run']} tests"),dict(check_id='standard_jupyter_execution',category='SOFTWARE',status='PASS',evidence='5 notebooks, nbclient + real ipykernel'),dict(check_id='clinical_rr_gbd_endpoint_alignment',category='SCIENTIFIC_ADMISSION',status='NOT_CHECKED',evidence='No separately audited incidence-only RR curve; GBD2023 primary disease appendix not acquired'),dict(check_id='china_full_exposure_distribution',category='SCIENTIFIC_ADMISSION',status='NOT_CHECKED',evidence='Only inactivity margins available; no individual or full category distribution'),dict(check_id='universal_R3_dominates_R2_requirement',category='SPECIFICATION',status='FAIL',evidence='550 maps to660 underR2 and600 underR3; formula contradicts universal rank'),dict(check_id='other_outcome_risk_mapping',category='SCIENTIFIC_ADMISSION',status='NOT_CHECKED',evidence='Endpoint mapping unadmitted'),dict(check_id='natural_history_and_economic_execution',category='SCOPE',status='NOT_APPLICABLE',evidence='No such module imported; current execution list contains CRA only')]
report.update(current_tests={'run':test['tests_run'],'passed':test['tests_run'],'failed':0},prior_tests={'count':85,'status':'HISTORICAL_NOT_EXECUTED_THIS_ROUND'},notebooks={'executed':5,'passed':5,'engine':'nbclient + real ipykernel'},parameter_rows=len(register),checks=checks,check_count=len(checks),file_integrity_status='PASS',scientific_admission_status='BLOCKED',specification_conflict_count=1,local_public_sources=raw,user_unrelated_untracked_preserved=unrelated)
write_json(R6/'results/model_validation_report.json',report)
write_json(R6/'logs/local_run_log.json',dict(worktree=str(ROOT),branch=config()['branch'],base=config()['baseline_commit'],local_head_at_run=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),utc=datetime.now(timezone.utc).isoformat(),python=sys.version,platform=platform.platform(),commands=['build_round6.py','run_tests.py','execute_notebooks.py','finalize_run.py'],status=report['analysis_status'],tests=report['current_tests'],notebooks=notebooks,randomness='none; deterministic weighted transformations',raw_source_files=raw,unrelated_untracked_preserved=unrelated))
env=subprocess.check_output([sys.executable,'-m','pip','freeze'],text=True)
(R6/'logs/environment_lock.txt').write_text(env,encoding='utf-8',newline='\n')
source_rows=[]
for r in locks:source_rows.append(dict(path=r['path'],sha256=r['sha256'],bytes=(ROOT/r['path']).stat().st_size,role='PRIOR_INPUT_READ_ONLY'))
for r in raw:source_rows.append(dict(path=r['path'],sha256=r['sha256'],bytes=r['bytes'],role=r['git_policy']))
write_csv(R6/'logs/input_integrity_manifest.csv',source_rows)
for p in [R6/'reports/HANDOFF_ROUND6.md']:
    content=p.read_text(encoding='utf-8').split('\n<!-- ACTUAL_CHECKS -->')[0]
    content+=f"\n<!-- ACTUAL_CHECKS -->\nCurrentCRA tests:{test['tests_run']}/{test['tests_run']}; prior85 are historical, not rerun; standard notebooks5/5; checks{len(checks)}; scientific admissionBLOCKED; specification conflict1.\n"
    content+='\nUncommitted scientific source artifact: raw/GBD2023_nonfatal_fulltext.xml is intentionally LOCAL_ONLY_PUBLIC_SOURCE (hash in logs/input_integrity_manifest.csv). RAND and GBD appendix PDFs were not obtained and are not claimed as archived. Existing ignored ZIPs remain in their original paths. Unrelated user untracked files preserved: '+str(unrelated)+'. Git-tracked round6 changes are committed separately; Python environment, runtime kernels and rendered evidence-page previews are excluded.\n'
    p.write_text(content,encoding='utf-8',newline='\n')
manifest=[]
for p in sorted(R6.rglob('*')):
    if not p.is_file() or '.runtime' in p.parts or '__pycache__' in p.parts or p.name=='sha256_manifest.csv' or p.suffix in ['.pdf','.xml','.html']:continue
    manifest.append(dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),bytes=p.stat().st_size))
write_csv(R6/'sha256_manifest.csv',manifest)
if any(sha(ROOT/r['path'])!=r['sha256'] for r in read_csv(R6/'sha256_manifest.csv')):raise SystemExit('manifest verification failure')
print(json.dumps(dict(status=report['analysis_status'],current_tests=report['current_tests'],standard_notebooks='5/5',file_manifest_rows=len(manifest),clinical_effects='BLOCKED_ENDPOINT_ALIGNMENT',specification='R3_R2_UNIVERSAL_ORDERING_CONFLICT'),indent=2))
