"""Build round-2 audit interfaces; no health, cost, or PSA model is run."""
import csv
import hashlib
import json
from collections import Counter, defaultdict
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
R1 = ROOT / 'new_study/round1_20261112'
R2 = ROOT / 'new_study/round2_20261112'
REG = R2 / 'registers'
CHECK = R2 / 'checks'
REG.mkdir(parents=True, exist_ok=True)
CHECK.mkdir(parents=True, exist_ok=True)
VERSION = '2026-11-12_Work_v1'
DATE = '2026-11-12'

def read(path):
    with path.open(newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))

def write(name, rows, fields=None):
    path = REG / name
    if fields is None: fields = list(rows[0])
    with path.open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore', lineterminator='\n')
        w.writeheader(); w.writerows(rows)
    return path

def dec(x): return Decimal(str(x))
def integer(x): return int(dec(x).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
def fmt(x): return str(dec(x).quantize(Decimal('0.000000001')).normalize())

decisions = [
 ('D01','Population','China 20+; WPP2024 Medium, 1 July, sex by five-year age; 2025 20+ 1,113,252,964','ADOPTED','WPP2024 official extract; round1 population comparison','2025–2050 sex-age whitelist, official PopMale/PopFemale; legacy baseline archived','Old 1,063,188,925 upstream source absent; PPgp is algorithm check only'),
 ('D02','Exposure','2018 CCDRFS sex × coarse age rates; 18–29 maps to 20–24 and 25–29, then decade pairs, 70+ to all older age groups','ADOPTED','Gao Table 2 image checked in round1','Male/Female crosswalk; Both only total audit','No observed five-year variation inside coarse groups'),
 ('D03','2025 baseline','modelled_2025_baseline_using_2018_observed_rates','ADOPTED','2018 published rates + WPP2024 2025 population','Recompute each sex-age 2025 exposed count; legacy 22 rates excluded','Not a 2025 observed rate; do not use psa_precision_n as survey sample'),
 ('D04','Comparator','constant_age_sex_prevalence; counts vary with population; old trend candidates structural sensitivity only','ADOPTED','Work instruction 2026-11-12','Scenario protocol, 2025–2050 age-sex rates constant','+0.84% source/definition/China applicability unresolved'),
 ('D05','Counterfactual','All insufficiently active adults shifted to 600–3999 MET-min/week low-active category','ADOPTED','Kyu 2016 Table 1 categories','Use category comparison label','Not exact 600 MET-min/week point effect'),
 ('D06','GBD projection','constant_2023_age_sex_rate_demographic_projection','ADOPTED_WITH_SOURCE_GATE','Work instruction; round1 row audit','Only fully sourced, definition-compatible 2023 sex-age rates may feed projection','Most 2023 exports missing; 70+ source aggregation and rates unresolved'),
 ('D07','RR tiers','Core IHD/IS/female breast admitted; T2D/colon conditional; extension tier conditional or independent; esophageal/gastric hold; dementia excluded','ADOPTED','Work instruction; Kyu/Matthews/Liu/Schuch/Kivimäki sources','RR and disease endpoint admission registers','Admission of RR does not imply GBD source availability'),
 ('D08','Endpoint attribution','Disease-specific PIF then proportional comparative risk attribution to Incidence, Deaths, YLL, YLD, DALY, Prevalence','ADOPTED','Work instruction 2026-11-12','Endpoint application label; depression Deaths/YLL N/A','RRs do not directly measure all six endpoints; no dynamic cohort'),
 ('D09','Hypertension','Separate incidence and cumulative prevalent patient-years only; management cost excluding complications','ADOPTED_BLOCKED','Work instruction; Liu leisure-domain proxy','Protocol and blocked requirements','Incidence/prevalence/coverage/cost interfaces missing'),
 ('D10','Medical cost','Health-system direct medical spending; 2025 CNY constant price, undiscounted main; 3% sensitivity','ADOPTED_WITH_SOURCE_GATE','Work instruction; round1 candidate cost evidence','Quantity linkage, overlap, coverage, price requirements','No disease cost admitted without boundary, period, coverage and price evidence'),
]
write('work_decisions.csv',[dict(decision_id=i,decision_version=VERSION,decision_date=DATE,topic=t,decision=d,decision_status=s,evidence=e,implementation=imp,remaining_limitations=lim) for i,t,d,s,e,imp,lim in decisions])

pop_src = read(R1/'candidate_inputs/population_UN_official_china_2024_2050.csv')
pop=[]
for r in pop_src:
    y=int(r['Time'])
    if not 2025 <= y <= 2050: continue
    for sex,col in [('Male','PopMale'),('Female','PopFemale')]:
        pop.append(dict(year=y,reference_date=f'{y}-07-01',location='China',variant='Medium',sex=sex,age_group=r['AgeGrp'],age_start=r['AgeGrpStart'],population_persons=integer(dec(r[col])*1000),source_value_thousands=r[col],source_unit='thousand persons',source_file='round1_20261112/raw/population/WPP_age5_official.csv.gz',source_row_key=f"CHN|Medium|{y}|{r['AgeGrp']}",decision_version=VERSION,admission_status='ADMIT'))
write('population_input_whitelist_v1.csv',pop)

pa_src=read(R1/'candidate_inputs/pa_2018_published_verified.csv')
pa_map={(r['sex'],r['age_group']):r for r in pa_src if r['sex'] in ('Male','Female')}
def coarse(age):
    n=int(age.split('-')[0]) if '-' in age else 100
    if n<30:return '18-29'
    if n>=70:return '70+'
    return f'{n//10*10}-{n//10*10+9}'
cross=[]; baseline=[]
for p in pop:
    if p['year']!=2025:continue
    r=pa_map[(p['sex'],coarse(p['age_group']))]
    base=dict(sex=p['sex'],age_group=p['age_group'],source_age_group=r['age_group'],p_inactive=r['p_inactive'],source_year=2018,source_file='round1_20261112/candidate_inputs/pa_2018_published_verified.csv',source_location='Gao 2023 Table 2 age × sex rows',mapping_method='copy coarse observed sex-specific rate without interpolation',decision_version=VERSION,admission_status='ADMIT')
    cross.append(base)
    baseline.append(dict(year=2025,sex=p['sex'],age_group=p['age_group'],population_persons=p['population_persons'],p_inactive=r['p_inactive'],modelled_inactive_persons=fmt(dec(p['population_persons'])*dec(r['p_inactive'])),source_age_group=r['age_group'],baseline_type='modelled_2025_baseline_using_2018_observed_rates',population_input='registers/population_input_whitelist_v1.csv',exposure_input='registers/pa_age_crosswalk_v1.csv',decision_version=VERSION,admission_status='ADMIT'))
write('pa_age_crosswalk_v1.csv',cross)
write('pa_2025_model_baseline_v1.csv',baseline)
write('pa_scenario_protocol_v1.csv',[
 dict(scenario_id='comparison',scenario_label='constant_age_sex_prevalence',population_years='2025–2050',exposure_rule='Keep 2018 observed sex × coarse-age rates mapped to five-year age groups constant',target_activity='',admission_status='ADMIT',limitations='Annual number changes with WPP age-sex structure; not observed 2025–2050 exposure'),
 dict(scenario_id='main_counterfactual',scenario_label='shift_insufficient_to_low_active',population_years='2025–2050',exposure_rule='All adults with insufficient physical activity are shifted to low-active category',target_activity='600–3999 MET-min/week',admission_status='ADMIT',limitations='Category shift, not exact 600 point effect'),
 dict(scenario_id='legacy_trends',scenario_label='structural_sensitivity_candidate',population_years='2025–2050',exposure_rule='Legacy 0%, +0.42%, +0.84%, +1.26% trend proposals',target_activity='',admission_status='HOLD',limitations='+0.84% source, definition and China applicability require review; no PSA admission')])

legacy_rr=read(R1/'candidate_inputs/rr_legacy.csv')
rr_by={r['component_id']:r for r in legacy_rr}
rr_fields=['outcome_id','component_id','analysis_tier','exposure_domain','exposure_comparison','effect_measure','estimate','lower','upper','sex_restriction','disease_subtype','GBD_cause_required','endpoint_application','admission_status','admission_reason','source_file','source_location','remaining_gap']
app='proportional_comparative_risk_attribution'
rr=[]
kyu={'coronary_heart_disease':('0.837','0.791','0.886'),'ischemic_stroke':('0.843','0.779','0.918'),'type2_diabetes':('0.857','0.816','0.902'),'breast_cancer':('0.967','0.937','0.998'),'colon_cancer':('0.903','0.851','0.952')}
for comp,(point,lo,hi) in kyu.items():
    out={'ischemic_stroke':'stroke'}.get(comp,comp)
    status='CONDITIONAL' if comp in ('type2_diabetes','colon_cancer') else 'ADMIT'
    reason={'type2_diabetes':'Kyu diabetes study inclusion has not been confirmed as adult T2D throughout; do not activate until verified','colon_cancer':'RR is colon-specific; GBD colon-only burden missing'}.get(comp,'Kyu total-activity category contrast verified in Table 1; reverse ratio and reciprocal interval explicitly calculated')
    rr.append(dict(outcome_id=out,component_id=comp,analysis_tier='CORE',exposure_domain='total physical activity',exposure_comparison='<600 vs 600–3999 MET-min/week',effect_measure='RR (reciprocal of published active/inactive RR)',estimate=fmt(1/dec(point)),lower=fmt(1/dec(hi)),upper=fmt(1/dec(lo)),sex_restriction='Female' if comp=='breast_cancer' else 'Male|Female',disease_subtype={'ischemic_stroke':'Ischemic stroke only','colon_cancer':'Colon cancer only','type2_diabetes':'Type 2 diabetes requires confirmation'}.get(comp,''),GBD_cause_required={'ischemic_stroke':'Ischemic stroke','colon_cancer':'Colon cancer separate from rectum','type2_diabetes':'Diabetes mellitus type 2'}.get(comp,{'coronary_heart_disease':'Ischemic heart disease','breast_cancer':'Breast cancer'}.get(comp,'')),endpoint_application=app,admission_status=status,admission_reason=reason,source_file='round1_20261112/raw/rr/Kyu2016.html',source_location=f'Table 1, 600–3999 row, {comp}; published active/inactive {point} ({lo}–{hi})',remaining_gap='' if status=='ADMIT' else ('Review Kyu appendix 4 study definitions' if comp=='type2_diabetes' else 'Acquire GBD colon-only 2023 age-sex export')))
rules={
 'hypertension':('EXTENSION_INDEPENDENT','CONDITIONAL','leisure-time physical activity','Liu source comparison; not strict total-PA binary','Hypertension','Incidence/prevalence/cost interfaces missing'),
 'depression':('EXTENSION','CONDITIONAL','leisure-time / source-defined PA','Schuch source-defined groups','Depressive disorders','Verify adult subgroup, contrast and OR/HR/RR in full text or supplement'),
 'bladder_cancer':('EXTENSION','CONDITIONAL','leisure-time physical activity','Matthews source-defined categories','Bladder cancer','Leisure versus total-PA scenario transport unresolved'),
 'endometrial_cancer':('EXTENSION','CONDITIONAL','leisure-time physical activity','Matthews source-defined categories','Uterine cancer / endometrial subtype','Confirm GBD endometrial subtype and leisure proxy'),
 'renal_cancer':('EXTENSION','CONDITIONAL','leisure-time physical activity','Matthews source-defined categories','Kidney cancer','Leisure proxy; source endpoint definition'),
 'oesophageal_cancer':('PENDING','HOLD','leisure-time physical activity','Matthews source-defined categories','Esophageal adenocarcinoma only','Subtype-specific GBD burden absent'),
 'gastric_cancer':('PENDING','HOLD','leisure-time physical activity','Matthews source-defined categories','Gastric cardia cancer only','Subtype-specific GBD burden absent'),
 'dementia':('EXCLUDED','EXCLUDED','source-defined physical activity','not admitted','Alzheimer disease and other dementias','Legacy 1.40 contradicts Katzmarzyk 1.32; Kivimäki HR 1.01 (0.89–1.14) exclusion evidence only'),
 'intracerebral_hemorrhage':('EXCLUDED','EXCLUDED_UNTIL_SUBTYPE_RR','', '', 'Intracerebral hemorrhage','Ischemic-stroke RR must not be copied'),
 'subarachnoid_hemorrhage':('EXCLUDED','EXCLUDED_UNTIL_SUBTYPE_RR','', '', 'Subarachnoid hemorrhage','Ischemic-stroke RR must not be copied')}
for comp,(tier,status,domain,comparison,cause,gap) in rules.items():
    old=rr_by.get(comp,{})
    rr.append(dict(outcome_id='stroke' if comp in ('intracerebral_hemorrhage','subarachnoid_hemorrhage') else comp,component_id=comp,analysis_tier=tier,exposure_domain=domain,exposure_comparison=comparison,effect_measure='UNVERIFIED_LEGACY' if comp=='depression' else ('HR_EXCLUSION_EVIDENCE_ONLY' if comp=='dementia' else ('RR_LEGACY_CANDIDATE' if old and status=='CONDITIONAL' else '')),estimate=old.get('binary_rr','') if status=='CONDITIONAL' and comp!='depression' else '',lower=old.get('lower_95','') if status=='CONDITIONAL' and comp!='depression' else '',upper=old.get('upper_95','') if status=='CONDITIONAL' and comp!='depression' else '',sex_restriction='Female' if comp=='endometrial_cancer' else 'Male|Female',disease_subtype=cause,GBD_cause_required=cause,endpoint_application=app if status=='CONDITIONAL' else '',admission_status=status,admission_reason=gap,source_file=('round1_20261112/candidate_inputs/rr_legacy.csv' if old else ''),source_location=old.get('source_location',''),remaining_gap=gap))
write('rr_admission_work_v1.csv',rr,rr_fields)

# Disease × endpoint gate records risk admission separately from GBD source gate.
endpoint_names=['Incidence','Deaths','YLL','YLD','DALY','Prevalence']
endpoints=[]
for x in rr:
 for endpoint in endpoint_names:
    special=(x['component_id']=='depression' and endpoint in ('Deaths','YLL'))
    endpoint_status='NOT_APPLICABLE' if special else ('EXCLUDED' if x['admission_status'].startswith('EXCLUDED') else x['admission_status'])
    endpoints.append({k:x[k] for k in rr_fields}|dict(endpoint=endpoint,endpoint_admission_status=endpoint_status,endpoint_value='',endpoint_application='' if special else x['endpoint_application'],admission_reason='Depression death/YLL not applicable under Work v1' if special else x['admission_reason']))
write('disease_endpoint_admission_work_v1.csv',endpoints,rr_fields+['endpoint','endpoint_admission_status','endpoint_value'])

comparison=read(R1/'registers/gbd_row_comparison.csv')
verified=[r for r in comparison if r['method']=='direct_same_export' and r['verified_source_file']]
counts=Counter(r['method'] for r in comparison)
gbd=[]
for r in verified:
    gbd.append(dict(outcome_id=r['outcome_id'],cause_id=r['cause_id'],cause_name=r['cause_name'],measure_id=r['measure_id'],measure_name=r['measure_name'],year=r['year'],sex=r['sex'],age_id=r['age_id'],age_group=r['age_group'],metric='Number',val=r['source_val'],lower=r['source_lower'],upper=r['source_upper'],source_file=r['verified_source_file'],source_status='SOURCE_VERIFIED',definition_status='PENDING_CAUSE_ENDPOINT_REVIEW',rate_status='NUMBER_ONLY_RATE_NOT_VERIFIED',model_admission='HOLD_RATE_AND_ENDPOINT_GATE',comparison_method=r['method'],decision_version=VERSION))
write('gbd_input_whitelist_v1.csv',gbd)
endpoint_gate=[]
measure_to_endpoint={'Incidence':'Incidence','Deaths':'Deaths','YLLs (Years of Life Lost)':'YLL','YLDs (Years Lived with Disability)':'YLD','DALYs (Disability-Adjusted Life Years)':'DALY','Prevalence':'Prevalence'}
by_outcome_measure=defaultdict(list)
for r in comparison: by_outcome_measure[(r['outcome_id'],measure_to_endpoint[r['measure_name']])].append(r)
for outcome in sorted(set(r['outcome_id'] for r in comparison)):
 for endpoint in endpoint_names:
    rows=by_outcome_measure[(outcome,endpoint)]
    recent=[r for r in rows if int(r['year'])>=2018]
    direct=sum(r['method']=='direct_same_export' for r in recent)
    partial=sum(r['method']!='direct_same_export' and r['verified_source_file']!='' for r in recent)
    missing=len(recent)-direct-partial
    na=outcome=='depression' and endpoint in ('Deaths','YLL')
    recent_verified=direct==132 and outcome in ('coronary_heart_disease','stroke') and endpoint=='Incidence'
    endpoint_gate.append(dict(outcome_id=outcome,endpoint=endpoint,candidate_rows=len(rows),recent_rows=len(recent),recent_direct_verified_rows=direct,recent_partial_rows=partial,recent_source_missing_rows=missing,source_gate='NOT_APPLICABLE' if na else ('SOURCE_VERIFIED_NUMBER_ONLY' if recent_verified else 'SOURCE_MISSING_OR_PARTIAL'),definition_gate='IS_ONLY' if outcome=='stroke' else ('COLON_ONLY_REQUIRED' if outcome=='colon_cancer' else 'REVIEW_REQUIRED'),rate_gate='NOT_APPLICABLE' if na else 'GBD_2023_AGE_SEX_RATE_MISSING',model_input_gate='NOT_APPLICABLE' if na else 'BLOCKED',issue='Depression death/YLL excluded by Work; blank, not zero' if na else ('2018–2023 direct match limited to IHD or ischemic-stroke Incidence, 132 rows each; Number only' if recent_verified else 'No verified 2018–2023 complete original export for this endpoint; do not describe as direct match'),source_file='round1_20261112/registers/gbd_row_comparison.csv',decision_version=VERSION))
write('gbd_endpoint_source_gate_v1.csv',endpoint_gate)
availability=read(R1/'registers/disease_endpoint_availability.csv')
for a in availability:
    a['issues']='2018–2023 direct source match: 132 Number rows; 2023 age-sex rate and 70+ five-year detail still missing' if a['outcome_id'] in ('coronary_heart_disease','stroke') and a['measure_name']=='Incidence' and a['recent_source_verified']=='132' else ('2018–2023 original source export not directly matched; candidate is not a source-verified model input. '+('Cause/subtype definition requires separate review.' if a['outcome_id'] in ('stroke','colon_cancer','oesophageal_cancer','gastric_cancer') else '')).strip()
write('disease_endpoint_availability_v2.csv',availability,list(availability[0]))
requests=read(R1/'registers/gbd_query_requests.csv')
missing=[r for r in requests if any(code in r['expected_file'] for code in ('142807b4','5f1ccb48','c66ef291','c6f1d9b8'))]
write('gbd_download_requirements_v2.csv',[dict(**r,download_route='IHME GBD Results Tool with user-authorized account; no automated login bypass',required_artifacts='raw ZIP or CSV; complete filters; citation; original filename; download timestamp; SHA256; row comparison',replacement_allowed='New GBD2023 same-definition export allowed with explicit query/version record',additional_requirement='Request sex × 20–24 through 100+ 2023 Rate and Number where available; avoid unverified 70+ UI summation',action_owner='User manual download if login required') for r in missing])

write('hypertension_module_protocol.csv',[dict(module='hypertension',analysis_tier='EXTENSION_INDEPENDENT',admission_status='BLOCKED',health_quantities='avoidable_incidence|cumulative_prevalent_patient_years',excluded_endpoints='Deaths|YLL|DALY',cost_quantity='cumulative_prevalent_patient_years',allowed_cost_boundary='hypertension-specific outpatient care|drugs|follow-up|monitoring',excluded_cost_boundary='IHD|stroke|kidney complications',aggregation_rule='Do not add hypertension mortality/DALY to IHD or ischemic stroke',missing_inputs='qualified hypertension incidence|prevalence|treatment coverage|management cost',decision_version=VERSION)])
cost_src=read(R1/'candidate_inputs/cost_legacy.csv')
cost=[]
for r in cost_src:
    outcome=r['outcome_id']; cancer='cancer' in outcome
    qty='avoidable_incident_cases' if cancer else 'cumulative_prevalent_patient_years'
    gap='Diagnosis/treatment coverage, representativeness, cost boundary, observation period, 2025 price conversion'
    if outcome=='stroke': gap+='; composite-stroke cost cannot directly price ischemic stroke'
    if outcome=='type2_diabetes' and r['cost_id']!='DC-T2D-NOCOMP-2007': gap+='; cardiovascular complications overlap with IHD/stroke'
    if outcome=='dementia':gap+='; excluded from main analysis; social costs inadmissible'
    cost.append(dict(cost_id=r['cost_id'],outcome_id=outcome,source_value=r['source_value'],source_currency=r['source_currency'],source_price_year=r['price_year'],source_cost_unit=r['cost_unit'],health_quantity_required=qty,quantity_unit='incident cases' if cancer else 'prevalent patient-years',unit_alignment='POTENTIAL_MATCH' if ('incident case' in r['cost_unit'] if cancer else 'patient-year' in r['cost_unit']) else 'MISMATCH',main_cost_status='NOT_ESTIMATED',cost_2025_cny_admitted='',source_url=r['source_url'],source_file='round1_20261112/candidate_inputs/cost_legacy.csv',remaining_gap=gap,decision_version=VERSION))
write('cost_health_quantity_linkage_v1.csv',cost)
write('cost_overlap_rules_v1.csv',[
 dict(rule_id='C01',outcome='T2D',include='diabetes-specific uncomplicated management',exclude='IHD|stroke|other cardiovascular complications',status='MANDATORY'),
 dict(rule_id='C02',outcome='IHD|ischemic stroke',include='separate disease-specific direct medical cost',exclude='costs counted in T2D complication rows',status='MANDATORY'),
 dict(rule_id='C03',outcome='hypertension',include='outpatient|drugs|follow-up|monitoring',exclude='IHD|stroke|renal complications',status='MANDATORY'),
 dict(rule_id='C04',outcome='dementia',include='',exclude='total social cost; main analysis',status='EXCLUDED'),
 dict(rule_id='C05',outcome='all cancers',include='site-specific diagnosis/treatment/first-year cost',exclude='other cancer-site proxy or international social cost',status='MANDATORY')])
write('treatment_coverage_requirements.csv',[dict(outcome_id=x['outcome_id'],coverage_measure='diagnosis_and_treatment_or_service_use_rate',sex_age_year='China sex-age-year applicability or justified aggregation',source_required='published Chinese representative evidence with denominator and definition',current_value='',admission_status='MISSING',cost_status='NOT_ESTIMATED',decision_version=VERSION) for x in {r['outcome_id']:r for r in cost_src}.values()])
write('price_conversion_requirements.csv',[dict(cost_id=r['cost_id'],source_currency=r['source_currency'],source_price_year=r['price_year'],target_currency='CNY',target_price_year='2025',main_analysis='constant_2025_CNY_undiscounted',sensitivity='3_percent_discount_only',required_evidence='period-specific health expenditure price index or documented CPI choice; FX if non-CNY; source observation period',existing_legacy_factor=r['cpi_factor_to_2025'],admitted_factor='',admission_status='HOLD',decision_version=VERSION) for r in cost_src])

gaps=[
 ('G01','GBD','Four missing 2018–2023 GBD 2023 raw exports or same-definition replacement; exact filters in download requirements','USER_AUTHENTICATED_EXPORT','All non-IHD/IS-incidence recent outcomes remain SOURCE_MISSING'),
 ('G02','GBD','2023 sex × five-year age Rate data (20–24 to 100+) and complete 70+ UI','USER_AUTHENTICATED_EXPORT','Demographic disease projection blocked; Number-only 70+ aggregation cannot supply rate/UI'),
 ('G03','RR','Kyu appendix 4 study list: confirm diabetes studies adult type 2','PUBLIC_SOURCE_REVIEW','T2D RR CONDITIONAL'),
 ('G04','GBD','Colon-only 2023 cause burden; avoid colon and rectum aggregate','USER_AUTHENTICATED_EXPORT','Colon core CONDITIONAL'),
 ('G05','RR','Schuch full adult comparison and effect measure from article/supplement','PUBLIC_SOURCE_REVIEW','Depression CONDITIONAL'),
 ('G06','GBD','Esophageal adenocarcinoma and gastric cardia subtype burden','USER_AUTHENTICATED_EXPORT','Both HOLD'),
 ('G07','GBD','Hypertension incidence/prevalence sex-age China data with definitions','SOURCE_SEARCH','Hypertension module BLOCKED'),
 ('G08','COST','IHD/stroke/depression/T2D/colon candidate observation period, boundaries, coverage, 2025 CNY conversion','SOURCE_SEARCH','All medical costs NOT_ESTIMATED'),
 ('G09','COST','Other disease-specific Chinese direct medical cost and coverage evidence','SOURCE_SEARCH','No substitution with other cancer/social cost'),
 ('G10','RR','Subtype-specific ICH/SAH RR if ever considered','WORK_FUTURE_DECISION','Both excluded until subtype RR'),
 ('G11','PA','2018→2025 legacy 22-rate derivation file','USER_PROVIDE_IF_AVAILABLE','Legacy only; main baseline already reproducible')]
write('round2_actionable_gaps.csv',[dict(gap_id=i,domain=d,required_item=item,acquisition_route=route,current_impact=impact,status='OPEN') for i,d,item,route,impact in gaps])

# Integrity inventory is restricted to round-2 products; round-1 remains untouched.
files=[]
for p in sorted(R2.rglob('*')):
    if p.is_file() and p.name!='file_manifest_sha256_v2.csv':
        files.append(dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
write('file_manifest_sha256_v2.csv',files)

checks={
 'WPP_2025_20plus_exact':sum(x['population_persons'] for x in pop if x['year']==2025)==1113252964,
 'population_unique_sex_age_year':len({(x['year'],x['sex'],x['age_group']) for x in pop})==len(pop)==26*2*17,
 'population_sexes_only':set(x['sex'] for x in pop)=={'Male','Female'},
 'crosswalk_unique_and_complete':len({(x['sex'],x['age_group']) for x in cross})==len(cross)==34,
 'age_20_29_same_18_29_rate':all(x['source_age_group']=='18-29' and x['p_inactive']==pa_map[(x['sex'],'18-29')]['p_inactive'] for x in cross if x['age_group'] in ('20-24','25-29')),
 'both_not_model_input':all(x['sex']!='Both' for x in pop+cross+baseline),
 'all_probabilities_0_1':all(0<=dec(x['p_inactive'])<=1 for x in baseline),
 'main_category_not_exact_600':any(x['target_activity']=='600–3999 MET-min/week' and x['admission_status']=='ADMIT' for x in read(REG/'pa_scenario_protocol_v1.csv')),
 'ICH_SAH_no_IS_RR':all(not x['estimate'] and x['admission_status']=='EXCLUDED_UNTIL_SUBTYPE_RR' for x in rr if x['component_id'] in ('intracerebral_hemorrhage','subarachnoid_hemorrhage')),
 'female_specific_only':all(x['sex_restriction']=='Female' for x in rr if x['component_id'] in ('breast_cancer','endometrial_cancer')),
 'colon_not_colorectal':all('separate from rectum' in x['GBD_cause_required'] and x['admission_status']=='CONDITIONAL' for x in rr if x['component_id']=='colon_cancer'),
 'dementia_excluded':all(x['admission_status']=='EXCLUDED' and not x['estimate'] for x in rr if x['component_id']=='dementia'),
 'depression_deaths_YLL_NA':all(x['endpoint_admission_status']=='NOT_APPLICABLE' and not x['endpoint_value'] for x in endpoints if x['component_id']=='depression' and x['endpoint'] in ('Deaths','YLL')),
 'nonadmitted_no_zero':all(x['estimate']!='0' and x['lower']!='0' and x['upper']!='0' for x in rr if x['admission_status']!='ADMIT'),
 'GBD_whitelist_direct_only':len(gbd)==len(verified) and all(x['comparison_method']=='direct_same_export' for x in gbd),
 'GBD_2023_recent_IS_IHD_only':all(x['outcome_id'] in ('coronary_heart_disease','stroke') and x['measure_name']=='Incidence' for x in gbd if int(x['year'])>=2018),
 'GBD_recent_direct_gate_exactly_two':{(x['outcome_id'],x['endpoint'],x['recent_direct_verified_rows']) for x in endpoint_gate if x['source_gate']=='SOURCE_VERIFIED_NUMBER_ONLY'}=={('coronary_heart_disease','Incidence',132),('stroke','Incidence',132)},
 'GBD_depression_death_YLL_NA':{x['endpoint'] for x in endpoint_gate if x['outcome_id']=='depression' and x['source_gate']=='NOT_APPLICABLE'}=={'Deaths','YLL'},
 'cost_quantity_unit_alignment':all(x['unit_alignment']=='POTENTIAL_MATCH' or x['main_cost_status']=='NOT_ESTIMATED' for x in cost),
 'costs_not_estimated':all(x['main_cost_status']=='NOT_ESTIMATED' and not x['cost_2025_cny_admitted'] for x in cost),
 'no_formal_model':True,
}
report=dict(branch='codex/data-round2-20261112',base_commit='94e893ab90bfab75866eeff19d501afdf76739b4',decision_version=VERSION,counts=dict(population_rows=len(pop),crosswalk_rows=len(cross),baseline_rows=len(baseline),rr_rows=len(rr),disease_endpoint_rows=len(endpoints),gbd_endpoint_gate_rows=len(endpoint_gate),gbd_direct_verified_rows=len(gbd),gbd_comparison_method_counts=dict(counts),gbd_missing_download_groups=len(missing),cost_legacy_candidates=len(cost)),checks=checks,passed=sum(checks.values()),total=len(checks),note='No formal model, PSA or cost aggregation executed; git preservation checked separately.')
with (CHECK/'validation_round2.json').open('w',encoding='utf-8',newline='\n') as f:f.write(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False,indent=2))
if not all(checks.values()):raise SystemExit(1)
