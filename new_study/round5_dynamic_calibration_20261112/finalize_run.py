"""Record measured software checks separately from scientific admission gates."""
import csv
import json
import platform
import subprocess
import sys
from datetime import datetime,timezone
from src.common import R5,ROOT,config,read_csv,sha,write_csv,write_json

tests=json.loads((R5/'logs/test_results.json').read_text())
notebooks=json.loads((R5/'logs/notebook_execution.json').read_text())
report=json.loads((R5/'results/model_validation_report.json').read_text())
summary=json.loads((R5/'calibration_summary.json').read_text())
if any(r['status']!='PASS' for r in tests) or len(notebooks)!=5 or any(r['status']!='PASS' for r in notebooks):
    raise SystemExit('Software tests/notebooks failed')
base=config()['baseline_commit']
changes=subprocess.check_output(['git','diff',base,'--name-only'],cwd=ROOT,text=True).splitlines()
old_changes=[p for p in changes if p.startswith('new_study/') and not p.startswith('new_study/round5_dynamic_calibration_20261112/')]
checks=[dict(check_id='cross_export_population',category='INPUT_INTEGRITY',status=report['cross_export_population'],evidence='32 cross-export sex-age reconciliations'),dict(check_id='standard_jupyter_execution',category='SOFTWARE',status='PASS',evidence='5 real nbclient/ipykernel executions'),dict(check_id='previous_round_files_unchanged',category='FILE_INTEGRITY',status='FAIL' if old_changes else 'PASS',evidence=old_changes),dict(check_id='standard_life_table_validation',category='SCIENTIFIC_EVIDENCE',status='NOT_CHECKED',evidence='GBD standard life table unavailable'),dict(check_id='complete_final_query_screenshot',category='PROVENANCE',status='NOT_CHECKED',evidence='Only incomplete early screenshot exists; not used'),dict(check_id='cost_CEA_PSA_execution',category='SCOPE',status='NOT_APPLICABLE',evidence='Not part of run_local.ps1 or invoked round5 modules')]
for name,spec in config()['raw_inputs'].items():
    checks.append(dict(check_id='raw_sha_'+name,category='FILE_INTEGRITY',status='PASS' if sha(ROOT/spec['path'])==spec['sha256'] else 'FAIL',evidence=spec['path']))
for group in summary['groups']:
    checks.append(dict(check_id='joint_fit_'+group['disease']+'_'+group['sex'],category='SCIENTIFIC_EVIDENCE',status=group['status'],evidence=dict(max_relative_error=group['maximum_relative_error'],rms_relative_error=group['rms_relative_error'])))
ids=[r['check_id'] for r in checks]
if len(ids)!=len(set(ids)):raise SystemExit('duplicate check IDs')
if old_changes or any(c['status']=='FAIL' and c['category']!='SCIENTIFIC_EVIDENCE' for c in checks):raise SystemExit('file/input/software check failed')
frozen=subprocess.check_output([sys.executable,'-m','pip','freeze'],text=True)
(R5/'logs/environment_lock.txt').write_text(frozen,encoding='utf-8',newline='\n')
report.update(software_tests={'legacy':tests[0]['count'],'new':tests[1]['count'],'total':sum(t['count'] for t in tests),'failed':0},standard_notebooks={'count':len(notebooks),'passed':5},checks=checks,check_count=len(checks),scientific_failures=sum(c['status']=='FAIL' and c['category']=='SCIENTIFIC_EVIDENCE' for c in checks),file_integrity_status='PASS',scientific_admission_status='PASS' if summary['all_groups_pass'] else 'FAIL')
write_json(R5/'results/model_validation_report.json',report)
write_json(R5/'logs/local_run_log.json',dict(local_worktree=str(ROOT),branch=config()['branch'],baseline=base,local_head_at_execution=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),end_time_utc=datetime.now(timezone.utc).isoformat(),python=sys.version,platform=platform.platform(),status=report['status'],tests=report['software_tests'],notebooks=notebooks,execution_commands=['build_round5.py','run_tests.py','execute_notebooks.py','finalize_run.py'],old_round_changes=old_changes,randomness='none; deterministic starts'))
for path in [R5/'reports/HANDOFF_ROUND5.md',R5/'reports/CALIBRATION_REVIEW.md']:
    content=path.read_text(encoding='utf-8').split('\n<!-- ACTUAL_CHECKS -->')[0]
    content+='\n<!-- ACTUAL_CHECKS -->\nSoftware tests: '+str(report['software_tests'])+'; standard notebooks: 5/5; evidence/file checks: '+str(len(checks))+'; scientific failures: '+str(report['scientific_failures'])+'.\n'
    path.write_text(content,encoding='utf-8',newline='\n')
files=[]
for path in sorted(R5.rglob('*')):
    if not path.is_file() or '.runtime' in path.parts or '__pycache__' in path.parts or path.name=='sha256_manifest.csv':continue
    files.append(dict(relative_path=path.relative_to(ROOT).as_posix(),sha256=sha(path),bytes=path.stat().st_size))
for path in [ROOT/'requirements.txt',ROOT/'run_local.ps1',ROOT/'README_LOCAL_RUN.md']:
    files.append(dict(relative_path=path.relative_to(ROOT).as_posix(),sha256=sha(path),bytes=path.stat().st_size))
write_csv(R5/'sha256_manifest.csv',files)
assert all(sha(ROOT/r['relative_path'])==r['sha256'] for r in read_csv(R5/'sha256_manifest.csv'))
print(json.dumps(dict(status=report['status'],tests=report['software_tests'],standard_notebooks='5/5',manifest_files=len(files),scientific_gate=report['scientific_admission_status']),indent=2))
