"""Read original ZIPs in place; validate raw dimensions and population denominators."""
import csv
import io
import math
import zipfile
from collections import defaultdict
from datetime import datetime,timezone
from .common import AGES,CAUSES,ROOT,InputBlocked,config,read_csv,sha

def load_sources():
    datasets={};audit=[]
    for name,spec in config()['raw_inputs'].items():
        path=ROOT/spec['path']
        if not path.is_file() or sha(path)!=spec['sha256']:
            raise InputBlocked('BLOCKED_INPUT: missing or SHA-mismatched '+str(path))
        with zipfile.ZipFile(path) as archive:
            members=archive.namelist();csvs=[n for n in members if n.lower().endswith('.csv')]
            if len(csvs)!=1 or 'citation.txt' not in members:
                raise InputBlocked('BLOCKED_INPUT: invalid ZIP members')
            rows=list(csv.DictReader(io.TextIOWrapper(archive.open(csvs[0]),encoding='utf-8-sig')))
            citation=archive.read('citation.txt').decode('utf-8-sig').strip()
        dims={field:sorted({r[field] for r in rows}) for field in ['year','cause_name','sex_name','age_name','measure_name','metric_name','location_name','population_group_name']}
        if dims['location_name']!=['China'] or dims['population_group_name']!=['All Population']:
            raise InputBlocked('BLOCKED_INPUT: population scope')
        if dims['sex_name']!=['Female','Male'] or dims['metric_name']!=['Number','Rate']:
            raise InputBlocked('BLOCKED_INPUT: sex/metric dimensions')
        seen=set();data={}
        for r in rows:
            key=tuple(r[x] for x in ['year','cause_name','sex_name','age_name','measure_name','metric_name'])
            if key in seen:raise InputBlocked('BLOCKED_INPUT: duplicate row')
            seen.add(key)
            lo,v,hi=[float(r[x]) for x in ['lower','val','upper']]
            if not all(math.isfinite(x) for x in [lo,v,hi]) or not 0<=lo<=v<=hi:
                raise InputBlocked('BLOCKED_INPUT: point/UI')
            age=r['age_name'].removesuffix(' years')
            if r['year']=='2023' and age in AGES:
                data[(CAUSES[r['cause_name']],r['sex_name'],age,r['measure_name'],r['metric_name'])]=v
        expected_measures={'Incidence'} if name=='incidence' else {'Prevalence','Deaths','YLDs (Years Lived with Disability)','YLLs (Years of Life Lost)','DALYs (Disability-Adjusted Life Years)'}
        expected_causes={'ALL'} if name=='all_cause' else {'IHD','IS'}
        expected={(d,s,a,m,t) for d in expected_causes for s in ['Male','Female'] for a in AGES for m in expected_measures for t in ['Number','Rate']}
        if set(data)!=expected:raise InputBlocked('BLOCKED_INPUT: detailed 2023 Cartesian dimensions')
        datasets[name]=data
        audit.append(dict(dataset=name,local_path=str(path.resolve()),bytes=path.stat().st_size,sha256=sha(path),zip_members=members,citation=citation,row_count=len(rows),detailed_2023_rows=len(data),unique_values=dims,last_modified_utc=datetime.fromtimestamp(path.stat().st_mtime,timezone.utc).isoformat(),audit_time_utc=datetime.now(timezone.utc).isoformat(),access='read_only_in_place',query_screenshot_status='INCOMPLETE_QUERY_SCREENSHOT_NOT_USED'))
    return datasets,audit

def reconcile(datasets):
    wpp=read_csv(ROOT/'new_study/round3_health_model_pilot_20261112/inputs/scenario_age_sex_2025_2050.csv')
    wpp={(r['sex'],r['age_group']):float(r['population']) for r in wpp if r['year']=='2025'}
    for sex in ['Male','Female']:
        wpp[(sex,'95+')]=wpp.pop((sex,'95-99'))+wpp.pop((sex,'100+'))
    out=[]
    for sex in ['Male','Female']:
        for age in AGES:
            populations=[]
            for name,data in datasets.items():
                values=[v/data[(d,s,a,m,'Rate')]*100000 for (d,s,a,m,t),v in data.items() if t=='Number' and s==sex and a==age]
                if not math.isclose(min(values),max(values),rel_tol=1e-8):raise InputBlocked('BLOCKED_INPUT: within-export population disagreement')
                populations.append(sum(values)/len(values))
            absolute=max(populations)-min(populations);relative=absolute/min(populations)
            p=wpp[(sex,age)]
            out.append(dict(sex=sex,age=age,incidence_export_population=populations[0],disease_export_population=populations[1],all_cause_export_population=populations[2],absolute_difference=absolute,relative_difference=relative,status='PASS' if relative<=1e-8 else 'FAIL',wpp_2025_population=p,wpp_minus_gbd_population=p-populations[0],wpp_relative_difference=p/populations[0]-1,wpp_comparison_role='EXTERNAL_2025_WPP_VS_2023_GBD_DIFFERENT_YEAR_AND_SOURCE'))
    return out
