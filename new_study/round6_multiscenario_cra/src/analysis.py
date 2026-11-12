"""Run identifiable exposure/risk arithmetic; gate clinical event attribution."""
from collections import defaultdict
import math
from .common import R6,ROOT,VARIANTS,read_csv,InputBlocked
from .exposure import known_inactive_share,completion,p15_mover_fraction
from .risk import category_identification_bounds

LEGACY_RR={'IHD':1.19474313,'IS':1.18623962}

def exposure_rows(baseline):
    out=[]
    for b in baseline:
        for scenario,path in VARIANTS:
            p=known_inactive_share(b['p_inactive'],scenario,b['year'],path)
            out.append(dict(year=b['year'],sex=b['sex'],age=b['age'],scenario=scenario,path=path,population=b['population'],baseline_p_inactive=b['p_inactive'],scenario_p_inactive=p,inactive_persons=None if p is None else b['population']*p,mean_activity_MET_min_week='',full_distribution_status='BLOCKED_EXPOSURE_DISTRIBUTION',inactive_fraction_status='DERIVED_FROM_VERIFIED_SOURCE' if scenario=='B0' else 'SCENARIO_ASSUMPTION' if p is not None else 'BLOCKED_EXPOSURE_DISTRIBUTION',exposure_source_year=2018,model_start_year=2025))
    return out

def risk_and_incidence(baseline,rates,categories):
    pifs=[];events=[]
    for b in baseline:
        year,sex,age=b['year'],b['sex'],b['age']
        for disease in ['IHD','IS']:
            baseline_events=b['population']*rates[(disease,sex,age)][0]/1e5
            for scenario,path in VARIANTS:
                lower=upper='';point='';difference_lower=difference_upper=''
                if scenario=='B0':
                    point=lower=upper=0.;risk_status='IDENTITY_REFERENCE'
                elif scenario in ['P15','R1']:
                    alpha=p15_mover_fraction(year) if scenario=='P15' else completion(year,path)
                    lower,upper=category_identification_bounds(b['p_inactive'],alpha,categories[disease])
                    risk_status='STRUCTURAL_SENSITIVITY_ONLY'
                else:risk_status='BLOCKED_EXPOSURE_DISTRIBUTION'
                if scenario in ['B0','P15','R1']:
                    alpha_s=0. if scenario=='B0' else p15_mover_fraction(year) if scenario=='P15' else completion(year,path)
                    delta=alpha_s-p15_mover_fraction(year)
                    unit_lower,unit_upper=category_identification_bounds(b['p_inactive'],1.,categories[disease])
                    difference_lower,difference_upper=sorted([delta*unit_lower,delta*unit_upper])
                pifs.append(dict(year=year,sex=sex,age=age,disease=disease,scenario=scenario,path=path,pif=point,categorical_pif_bound_lower=lower,categorical_pif_bound_upper=upper,categorical_difference_vs_P15_lower=difference_lower,categorical_difference_vs_P15_upper=difference_upper,risk_calculation_status=risk_status,interval_type='IDENTIFICATION_ENVELOPE_NOT_CI' if lower!='' else '',continuous_pif_status='IDENTITY_REFERENCE' if scenario=='B0' else 'BLOCKED_EXPOSURE_DISTRIBUTION',endpoint_admission='REFERENCE_ONLY' if scenario=='B0' else 'BLOCKED_ENDPOINT_ALIGNMENT'))
                events.append(dict(year=year,sex=sex,age=age,disease=disease,scenario=scenario,path=path,population=b['population'],baseline_expected_incident_units=baseline_events,avoided_incident_units=0. if scenario=='B0' else '',scenario_expected_incident_units=baseline_events if scenario=='B0' else '',result_status='B0_DESCRIPTIVE_RATE_PROJECTION' if scenario=='B0' else 'BLOCKED_ENDPOINT_ALIGNMENT',unit='GBD_reported_incident_units_not_assumed_unique_patients'))
    return pifs,events

def national_exposure(rows):
    groups=defaultdict(list)
    for r in rows:groups[(r['year'],r['scenario'],r['path'])].append(r)
    out=[]
    for (year,scenario,path),items in sorted(groups.items()):
        pop=sum(r['population'] for r in items)
        known=all(r['scenario_p_inactive'] is not None for r in items)
        inactive=sum(r['inactive_persons'] for r in items) if known else None
        out.append(dict(year=year,scenario=scenario,path=path,population=pop,baseline_p_inactive=sum(r['population']*r['baseline_p_inactive'] for r in items)/pop,scenario_p_inactive=inactive/pop if known else '',inactive_persons=inactive if known else '',status='SCENARIO_ASSUMPTION' if known else 'BLOCKED_EXPOSURE_DISTRIBUTION',mean_MET_min_week=''))
    return out

def comparison_summary(events):
    groups=defaultdict(list)
    for row in events:groups[(row['disease'],row['scenario'],row['path'])].append(row)
    out=[]
    for (disease,scenario,path),rows in sorted(groups.items()):
        periods=[('annual',str(y),y,y) for y in range(2025,2051)]+[('cumulative',f'2025-{end}',2025,end) for end in [2030,2034,2050]]
        for kind,label,start,end in periods:
            selected=[r for r in rows if start<=r['year']<=end]
            base=sum(r['baseline_expected_incident_units'] for r in selected)
            out.append(dict(disease=disease,scenario=scenario,path=path,period_type=kind,period=label,calendar_years=end-start+1,baseline_expected_incident_units=base,avoided_incident_units=0. if scenario=='B0' else '',relative_change_percent=0. if scenario=='B0' else '',difference_vs_P15='',status='B0_DESCRIPTIVE_RATE_PROJECTION' if scenario=='B0' else 'BLOCKED_ENDPOINT_ALIGNMENT',interpretation='ENDPOINT_COUNTERFACTUAL' if kind=='annual' and start in [2030,2034,2050] else 'CALENDAR_SUM_WITH_INSTANT_RESPONSE_ASSUMPTION' if kind=='cumulative' else 'ANNUAL_CALENDAR_SCENARIO',exposure_gap='' if scenario in ['B0','P15','R1'] else 'BLOCKED_EXPOSURE_DISTRIBUTION'))
    return out

def legacy_regression(baseline,rates):
    """Old binary P15 ONLY. Never used as the round-six admitted effect input."""
    old=read_csv(ROOT/'new_study/round3_health_model_pilot_20261112/results/incidence_age_sex_2025_2050.csv')
    old={(int(r['year']),r['disease'],r['sex'],r['age_group']):r for r in old}
    out=[]
    for b in baseline:
        for disease in ['IHD','IS']:
            p0=b['p_inactive'];p1=p0*(1-p15_mover_fraction(b['year']));rr=LEGACY_RR[disease]
            pif=(p0-p1)*(rr-1)/(1+p0*(rr-1))
            base=b['population']*rates[(disease,b['sex'],b['age'])][0]/1e5
            calculated=base*pif
            ref=old[(b['year'],disease,b['sex'],b['age'])]
            delta=calculated-float(ref['incident_cases_averted'])
            if abs(delta)>1e-7:raise InputBlocked('REGRESSION_FAILURE: old P15 detail differs')
            out.append(dict(year=b['year'],disease=disease,sex=b['sex'],age=b['age'],scenario='P15',recomputed_legacy_avoided_units=calculated,old_avoided_units=ref['incident_cases_averted'],absolute_difference=abs(delta),status='REGRESSION_ONLY_NOT_RR_ADMISSION'))
    return out

def legacy_summaries(rows):
    out=[]
    expected={'IHD':[45531.007,116899.570,547363.017],'IS':[57420.852,143733.241,598423.448]}
    for d in ['IHD','IS']:
        for j,end in enumerate([2030,2034,2050]):
            n=sum(r['recomputed_legacy_avoided_units'] for r in rows if r['disease']==d and r['year']<=end)
            if abs(n-expected[d][j])>.001:raise InputBlocked('REGRESSION_FAILURE: old P15 cumulative')
            out.append(dict(disease=d,scenario='P15',period=f'2025-{end}',calendar_years=end-2025+1,recomputed_legacy_avoided_units=n,rounded_old_reference=expected[d][j],status='REGRESSION_ONLY_NOT_RR_ADMISSION'))
    return out
