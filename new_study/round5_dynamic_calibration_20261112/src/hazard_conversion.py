import math
from .common import AGES,InputBlocked

def rate_to_hazard(rate):
    if not math.isfinite(rate) or rate<0:raise InputBlocked('negative/nonfinite mortality rate')
    return rate/100000

def hazard_to_probability(hazard,dt=1):
    if not math.isfinite(hazard) or hazard<0 or dt<0:raise InputBlocked('invalid hazard/duration')
    return -math.expm1(-hazard*dt)

def subtract_target(all_cause,target):
    if all_cause<target:raise InputBlocked('BLOCKED_INPUT: negative other-cause hazard')
    return all_cause-target

def prepare(datasets):
    conversions=[];others=[]
    for disease in ['IHD','IS']:
        for sex in ['Male','Female']:
            for age in AGES:
                rates=[('all_cause',datasets['all_cause'][('ALL',sex,age,'Deaths','Rate')]),('target_disease_population',datasets['disease'][(disease,sex,age,'Deaths','Rate')])]
                for typ,rate in rates:
                    hazard=rate_to_hazard(rate)
                    conversions.append(dict(disease=disease,sex=sex,age=age,rate_type=typ,rate_per_100k=rate,annual_hazard=hazard,annual_probability=hazard_to_probability(hazard),source='GBD2023 '+('all_cause' if typ=='all_cause' else 'disease')+' raw export',status='PASS'))
                all_h,target=[rate_to_hazard(v) for _,v in rates]
                other=subtract_target(all_h,target)
                others.append(dict(disease_model=disease,sex=sex,age=age,all_cause_hazard=all_h,target_disease_population_mortality_hazard=target,other_cause_hazard=other,status='WORK_SPECIFIED_HAZARD_DECOMPOSITION',notes='Other-cause hazard equal in disease-free and diseased states; other target disease remains included'))
    return conversions,others
