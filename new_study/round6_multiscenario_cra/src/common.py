import csv,hashlib,json
from pathlib import Path

R6=Path(__file__).resolve().parents[1]
ROOT=R6.parents[1]
AGES=[f'{a}-{a+4}' for a in range(20,95,5)]+['95+']
DISEASES={'Ischemic heart disease':'IHD','Ischemic stroke':'IS'}
VARIANTS=[('B0','baseline'),('P15','gradual_2030')]+[(s,p) for s in ['R1','R2','R3'] for p in ['immediate_2025','common_2030']]

class InputBlocked(RuntimeError):pass

def read_csv(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def write_csv(path,rows,fields=None):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields or list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)

def write_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8',newline='\n')

def config():return json.loads((R6/'config/scenarios.yaml').read_text(encoding='utf-8'))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def verify_old_inputs():
    locks=json.loads((R6/'config/source_lock.json').read_text(encoding='utf-8'))
    rows=[]
    for path,expected in locks.items():
        actual=sha(ROOT/path)
        if actual!=expected:raise InputBlocked('BLOCKED_INPUT: '+path)
        rows.append(dict(path=path,sha256=actual,status='PASS'))
    return rows
