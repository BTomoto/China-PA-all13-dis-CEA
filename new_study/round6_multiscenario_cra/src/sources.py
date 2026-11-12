import csv,io,math,re,zipfile
from collections import defaultdict
from pypdf import PdfReader
from .common import ROOT,R6,AGES,DISEASES,InputBlocked,read_csv

POP='new_study/round2_20261112/registers/population_input_whitelist_v1.csv'
PA='new_study/round2_target_prep_20261112/registers/exposure_crosswalk_ci_v2.csv'
KYU='new_study/round1_20261112/raw/pmc_cloud/PMC4979358/kyuh031211.ww4_2kb.pdf'
RAW='new_study/round1_20261112/handoff/continuation/source_data/gbd/IHME-GBD_2023_DATA-85af7c45-1.zip'

def population_exposure():
    pop=read_csv(ROOT/POP);pa=read_csv(ROOT/PA)
    exposures={(r['sex'],r['age_group']):r for r in pa}
    if len(exposures)!=34 or len(pop)!=884:raise InputBlocked('population/exposure dimensions')
    group=defaultdict(list)
    for r in pop:
        sex,age=r['sex'],r['age_group'];n=int(r['population_persons']);p=float(exposures[(sex,age)]['p_inactive'])
        group[(int(r['year']),sex,'95+' if age in ['95-99','100+'] else age)].append((n,p,exposures[(sex,age)]))
    out=[]
    for (year,sex,age),items in sorted(group.items()):
        n=sum(x[0] for x in items);p=sum(x[0]*x[1] for x in items)/n
        if len({x[2]['shared_parameter_id'] for x in items})!=1:raise InputBlocked('inconsistent merged exposure source')
        out.append(dict(year=year,sex=sex,age=age,population=n,p_inactive=p,lower_95=float(items[0][2]['lower_95']),upper_95=float(items[0][2]['upper_95']),shared_parameter_id=items[0][2]['shared_parameter_id'],source_age=items[0][2]['source_age_group']))
    if len(out)!=832 or len({(r['year'],r['sex'],r['age']) for r in out})!=832:raise InputBlocked('grouped input dimensions')
    return out

def gbd_rates():
    with zipfile.ZipFile(ROOT/RAW) as z:
        name=next(n for n in z.namelist() if n.endswith('.csv'));raw=list(csv.DictReader(io.TextIOWrapper(z.open(name),encoding='utf-8-sig')));citation=z.read('citation.txt').decode('utf-8-sig')
    rates={};numbers={}
    for r in raw:
        age=r['age_name'].removesuffix(' years')
        if r['year']!='2023' or age not in AGES or r['measure_name']!='Incidence':continue
        if r['cause_name'] not in DISEASES or r['sex_name'] not in ['Male','Female'] or r['location_name']!='China' or r['population_group_name']!='All Population':raise InputBlocked('GBD scope')
        key=(DISEASES[r['cause_name']],r['sex_name'],age)
        table=rates if r['metric_name']=='Rate' else numbers if r['metric_name']=='Number' else None
        if table is None or key in table:raise InputBlocked('GBD duplicate/metric')
        v,lo,hi=[float(r[k]) for k in ['val','lower','upper']]
        if not 0<=lo<=v<=hi:raise InputBlocked('GBD UI')
        table[key]=(v,lo,hi)
    if len(rates)!=64 or set(rates)!=set(numbers):raise InputBlocked('GBD age-sex-cause completeness')
    for sex in ['Male','Female']:
        for age in AGES:
            implied=[numbers[(d,sex,age)][0]/rates[(d,sex,age)][0]*1e5 for d in ['IHD','IS']]
            if not math.isclose(*implied,rel_tol=1e-8):raise InputBlocked('GBD implied population')
    return rates,dict(source_path=RAW,citation=citation.strip(),internal_csv=name,raw_rows=len(raw),rate_rows=len(rates),status='SOURCE_VERIFIED_MODEL_ESTIMATE')

def extract_continuous_rr():
    reader=PdfReader(ROOT/KYU);rows=[]
    for disease in ['IHD','IS']:
        rows.append(dict(disease=disease,dose=0,estimate=1.,lower='',upper='',reference='zero total activity',source_page=79,source_table='F',source_file=KYU,source_status='SOURCE_VERIFIED',admission_status='BLOCKED_ENDPOINT_ALIGNMENT'))
    for page in [78,79]:
        for line in reader.pages[page].extract_text().splitlines():
            match=re.match(r'^([\d,]+)\s+(.+)',line.strip())
            if not match or '(' not in match[2]:continue
            dose=int(match[1].replace(',',''))
            if dose<600 or dose>30600 or dose%600:continue
            cells=re.findall(r'([\d.][\d.\s]*)\(([^)]+)\)',match[2])
            if len(cells)!=5:raise InputBlocked('Kyu Table F cell parsing')
            for disease,index in [('IHD',3),('IS',4)]:
                point=float(re.sub(r'\s','',cells[index][0]));lo,hi=[float(re.sub(r'\s','',v)) for v in cells[index][1].split(',')]
                if not 0<lo<=point<=hi:raise InputBlocked('Kyu Table F UI')
                rows.append(dict(disease=disease,dose=dose,estimate=point,lower=lo,upper=hi,reference='zero total activity',source_page=page+1,source_table='F',source_file=KYU,source_status='SOURCE_VERIFIED',admission_status='BLOCKED_ENDPOINT_ALIGNMENT'))
    if len(rows)!=104 or len({(r['disease'],r['dose']) for r in rows})!=104:raise InputBlocked('Kyu grid missing/duplicate')
    return rows

def category_rr():
    rows=read_csv(ROOT/'new_study/round4_dynamic_health_model_20261112/inputs/kyu_category_rr.csv')
    return {d:[float(r['rr_vs_inactive']) for r in rows if r['disease']==d] for d in ['IHD','IS']}
