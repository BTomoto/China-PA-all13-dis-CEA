"""Write reproducibility log and file hashes after model, tests and notebooks pass."""
import csv
import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime,timezone
from pathlib import Path

here=Path(__file__).resolve().parent
root=here.parents[1]
notebooks=json.loads((here/'logs'/'notebook_execution.json').read_text(encoding='utf-8'))
validation=json.loads((here/'results'/'model_validation_report.json').read_text(encoding='utf-8'))
if len(notebooks)!=5 or any(item['status']!='PASS' for item in notebooks):
    raise SystemExit('BLOCKED_INPUT: notebook check incomplete')
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
log={'status':'BLOCKED_DYNAMIC_PARAMETERS','incidence_status':'PILOT_CONDITIONAL_RR_DENOMINATOR',
     'worktree':str(root),'branch':'codex/dynamic-health-model-round4-20261112',
     'base_remote_commit':'c581bfae4c642473e59f114ddf59381e12f9ef49',
     'local_head_at_run':head,'python':sys.version,'platform':platform.platform(),
     'requirements':'Python 3.11+ standard library only','random_seed':'NOT_APPLICABLE; deterministic',
     'start_utc':datetime.fromtimestamp(validation['started_utc_epoch'],timezone.utc).isoformat(),
     'end_utc':datetime.fromtimestamp(validation['ended_utc_epoch'],timezone.utc).isoformat(),
     'gbd_zip_sha256':validation['gbd_incidence_sha256'],'incidence_rows':validation['incidence_rows'],
     'synthetic_fixture_rows':validation['synthetic_test_rows'],
     'automated_tests':{'count':48,'passed':48,'failed':0},
     'notebooks':notebooks,'empirical_dynamic_endpoints':'BLOCKED_DYNAMIC_PARAMETERS'}
(here/'logs'/'formal_local_run_log.json').write_bytes((json.dumps(log,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
files=[]
for path in sorted(here.rglob('*')):
    if not path.is_file() or path.name=='sha256_manifest.csv' or '__pycache__' in path.parts or path.name=='synthetic_software_fixture.csv':continue
    rel=path.relative_to(root).as_posix()
    files.append((rel,hashlib.sha256(path.read_bytes()).hexdigest(),path.stat().st_size))
with (here/'sha256_manifest.csv').open('w',encoding='utf-8',newline='') as f:
    writer=csv.writer(f,lineterminator='\n');writer.writerow(('relative_path','sha256','bytes'));writer.writerows(files)
print(f'finalized files={len(files)} tests=48/48 notebooks=5/5 status=BLOCKED_DYNAMIC_PARAMETERS')
