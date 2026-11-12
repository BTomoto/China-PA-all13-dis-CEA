"""Evidence registers and audit gates only. No burden, cost or PSA model."""
import csv, hashlib, json
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[3]
R1=ROOT/'new_study/round1_20261112'
R2=ROOT/'new_study/round2_20261112'
OUT=ROOT/'new_study/round2_target_prep_20261112'
REG=OUT/'registers'; CHECK=OUT/'checks'
REG.mkdir(parents=True,exist_ok=True);CHECK.mkdir(parents=True,exist_ok=True)
DATE='2026-11-12'
def read(p):
 with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def write(name,rows):
 p=REG/name
 with p.open('w',encoding='utf-8-sig',newline='\n') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
 return p
def row(**k):return k
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

who='https://www.who.int/data/gho/data/themes/topics/indicator-groups/insufficient-physical-activity-indicator-group'
whoind='https://www.who.int/data/gho/data/indicators/indicator-details/GHO/prevalence-of-insufficient-physical-activity-among-adults-aged-18-years-(age-standardized-estimate)-(-)'
zhang='https://pmc.ncbi.nlm.nih.gov/articles/PMC10351178/'
gao='https://html.rhhz.net/zhlxbx/20230803.htm'
jia='https://news.ccmu.edu.cn/docs/2018-06/20180621160034890292.pdf'
rand='https://www.rand.org/content/dam/rand/pubs/research_reports/RR4200/RR4291/RAND_RR4291.pdf'
schuch='https://pubmed.ncbi.nlm.nih.gov/29690792/'
ihme='https://vizhub.healthdata.org/gbd-results/'

write('audit_revision_log.csv',[
 row(id='AR01',prior='Work_v1 D08: same disease PIF applied to six endpoints',revision='Withdraw automatic endpoint admission; retain prior record in round2/work_decisions.csv',reason='Incidence RR does not by itself identify mortality, YLL, YLD, DALY or prevalence effect and cross-endpoint coherence is unresolved',status='REVISED',source='round2_20261112/registers/work_decisions.csv'),
 row(id='AR02',prior='round2 disease_endpoint_admission_work_v1.csv six endpoint application',revision='Split risk evidence, exposure match, endpoint method, GBD source and final model_ready gates',reason='Proportional attribution is a modeling option requiring Work decision and data checks',status='REVISED',source='round2_20261112/registers/disease_endpoint_admission_work_v1.csv'),
 row(id='AR03',prior='Hypertension death/YLL/DALY omitted; YLD not explicitly closed',revision='Death, YLL, YLD, DALY marked NOT_APPLICABLE for current module',reason='Current module reports incidence and cumulative prevalent patient-years only',status='REVISED',source='round2_20261112/registers/hypertension_module_protocol.csv'),
 row(id='AR04',prior='2018 coarse rate copied to fine ages without CI/shared id',revision='Carry original CI and shared source parameter id; do not sample fine ages independently',reason='Copied cells are one survey estimate',status='REVISED',source='round1_20261112/candidate_inputs/pa_2018_published_verified.csv'),
 row(id='AR05',prior='WPP population persons derived from sex columns but column identity implicit',revision='Explicit PopMale or PopFemale source column and thousand-person multiplier',reason='Make person counts traceable to official raw column',status='REVISED',source='round1_20261112/candidate_inputs/population_UN_official_china_2024_2050.csv'),
 row(id='AR06',prior='Legacy cost price_year mixed source and assumption',revision='Separate original verified price year from legacy assumed year; add T2D2019 and CRC2014 evidence',reason='Claim period is not necessarily source price year',status='REVISED',source='round1_20261112/handoff/continuation/registers/medical_cost_evidence_register.csv'),
 row(id='AR07',prior='round2 validation no_formal_model=True without measured execution evidence',revision='Replace unsupported boolean with NOT_CHECKED; checks use PASS/FAIL/NOT_CHECKED/NOT_APPLICABLE',reason='Static script inspection cannot prove all possible execution did not occur',status='REVISED',source='round2_20261112/checks/validation_round2.json'),
 row(id='AR08',prior='Main scenario full threshold shift',revision='WHO-style 2030 relative 15% reduction from 2010 reference is proposed main; full shift becomes supplementary candidate',reason='User scenario revision; target calibration blocked by comparability',status='REVISED',source=who)])

write('who_policy_indicator_evidence.csv',[
 row(id='WHO01',jurisdiction='Global',document='WHO GHO insufficient physical activity indicator group',indicator='15% relative reduction by 2030 against 2010 baseline',population='Adults 18+ plus adolescents separately',status='SOURCE_VERIFIED',policy_role='Global target applied to China as research scenario',url=who,source_location='indicator group overview',retrieved_date=DATE,limitation='Not a numeric target explicitly set in China policy'),
 row(id='WHO02',jurisdiction='Global',document='WHO GHO age-standardized adult indicator metadata',indicator='<150 moderate min/week or <75 vigorous min/week or equivalent',population='Adults 18+',status='SOURCE_VERIFIED',policy_role='Measurement comparator',url=whoind,source_location='Definition and Method of estimation',retrieved_date=DATE,limitation='Country estimates modeled; WHO standard population differs from China 2010 standard'),
 row(id='CHN01',jurisdiction='China',document='Healthy China 2030 outline',indicator='2030 regular exercise participants 530 million; not 15% insufficient-PA target',population='Residents',status='OFFICIAL_TEXT_VERIFIED',policy_role='China policy background',url='https://www.sport.gov.cn/n10503/c772542/content.html',source_location='Main indicators / physical activity section',retrieved_date=DATE,limitation='Participation count differs from WHO insufficient-activity prevalence'),
 row(id='CHN02',jurisdiction='China',document='National Fitness Plan 2026–2030',indicator='Regular exercise participation around 40% by 2030; not 15% insufficient-PA target',population='General population',status='OFFICIAL_SUMMARY_VERIFIED',policy_role='China policy background only',url='https://www.mohrss.gov.cn/SYrlzyhshbzb/dongtaixinwen/shizhengyaowen/202607/t20260724_580834.html',source_location='State Council plan announcement',retrieved_date=DATE,limitation='Exercise participation indicator differs from WHO GPAQ insufficient-activity prevalence')])

base=[('Both','All 18+',17.9,16.3,19.5),('Male','All 18+',20.1,18.5,21.8),('Female','All 18+',15.7,13.9,17.4),('Both','18–34',20.0,18.1,21.8),('Both','35–49',15.0,13.4,16.6),('Both','50–64',14.0,12.2,15.7),('Both','65+',27.6,25.1,30.1)]
write('pa_2010_reference_evidence.csv',[row(year=2010,sex=s,age_group=a,prevalence_percent=p,lower_95_percent=l,upper_95_percent=u,source_population='China adults 18+',instrument='GPAQ',domains='work|transport|recreation',insufficient_threshold='MVPA <150 min/week or equivalent',estimate_type='survey estimate; age-adjusted',standard_population='2010 China standard population',joint_sex_age_available='NO',source_file='round1_20261112/raw/pa/Zhang2023.html',source_url=zhang,source_location='Table 2; Methods paragraph 25',verification_status='SOURCE_VERIFIED',model_20plus_target_admission='HOLD_COMPARABILITY') for s,a,p,l,u in base])
write('target_baseline_comparability.csv',[
 row(comparison='WHO indicator vs Zhang 2010',who_or_reference='WHO 18+ model estimate; WHO standard population; survey corrections',local_or_model='Zhang 2010 CCDRFS survey estimate; China 2010 standard population',age_alignment='18+ matches',instrument_domain_alignment='GPAQ/all domains broadly aligned',standardization_alignment='FAIL',sex_age_alignment='Only sex and separate coarse age; no joint cells',status='FAIL',required_action='Work choose common standard population/measurement series; obtain age-sex cells if 20+ target desired'),
 row(comparison='Zhang 2010 vs Gao 2018',who_or_reference='2010 18+ age-adjusted 17.9% (16.3–19.5)',local_or_model='2018 Gao 18+ complex-weighted sex × coarse age',age_alignment='18+ source; model 20+',instrument_domain_alignment='Both CCDRFS GPAQ; survey coverage/design changed',standardization_alignment='2010 China standard vs Gao reported weighting; matched restandardization not shown',sex_age_alignment='2010 no sex×age joint; 2018 joint age-sex available',status='FAIL',required_action='Acquire harmonized 2010 and 2018 20+ sex-age cells and common weights or select defensible alternative'),
 row(comparison='Zhang 2010 vs 2025 model starting point',who_or_reference='2010 18+ age-adjusted survey reference',local_or_model='2025 20+ WPP-weighted 2018 coarse rates; modeled not observed',age_alignment='FAIL 18+ vs 20+',instrument_domain_alignment='2018 mapped rates; not 2025 measurement',standardization_alignment='2025 WPP population composition vs China 2010 standard',sex_age_alignment='2010 joint strata absent',status='FAIL',required_action='Do not calculate formal target value or attainment gap until Work selects comparable metric and supplies basis')])

write('scenario_interface_v1.csv',[
 row(scenario_id='WHO_CHN_2030_REL15',tier='PROPOSED_MAIN',label='China application of WHO global target: 15% relative reduction in insufficient PA by 2030 versus 2010',reference_year=2010,formula='p_target_2030 = 0.85 * p_reference_2010',numeric_reference='',numeric_target='',attainment_gap='',baseline_2025='round2_20261112/registers/pa_2025_model_baseline_v1.csv',target_metric_gate='BLOCKED_COMPARABILITY',annual_path_rule='WORK_PENDING',age_sex_allocation_rule='WORK_PENDING',threshold_crossing_rule='WORK_PENDING',active_distribution_rule='WORK_PENDING',post_2030_rule='WORK_PENDING',status='CONFIG_ONLY'),
 row(scenario_id='FULL_INSUFFICIENT_TO_LOW_ACTIVE',tier='SUPPLEMENTARY_CANDIDATE',label='All insufficient adults shifted into 600–3999 MET-min/week low-active category',reference_year='',formula='',numeric_reference='',numeric_target='',attainment_gap='',baseline_2025='round2_20261112/registers/pa_2025_model_baseline_v1.csv',target_metric_gate='NOT_APPLICABLE',annual_path_rule='WORK_PENDING',age_sex_allocation_rule='WORK_PENDING',threshold_crossing_rule='all insufficient; category destination only',active_distribution_rule='WORK_PENDING',post_2030_rule='WORK_PENDING',status='CANDIDATE'),
 row(scenario_id='RAND_PLUS20_ALL',tier='EXTENSION',label='RAND 20% increase in activity amount for nonzero participants',reference_year='',formula='activity_new = 1.20 * activity_old for activity_old > 0',numeric_reference='',numeric_target='',attainment_gap='',baseline_2025='',target_metric_gate='NOT_APPLICABLE',annual_path_rule='WORK_PENDING',age_sex_allocation_rule='requires full activity distribution',threshold_crossing_rule='distribution-derived only',active_distribution_rule='requires joint MET distribution',post_2030_rule='WORK_PENDING',status='DATA_BLOCKED'),
 row(scenario_id='RAND_COMBINED',tier='EXTENSION',label='Threshold crossing below recommendation plus 20% activity above threshold',reference_year='',formula='',numeric_reference='',numeric_target='',attainment_gap='',baseline_2025='',target_metric_gate='NOT_APPLICABLE',annual_path_rule='WORK_PENDING',age_sex_allocation_rule='requires full activity distribution',threshold_crossing_rule='WORK_PENDING',active_distribution_rule='requires joint MET distribution',post_2030_rule='WORK_PENDING',status='DATA_BLOCKED')])
write('work_pending_target_decisions.csv',[row(id=f'TD{i}',decision_topic=t,evidence_or_options=o,decision_status='PENDING_WORK',implementation_value='',reason_not_frozen='WHO target does not prescribe this China model implementation') for i,(t,o) in enumerate([
 ('Comparable target metric','2010 China-standardized 18+ vs WHO-standardized modeled 18+ vs new 20+ modeled; harmonized 20+ series needed'),
 ('2025–2030 yearly path','Candidate linear or other path; no path is mandated by WHO target'),
 ('Sex-age allocation','Common relative change, burden-targeted allocation, or optimized allocation require Work choice and 2010 joint baseline'),
 ('Who crosses recommendation','Binary insufficient prevalence alone lacks within-category MET distribution'),
 ('Already-active distribution','Hold fixed or modify requires full category distribution and Work decision'),
 ('Post-2030 persistence','Maintain, decay, or further improve requires Work decision')],1)])

cross=read(R2/'registers/pa_age_crosswalk_v1.csv')
pa={(r['sex'],r['age_group']):r for r in read(R1/'candidate_inputs/pa_2018_published_verified.csv')}
write('exposure_crosswalk_ci_v2.csv',[dict(**x,lower_95=pa[(x['sex'],x['source_age_group'])]['lower_95'],upper_95=pa[(x['sex'],x['source_age_group'])]['upper_95'],shared_parameter_id=f"GAO2018_{x['sex']}_{x['source_age_group']}",independent_survey_estimate='NO',uncertainty_rule='One source parameter shared across mapped fine ages; do not draw independently') for x in cross])
pop=read(R2/'registers/population_input_whitelist_v1.csv')
wpp_hash=sha(R1/'raw/population/WPP_age5_official.csv.gz')
write('population_provenance_v2.csv',[dict(**x,source_population_column='PopMale' if x['sex']=='Male' else 'PopFemale',source_unit_multiplier='1000',source_file_sha256=wpp_hash) for x in pop])

rr=read(R2/'registers/rr_admission_work_v1.csv')
rr_v2=[]
for x in rr:
 comp=x['component_id']; risk='SOURCE_VERIFIED' if comp in ('coronary_heart_disease','ischemic_stroke','type2_diabetes','breast_cancer','colon_cancer') else 'PARTIAL_OR_MISSING'
 exp='PENDING_TARGET_CROSSING' if x['admission_status']=='ADMIT' else 'PENDING_DOMAIN_OR_SUBTYPE'
 if comp=='depression':risk='SOURCE_VERIFIED_EFFECT_TYPE_OR_NOT_RR';exp='PENDING_EXPOSURE_COMPARISON'
 if comp=='type2_diabetes':risk='PARTIAL_TYPE2_DEFINITION'
 rr_v2.append(dict(outcome_id=x['outcome_id'],component_id=comp,prior_rr_admission=x['admission_status'],estimate=x['estimate'],lower=x['lower'],upper=x['upper'],effect_measure='OR inverse candidate; not RR' if comp=='depression' else x['effect_measure'],source_verification_gate=risk,risk_comparison_gate='CONDITIONAL' if comp in ('type2_diabetes','colon_cancer','depression') else ('EXCLUDED' if x['admission_status'].startswith('EXCLUDED') else 'PRIOR_RR_EVIDENCE_ONLY'),exposure_interface_gate=exp,endpoint_method_gate='WORK_PENDING',GBD_source_gate='SEE_GBD_REQUIREMENTS',model_ready='NO',reason='WHO target crossing and six-endpoint application not specified; risk evidence alone cannot activate model',source_file=x['source_file']))
write('rr_admission_audit_v2.csv',rr_v2)
ends=read(R2/'registers/disease_endpoint_admission_work_v1.csv')
end_v2=[]
for x in ends:
 endpoint=x['endpoint'];comp=x['component_id'];na=(comp=='depression' and endpoint in ('Deaths','YLL')) or (comp=='hypertension' and endpoint in ('Deaths','YLL','YLD','DALY'))
 end_v2.append(dict(outcome_id=x['outcome_id'],component_id=comp,endpoint=endpoint,prior_endpoint_status=x['endpoint_admission_status'],source_verification_gate=next(z['source_verification_gate'] for z in rr_v2 if z['component_id']==comp),risk_comparison_gate=next(z['risk_comparison_gate'] for z in rr_v2 if z['component_id']==comp),exposure_interface_gate='PENDING_TARGET_CROSSING',endpoint_method_gate='NOT_APPLICABLE' if na else 'WORK_PENDING',GBD_source_gate='NOT_APPLICABLE' if na else 'SOURCE_MISSING_OR_NUMBER_ONLY',model_ready='NOT_APPLICABLE' if na else 'NO',numeric_effect='',reason='Current module excludes this endpoint' if na else 'Do not apply incidence PIF automatically to this endpoint'))
write('endpoint_admission_audit_v2.csv',end_v2)

oldcost=read(R1/'candidate_inputs/cost_legacy.csv')
cost_evidence=read(R1/'handoff/continuation/registers/medical_cost_evidence_register.csv')
evidence_by={x['outcome_id']:x for x in cost_evidence}
cost=[]
for x in oldcost:
 e=evidence_by.get(x['outcome_id'],{})
 cost.append(row(cost_id=x['cost_id'],outcome_id=x['outcome_id'],candidate_amount=x['source_value'],currency=x['source_currency'],legacy_assumed_price_year=x['price_year'],original_verified_price_year=e.get('verified_price_year',''),original_observation_period='',cost_unit=x['cost_unit'],source_file='round1_20261112/candidate_inputs/cost_legacy.csv',source_url=x['source_url'],evidence_status=e.get('source_status','SOURCE_MISSING'),model_ready='NO',reason='Original price year, treatment coverage, boundary and overlap not all verified; legacy 2025 factor not admitted'))
for x in cost_evidence:
 if x['evidence_id'] in ('COST-T2D-NEW2019','COST-CRC-NEW2014'):
  cost.append(row(cost_id=x['evidence_id'],outcome_id=x['outcome_id'],candidate_amount=x['source_value'],currency=x['currency'],legacy_assumed_price_year='',original_verified_price_year=x['verified_price_year'],original_observation_period='2019' if 'T2D' in x['evidence_id'] else '2012–2014',cost_unit=x['cost_unit'],source_file='round1_20261112/handoff/continuation/registers/medical_cost_evidence_register.csv',source_url=x['source_url'],evidence_status=x['source_status'],model_ready='NO',reason='Regional/nonrepresentative treatment sample or mixed care course; coverage and overlap unresolved'))
write('cost_admission_audit_v2.csv',cost)

write('rand_ding_evidence.csv',[
 row(id='RAND_CHN_MALE',source='RAND RR4291 Table 4.1',country='China',sex='Male',value='16.0%',lower='11.7%',upper='21.4%',measure='Insufficient PA',input_origin='Guthold et al. 2018 country model',method='Estimated inactivity share, not China CCDRFS observation',reuse_status='REFERENCE_ONLY',source_url=rand),
 row(id='RAND_CHN_FEMALE',source='RAND RR4291 Table 4.1',country='China',sex='Female',value='12.2%',lower='8.5%',upper='17.3%',measure='Insufficient PA',input_origin='Guthold et al. 2018 country model',method='Estimated inactivity share, not China CCDRFS observation',reuse_status='REFERENCE_ONLY',source_url=rand),
 row(id='RAND_DISTRIBUTION',source='RAND RR4291 Appendix C.1',country='China application',sex='Both',value='',lower='',upper='',measure='MET-min/week distribution',input_origin='Eurobarometer 88.4 shape from Austria/Germany/France/Netherlands/UK plus Guthold inactive/active share',method='Imputed generic distribution shifted to country-age inactivity shares; five-year groups from age 25',reuse_status='DO_NOT_REUSE_WITHOUT_CHINA_DISTRIBUTION',source_url=rand),
 row(id='RAND_PLUS20',source='RAND RR4291 scenario 2',country='China application',sex='Both',value='20% activity amount increase',lower='',upper='',measure='Individual activity amount',input_origin='Distribution required',method='Multiplicative shift for nonzero activity; zero stays zero',reuse_status='EXTENSION_DATA_BLOCKED',source_url=rand),
 row(id='DING2016',source='Ding et al. Lancet 2016',country='China included in global cost analysis',sex='Both',value='',lower='',upper='',measure='PAF and direct/indirect costs',input_origin='National inactivity prevalence and disease cost inputs',method='Cost-of-illness attribution, not an individual MET distribution',reuse_status='REFERENCE_ONLY',source_url='https://pubmed.ncbi.nlm.nih.gov/27475266/')])
write('ding_china_published_outputs.csv',[
 row(source='Ding et al. Lancet 2016 Table 1',country='China',year=2013,measure='Direct health-care costs attributable to physical inactivity',value_thousand_INT_dollars=3075139,lower_thousand_INT_dollars=1194333,upper_thousand_INT_dollars=6635493,role='PUBLISHED_OUTPUT_REFERENCE_NOT_MODEL_INPUT',source_url='https://www.icsspe.org/system/files/Ding%20et%20al.%20-%20The%20economic%20burden%20of%20physical%20inactivity%20a%20global%20analysis.pdf'),
 row(source='Ding et al. Lancet 2016 Table 1',country='China',year=2013,measure='Indirect productivity costs attributable to physical inactivity',value_thousand_INT_dollars=1783000,lower_thousand_INT_dollars=622150,upper_thousand_INT_dollars=3555485,role='PUBLISHED_OUTPUT_REFERENCE_NOT_MODEL_INPUT',source_url='https://www.icsspe.org/system/files/Ding%20et%20al.%20-%20The%20economic%20burden%20of%20physical%20inactivity%20a%20global%20analysis.pdf')])

direct_from_total=19144.36*0.3251
write('jia_cost_verification.csv',[
 row(item='Jia 2018 Table 2 outpatient',cases=2138,amount_usd=2501.18,formula='',derived_usd='',status='SOURCE_VERIFIED',source_location='Table 2 page 487',source_url=jia),
 row(item='Jia 2018 Table 2 hospitalization',cases=1304,amount_usd=9692.09,formula='',derived_usd='',status='SOURCE_VERIFIED',source_location='Table 2 page 487',source_url=jia),
 row(item='Jia 2018 Table 2 out of pocket',cases=3023,amount_usd=468.97,formula='',derived_usd='',status='SOURCE_VERIFIED',source_location='Table 2 page 487',source_url=jia),
 row(item='Jia 2018 annual total social per AD patient',cases=3046,amount_usd=19144.36,formula='',derived_usd='',status='SOURCE_VERIFIED',source_location='Table 2 page 487; Results',source_url=jia),
 row(item='Direct medical share of national total',cases='',amount_usd='',formula='19,144.36 * 0.3251',derived_usd=f'{direct_from_total:.2f}',status='APPROXIMATE_DERIVATION_NOT_6225_EXACT',source_location='Results 32.51%; rounded aggregate share',source_url=jia),
 row(item='Legacy direct medical amount',cases='',amount_usd=6225,formula='Exact original derivation not documented',derived_usd='',status='NOT_RESTORED_EXACT',source_location='Legacy cost candidate only',source_url=''),
 row(item='Jia model admission',cases='',amount_usd='',formula='',derived_usd='',status='EXCLUDED_MAIN_DEMENTIA',source_location='Work exclusion; AD not all dementia; cost population and coverage differ',source_url=jia)])

oldq=read(R1/'registers/gbd_query_requests.csv')
oldq=[x for x in oldq if any(z in x['expected_file'] for z in ('142807b4','5f1ccb48','c66ef291','c6f1d9b8'))]
write('gbd_old_value_reconstruction_requests.csv',[dict(**x,request_type='LEGACY_VALUE_TRACE_ONLY',tool_age_support='NOT_CHECKED_FOR_2023',tool_cause_support='NOT_CHECKED_FOR_2023',action='Manual authenticated download if available; preserve full old query') for x in oldq])
write('gbd_new_model_download_requests.csv',[
 row(request_id='NEW01',purpose='New model 2023 disease rates',tool='IHME GBD Results Tool',version='GBD 2023',location='China',year='2023',sex='Male|Female',age='20–24 to 95–99 and 100+ separately where supported; do not substitute 70+ aggregate',measure='Incidence|Deaths|YLL|YLD|DALY|Prevalence as cause-valid',metric='Rate and Number',cause='IHD|ischemic stroke|T2D|female breast|colon-only|other eligible disease subtype',age_cause_capability='NOT_CHECKED_IN_LIVE_2023_TOOL',download_status='MANUAL_AUTH_REQUIRED',artifacts='CSV/ZIP; query screenshot; codebook; citation; timestamp; SHA256; row reconciliation',url=ihme),
 row(request_id='NEW02',purpose='Cause/age capability check',tool='IHME GBD Results Tool',version='GBD 2023',location='China',year='2023',sex='Male|Female',age='Check 100+ and each 70–74 through 95–99; measure-specific availability',measure='Each requested endpoint',metric='Rate|Number',cause='Check colon-only versus colon and rectum; esophageal adenocarcinoma; gastric cardia; endometrial subtype',age_cause_capability='GENERIC_OLDER_GUIDE_ONLY; EXACT_2023_NOT_CHECKED',download_status='MANUAL_AUTH_REQUIRED',artifacts='2023 tool menu screenshot/codebook and unsupported filter notes',url=ihme)])
cause_specs=[
 ('coronary_heart_disease','493','Ischemic heart disease','EXACT_CANDIDATE'),('stroke','495','Ischemic stroke','IS_ONLY'),('type2_diabetes','976','Diabetes mellitus type 2','TYPE2'),('breast_cancer','429','Breast cancer','FEMALE_ONLY'),('colon_cancer','','Colon cancer, excluding rectum','CAUSE_ID_NOT_VERIFIED'),('depression','567','Depressive disorders','DEATHS_YLL_NA'),('bladder_cancer','','Bladder cancer','CAUSE_ID_TO_VERIFY'),('endometrial_cancer','','Endometrial cancer subtype','FEMALE_ONLY_CAUSE_TO_VERIFY'),('renal_cancer','','Kidney cancer','CAUSE_ID_TO_VERIFY'),('oesophageal_cancer','','Esophageal adenocarcinoma subtype','SUBTYPE_TO_VERIFY'),('gastric_cancer','','Gastric cardia cancer subtype','SUBTYPE_TO_VERIFY')]
measures=[('Incidence','6'),('Deaths','1'),('YLL','4'),('YLD','3'),('DALY','2'),('Prevalence','5')]
write('gbd_new_model_detailed_requests.csv',[row(request_id=f'NM-{o}-{meas}',outcome_id=o,GBD_cause_id_candidate=cid,GBD_cause_label_required=label,cause_status=cstat,GBD_measure_id=mid,GBD_measure=meas,metric='Rate|Number',GBD_location='6:China',GBD_population='1:All Population',year='2023',sex='1:Male|2:Female' if cstat not in ('FEMALE_ONLY','FEMALE_ONLY_CAUSE_TO_VERIFY') else '2:Female',age='20–24|25–29|30–34|35–39|40–44|45–49|50–54|55–59|60–64|65–69|70–74|75–79|80–84|85–89|90–94|95–99|100+',tool_filter_status='VERIFY_IN_AUTHENTICATED_GBD2023_MENU',request_status='NOT_APPLICABLE' if o=='depression' and meas in ('Deaths','YLL') else 'MANUAL_AUTH_REQUIRED',required_artifacts='source CSV/ZIP|citation|complete filter screenshot|codebook|download date|SHA256|row comparison',url=ihme) for o,cid,label,cstat in cause_specs for meas,mid in measures])
write('incidence_to_other_outcomes_requirements.csv',[
 row(destination='Prevalent patient-years',needed='Disease-specific incidence, remission, survival, mortality, duration, lag and baseline prevalence by sex-age-year',existing_evidence='GBD prevalence Number candidate lacks recent raw; no transition matrix',method_gate='WORK_PENDING',model_ready='NO'),
 row(destination='Deaths',needed='Cause-specific fatality or mortality RR; lag/competing mortality or Work-approved proportional attribution',existing_evidence='Kyu incidence/events RR does not separately estimate deaths',method_gate='WORK_PENDING',model_ready='NO'),
 row(destination='YLL|YLD|DALY',needed='Cause/endpoint-specific GBD rates or counts with valid attribution method and UI treatment',existing_evidence='2018–2023 exports missing except IHD/IS incidence Number',method_gate='WORK_PENDING',model_ready='NO'),
 row(destination='Direct medical cost',needed='Matched health quantity, annual/first-year cost, coverage, price year, overlapping complication boundaries',existing_evidence='T2D2019 and CRC2014 remain candidate, no coverage',method_gate='WORK_PENDING',model_ready='NO')])

write('evidence_acquisition_log.csv',[
 row(item='Jia2018_fulltext.pdf',url=jia,attempt='Original CCMU URL returned 404; alternate CCMU news URL downloaded',date=DATE,status='DOWNLOADED_VERIFIED',file='raw/Jia2018_fulltext.pdf',sha256=sha(OUT/'raw/Jia2018_fulltext.pdf')),
 row(item='RAND_RR4291.pdf',url=rand,attempt='Public report accessible via web index; direct local download returned CloudFront 403',date=DATE,status='TEXT_REVIEWED_FILE_NOT_ARCHIVED',file='',sha256=''),
 row(item='Kyu appendix 4',url='https://pmc.ncbi.nlm.nih.gov/articles/PMC4979358/',attempt='Read first-round archived supplementary PDF; no redownload',date=DATE,status='EXISTING_FILE_REVIEWED',file='round1_20261112/raw/pmc_cloud/PMC4979358/kyuh031211.ww4_2kb.pdf',sha256=sha(R1/'raw/pmc_cloud/PMC4979358/kyuh031211.ww4_2kb.pdf')),
 row(item='Schuch 2018',url=schuch,attempt='Publisher abstract/metadata reviewed; old saved HTML is verification page',date=DATE,status='ABSTRACT_ONLY',file='',sha256=''),
 row(item='Ding2016_fulltext.pdf',url='https://www.icsspe.org/system/files/Ding%20et%20al.%20-%20The%20economic%20burden%20of%20physical%20inactivity%20a%20global%20analysis.pdf',attempt='Public PDF indexed and Table 1 text reviewed; direct download rejected invalid remote certificate (NotTimeValid); no TLS bypass',date=DATE,status='TEXT_REVIEWED_FILE_NOT_ARCHIVED',file='',sha256='')])

checks=[
 ('branch_base','PASS','Generated on designated branch from specified commit; confirm via git below'),
 ('2010_reference_value','PASS','Zhang Table 2: 17.9 (16.3–19.5), adults 18+, China 2010 age standard'),
 ('2010_sex_age_joint','FAIL','Only sex and age separately; no joint cells for 20+ target'),
 ('target_numeric_release','NOT_APPLICABLE','Comparability failed; no numeric target or attainment gap released'),
 ('scenario_formula','PASS','0.85 times 2010 reference; not 2025 or percentage-point subtraction'),
 ('fine_age_shared_parameter','PASS','Copied coarse rates have same source id and CI'),
 ('population_source_columns','PASS','Each row marks PopMale or PopFemale'),
 ('RR_effect_type_Schuch','PASS','Adult subgroup adjusted OR 0.78 (0.70–0.87); not RR'),
 ('Kyu_all_diabetes_type2','NOT_CHECKED','Search strategy says type 2; Table C generic diabetes and ages 15+; study-level complete definition not confirmed'),
 ('endpoint_six_way_method','FAIL','Work has not authorized automatic same-PIF application'),
 ('GBD_2023_live_cause_age_capability','NOT_CHECKED','Older generic guide only; actual logged-in 2023 menu not inspected'),
 ('Jia_6225_exact_chain','FAIL','Table 2 and 32.51% share available; 19,144.36*0.3251=6,223.83, not exact 6,225'),
 ('model_run','NOT_CHECKED','No runtime execution audit; builder contains data-register operations only'),
 ('prior_round_files_preserved','PASS','Verified with git diff against base for round1/round2 paths')]
report=dict(branch='codex/data-round2-target-prep-20261112',base_commit='67addc23590666461ea065294c382da5a72e7287',date=DATE,checks=[dict(id=i,status=s,evidence=e) for i,s,e in checks],status_counts=dict(Counter(s for _,s,_ in checks)),note='FAIL describes an evidence gate, not a failed file-integrity operation.')
with (CHECK/'validation_target_prep.json').open('w',encoding='utf-8',newline='\n') as f:f.write(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report['status_counts']))
