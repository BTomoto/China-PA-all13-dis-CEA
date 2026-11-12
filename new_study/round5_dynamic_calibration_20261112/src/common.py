import csv
import hashlib
import json
from pathlib import Path

R5 = Path(__file__).resolve().parents[1]
ROOT = R5.parents[1]
AGES = [f'{a}-{a+4}' for a in range(20, 95, 5)] + ['95+']
CAUSES = {'Ischemic heart disease': 'IHD', 'Ischemic stroke': 'IS', 'All causes': 'ALL'}
YLD = 'YLDs (Years Lived with Disability)'
YLL = 'YLLs (Years of Life Lost)'
DALY = 'DALYs (Disability-Adjusted Life Years)'

class InputBlocked(RuntimeError):
    pass

def config():
    # JSON is a strict subset of YAML 1.2; no second parser/config interpretation.
    return json.loads((R5/'config/dynamic_model_config.yaml').read_text(encoding='utf-8'))

def read_csv(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))

def write_csv(path, rows, fields=None):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',encoding='utf-8',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=fields or list(rows[0]),lineterminator='\n')
        writer.writeheader();writer.writerows(rows)

def write_json(path, obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def frozen_incidence():
    rows=read_csv(ROOT/'new_study/round3_health_model_pilot_20261112/results/incidence_age_sex_2025_2050.csv')
    if len(rows)!=1664 or len({(r['year'],r['sex'],r['age_group'],r['disease']) for r in rows})!=1664:
        raise InputBlocked('BLOCKED_INPUT: frozen incidence dimensions')
    for disease,values in {'IHD':[45531.007,116899.570,547363.017],'IS':[57420.852,143733.241,598423.448]}.items():
        for end,target in zip([2030,2034,2050],values):
            actual=sum(float(r['incident_cases_averted']) for r in rows if r['disease']==disease and int(r['year'])<=end)
            if abs(actual-target)>.001:
                raise InputBlocked('BLOCKED_INPUT: frozen incidence total changed')
    return rows
