"""Audit the collected data. This script never runs the health/CEA/PSA model.

Usage from repository root: python new_study/scripts/audit_inputs.py
Requires openpyxl for read-only XLSX inspection.
"""
import csv
import hashlib
import json
import math
from pathlib import Path
from collections import Counter, defaultdict
import openpyxl

ROOT = Path(__file__).resolve().parents[2]
NEW = ROOT / 'new_study'
OLD = ROOT / 'legacy_excluded'
errors = []
checks = []

def check(label, ok, detail):
    checks.append({'check': label, 'passed': bool(ok), 'detail': detail})
    if not ok:
        errors.append(label)

def rows(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

def same(a, b):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return math.isclose(a, b, rel_tol=1e-13, abs_tol=1e-12)
    return a == b

old_path = OLD / 'data/Public_model_inputs.xlsx'
new_path = NEW / 'data/New_study_inputs.xlsx'
check('old_workbook_sha256', hashlib.sha256(old_path.read_bytes()).hexdigest() ==
      'e880cd9998e3c600454d8ad001fa8a374989047d762ec0b09649bccbb29bb967', 'Old workbook bytes unchanged')
old = openpyxl.load_workbook(old_path, read_only=True, data_only=False)
new = openpyxl.load_workbook(new_path, read_only=True, data_only=False)
reused = ['未来人口','历史人口','身体活动水平','疾病映射','RR原始登记','二分类RR','GBD疾病负担','GBD病例','高血压参数','疾病单位成本']
for name in reused:
    aa, bb = list(old[name].values), list(new[name].values)
    ok = len(aa) == len(bb) and all(len(a)==len(b) and all(same(x,y) for x,y in zip(a,b)) for a,b in zip(aa,bb))
    check('retained_values_'+name, ok, f'{len(aa)-1} rows compared')
check('new_workbook_sheets', len(new.sheetnames)==31, new.sheetnames)
check('no_policy_sheets_in_new_workbook', not any(n in new.sheetnames for n in ['政策情景','政策效应登记','政策年度成本','长期成本情景','宏观及支付参数','GDP文献基准']), 'Full legacy workbook is archived separately')
registry_map = {
 'PA观测证据':'pa_observed_evidence.csv', 'RR证据核验':'rr_evidence_register.csv',
 '医疗费用证据':'medical_cost_evidence_register.csv', '人口细年龄':'wpp_fine_age.csv',
 '人口源登记':'population_source_manifest.csv', '人口逐层核验':'population_reconciliation.csv',
 '基线分母核验':'baseline_denominator_audit.csv', 'GBD源登记':'gbd_source_manifest.csv',
 'GBD逐行核验':'gbd_value_reconciliation.csv', 'GBD覆盖':'gbd_coverage.csv',
 'GBD恢复原始':'gbd_recovered_raw.csv', 'RR准入登记':'rr_admission_register.csv',
 '价格源登记':'price_conversion_register.csv', '结局映射核验':'outcome_mapping_register.csv',
 '研究协议待定项':'scenario_protocol.csv', '自然史与滞后缺口':'disease_transition_and_lag_requirements.csv',
 '不确定性登记':'uncertainty_register.csv', '数据缺口进度':'data_gaps_status.csv', '核验结果':'data_qc.csv'
}
for sheet, filename in registry_map.items():
    raw=rows(NEW/'registers'/filename)
    vals=list(new[sheet].values)
    headers=list(vals[0])[:len(raw[0])]
    ok=len(vals)-1==len(raw)
    for row, source in zip(vals[1:],raw):
        for h,value in zip(headers,row):
            ref=source[h]
            if isinstance(value,bool): match=ref==str(value)
            elif isinstance(value,(int,float)):
                try:match=math.isclose(value,float(ref),rel_tol=1e-13,abs_tol=1e-12)
                except ValueError:match=False
            else:match=ref==('' if value is None else value)
            ok=ok and match
    check('csv_xlsx_'+sheet,ok,f'{len(raw)} records')
for r in rows(NEW/'registers/gbd_source_manifest.csv'):
    if r['status']=='RECOVERED':
        p=NEW/'source_data/gbd'/r['source_file']
        check('raw_GBD_hash_'+r['source_file'], hashlib.sha256(p.read_bytes()).hexdigest()==r['sha256'], 'Source ZIP hash matches register')
wp=rows(NEW/'registers/wpp_fine_age.csv')
aggregates=defaultdict(float)
for r in wp:
    end_prev=float(r['end_previous_year_thousand']);end_current=float(r['end_current_year_thousand'])
    pop=(end_prev+end_current)*500
    check_label=(r['variant'],int(r['year']),r['sex'],'70+' if int(r['age_group'].split('-')[0].rstrip('+'))>=70 else r['age_group'])
    aggregates[check_label]+=pop
check('wpp_fine_age_formula',all(math.isclose(float(r['population']),(float(r['end_previous_year_thousand'])+float(r['end_current_year_thousand']))*500,abs_tol=1e-6) for r in wp),f'{len(wp)} fine-age rows')
legacy_pop=list(old['未来人口'].values);headers=legacy_pop[0]
matches=0
for row in legacy_pop[1:]:
    r=dict(zip(headers,row)); key=(r['variant'],r['year'],r['sex'],r['age_group'])
    matches+=abs(aggregates[key]-r['population'])<1
check('wpp_reconstructed_1716',matches==1716,f'{matches}/1716')
gbdcounts=Counter(r['status'] for r in rows(NEW/'registers/gbd_value_reconciliation.csv'))
check('gbd_reconciliation_counts',gbdcounts=={'DIRECT_MATCH':12296,'POINT_ONLY_MATCH':1184,'INTERVAL_METHOD_DIFF':32,'SOURCE_NOT_RECOVERED':10068},dict(gbdcounts))
rrs=new['RR证据核验'];cached=openpyxl.load_workbook(new_path,read_only=True,data_only=True)['RR证据核验']
formulas_ok=True
for r in range(2,17):
    for c,den in [(16,4),(17,6),(18,5)]:
        value=cached.cell(r,c).value
        formulas_ok &= rrs.cell(r,c).data_type=='f' and value is not None and math.isclose(value,1/rrs.cell(r,den).value,rel_tol=1e-12)
check('Kyu_inverse_formulas_and_caches',formulas_ok,'15 categorical estimates; reverse lower/upper correctly')
result={'data_preparation_checks_passed':not errors,'model_ready':False,
        'scientific_gaps_closed':False,'health_CEA_PSA_executed':False,
        'checks':checks,'errors':errors}
(NEW/'validation_report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps({'passed':not errors,'checks':len(checks),'errors':errors,'model_ready':False},ensure_ascii=False))
if errors:raise SystemExit(1)
