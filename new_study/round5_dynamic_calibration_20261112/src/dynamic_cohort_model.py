"""Avoided incident disease cohorts with competing hazards and annual age flow."""
import math
from collections import defaultdict
import numpy as np
from .common import AGES,InputBlocked

OUTCOMES=['incident_cases_averted','prevalent_patient_years_averted','target_disease_deaths_averted','other_cause_deaths_competing','YLD_averted','YLL_averted','DALY_averted']

def advance_age(stock):
    stock=np.asarray(stock,dtype=float)
    if stock.shape!=(16,) or np.any(stock<0):raise ValueError('invalid age stock')
    out=stock.copy();flow=stock[:-1]*.2
    out[:-1]-=flow;out[1:]+=flow
    return out

def cycle(count,target,other,dt):
    if min(count,target,other,dt)<0:raise ValueError('negative state/hazard')
    h=target+other
    person_years=count*dt if h==0 else count*(-math.expm1(-h*dt))/h
    return count*math.exp(-h*dt),person_years,target*person_years,other*person_years

def lookup_tables(parameters,others,weights,years):
    return ({(r['disease'],r['sex'],r['age']):r for r in parameters},
            {(r['disease_model'],r['sex'],r['age']):r for r in others},
            {(r['disease'],r['sex'],r['age']):r for r in weights},
            {(r['disease'],r['sex'],r['age']):r for r in years})

def run(incidence,parameters,others,weights,years,*,calibration_passed,first_duration=.5,synthetic=False):
    if not calibration_passed:raise InputBlocked('BLOCKED_TRANSITION_CALIBRATION')
    if not synthetic and any(r.get('admission_status')!='CALIBRATED_PROVISIONAL' for r in parameters):
        raise InputBlocked('BLOCKED_TRANSITION_CALIBRATION: unadmitted/synthetic parameter')
    tables=lookup_tables(parameters,others,weights,years)
    if not synthetic and any('SYNTHETIC' in str(row) for table in tables for row in table.values()):
        raise InputBlocked('BLOCKED_INPUT: synthetic parameter in empirical run')
    sources={(int(r['year']),r['disease'],r['sex'],r['age_group']):float(r['incident_cases_averted']) for r in incidence}
    result=[]
    for disease in ['IHD','IS']:
        for sex in ['Male','Female']:
            stock=np.zeros(16)
            for year in range(2025,2051):
                survivors=np.zeros(16)
                for j,age in enumerate(AGES):
                    key=(disease,sex,age)
                    if any(key not in table for table in tables):raise InputBlocked('missing age-sex-disease parameter')
                    fatality=float(tables[0][key]['calibrated_case_fatality_hazard'])
                    other=float(tables[1][key]['other_cause_hazard'])
                    entry=sources.get((year,disease,sex,age),0.)
                    if entry<0:raise ValueError('negative incident entry')
                    old=cycle(stock[j],fatality,other,1.)
                    new=cycle(entry,fatality,other,first_duration)
                    survive,py,deaths,otherdeaths=[a+b for a,b in zip(old,new)]
                    dw=float(tables[2][key]['effective_disability_weight']);yll_d=float(tables[3][key]['YLL_per_death'])
                    yld=py*dw;yll=deaths*yll_d
                    survivors[j]=survive
                    result.append(dict(year=year,disease=disease,sex=sex,age=age,incident_cases_averted=entry,prevalent_patient_years_averted=py,target_disease_deaths_averted=deaths,other_cause_deaths_competing=otherdeaths,YLD_averted=yld,YLL_averted=yll,DALY_averted=yld+yll,end_stock_before_age_flow=survive,result_status='SYNTHETIC_TEST_ONLY' if synthetic else 'DYNAMIC_PILOT_PROVISIONAL'))
                stock=advance_age(survivors)
    return result

def aggregate(rows):
    statuses={r['result_status'] for r in rows}
    if len(statuses)!=1 or statuses-{'SYNTHETIC_TEST_ONLY','DYNAMIC_PILOT_PROVISIONAL'}:
        raise InputBlocked('Cannot aggregate mixed/unadmitted result statuses')
    status=next(iter(statuses))
    out=defaultdict(lambda:defaultdict(float))
    for row in rows:
        for end in [2030,2034,2050]:
            if int(row['year'])<=end:
                for sex,age in [(row['sex'],row['age']),(row['sex'],'ALL'),('ALL',row['age']),('ALL','ALL')]:
                    key=(row['disease'],sex,age,f'2025-{end}')
                    for measure in OUTCOMES:out[key][measure]+=float(row[measure])
    return [dict(disease=k[0],sex=k[1],age=k[2],period=k[3],**v,result_status=status) for k,v in sorted(out.items())]

def blocked_results(incidence):
    rows=[]
    for r in incidence:
        rows.append(dict(year=r['year'],disease=r['disease'],sex=r['sex'],age=r['age_group'],incident_cases_averted=r['incident_cases_averted'],**{m:'' for m in OUTCOMES[1:]},end_stock_before_age_flow='',result_status='BLOCKED_TRANSITION_CALIBRATION'))
    summary=[]
    for disease in ['IHD','IS']:
        for end in [2030,2034,2050]:
            summary.append(dict(disease=disease,sex='ALL',age='ALL',period=f'2025-{end}',incident_cases_averted=sum(float(r['incident_cases_averted']) for r in incidence if r['disease']==disease and int(r['year'])<=end),**{m:'' for m in OUTCOMES[1:]},result_status='BLOCKED_TRANSITION_CALIBRATION'))
    return rows,summary
