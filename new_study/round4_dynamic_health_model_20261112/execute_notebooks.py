"""Execute simple reproducible notebooks using Python stdlib, without Jupyter."""
import contextlib
import io
import json
import sys
from pathlib import Path

here=Path(__file__).resolve().parent
sys.path.insert(0,str(here))
status=[]
for path in sorted((here/'notebooks').glob('*.ipynb')):
    notebook=json.loads(path.read_text(encoding='utf-8'))
    space={'__name__':'__notebook__'}
    output=io.StringIO()
    try:
        with contextlib.redirect_stdout(output):
            for cell in notebook['cells']:
                if cell['cell_type']=='code':exec(''.join(cell['source']),space)
        result='PASS'
    except Exception as error:
        result='FAIL: '+repr(error)
    status.append({'notebook':path.name,'status':result,'stdout':output.getvalue()})
    print(path.name,result)
(here/'logs'/'notebook_execution.json').write_bytes((json.dumps(status,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
if any(r['status']!='PASS' for r in status):raise SystemExit(1)
