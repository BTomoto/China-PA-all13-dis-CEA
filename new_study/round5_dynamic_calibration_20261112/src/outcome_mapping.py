import math
from .common import AGES,YLD,YLL,InputBlocked

def checked_ratio(data,disease,sex,age,numerator,denominator):
    ratio=data[(disease,sex,age,numerator,'Number')]/data[(disease,sex,age,denominator,'Number')]
    rate_ratio=data[(disease,sex,age,numerator,'Rate')]/data[(disease,sex,age,denominator,'Rate')]
    if ratio<0 or not math.isclose(ratio,rate_ratio,rel_tol=1e-9):raise InputBlocked('BLOCKED_INPUT: Number/Rate outcome ratio disagreement')
    return ratio,rate_ratio

def prepare(data):
    weights=[];years=[]
    for disease in ['IHD','IS']:
        for sex in ['Male','Female']:
            for age in AGES:
                dw,rdw=checked_ratio(data,disease,sex,age,YLD,'Prevalence')
                if not 0<=dw<=1:raise InputBlocked('BLOCKED_INPUT: effective DW out of range')
                yr,ryr=checked_ratio(data,disease,sex,age,YLL,'Deaths')
                base=dict(disease=disease,sex=sex,age=age,source='GBD2023 disease-burden ZIP point estimates',admission_status='OUTCOME_MAPPING',notes='Cross-sectional age-specific mapping; no independent ratio CI. 95+ uses its original open-age ratio; standard life-table external check pending' if age=='95+' else 'Cross-sectional mapping; no independent ratio CI; not a transition probability')
                weights.append(dict(base,YLD=data[(disease,sex,age,YLD,'Number')],prevalence=data[(disease,sex,age,'Prevalence','Number')],effective_disability_weight=dw,rate_ratio=rdw))
                years.append(dict(base,YLL=data[(disease,sex,age,YLL,'Number')],deaths=data[(disease,sex,age,'Deaths','Number')],YLL_per_death=yr,rate_ratio=ryr))
    return weights,years
