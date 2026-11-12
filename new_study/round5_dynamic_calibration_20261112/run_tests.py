"""Run untouched round-four tests and round-five tests in isolated processes."""
import json
import os
import re
import subprocess
import sys
from src.common import R5,ROOT,write_json

results=[]
for name,folder,pattern in [('legacy_round4',ROOT/'new_study/round4_dynamic_health_model_20261112','test_dynamic.py'),('new_round5',R5,'test_round5.py')]:
    env=dict(os.environ,PYTHONPATH=str(folder),PYTHONDONTWRITEBYTECODE='1')
    output=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-p',pattern,'-v'],cwd=folder,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace')
    text=output.stdout+output.stderr
    (R5/'logs'/f'{name}_tests.log').write_text(text,encoding='utf-8',newline='\n')
    matched=re.search(r'Ran (\d+) tests?',text);count=int(matched.group(1)) if matched else 0
    cases=[]
    for line in text.splitlines():
        if line.startswith('test_') and ' ... ' in line:
            test,status=line.rsplit(' ... ',1);cases.append(dict(check_id=name+':'+test.split(' ')[0],status='PASS' if status=='ok' else 'FAIL',detail=line))
    results.append(dict(suite=name,count=count,status='PASS' if output.returncode==0 and count>0 else 'FAIL',returncode=output.returncode,cases=cases))
    print(name,count,results[-1]['status'],flush=True)
write_json(R5/'logs/test_results.json',results)
ids=[c['check_id'] for r in results for c in r['cases']]
if len(ids)!=len(set(ids)) or any(r['status']!='PASS' for r in results) or results[0]['count']!=48 or results[1]['count']<22:raise SystemExit(1)
