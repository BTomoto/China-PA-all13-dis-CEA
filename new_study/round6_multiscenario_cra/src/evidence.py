"""Separate source verification from exposure and clinical endpoint admission."""
from .common import ROOT,R6,config,read_csv
from .sources import KYU,PA,POP
from .analysis import LEGACY_RR

RAND='https://www.rand.org/content/dam/rand/pubs/research_reports/RR4200/RR4291/RAND_RR4291.pdf'
KYU_URL='https://doi.org/10.1136/bmj.i3857'
GBD_URL='https://doi.org/10.1016/S0140-6736(25)01637-X'
STROKE_URL='https://doi.org/10.1159/000552065'
GBD_CVD='https://www.jacc.org/doi/suppl/10.1016/j.jacc.2025.08.015/suppl_file/mmc2.pdf'
WHO='https://www.who.int/Data/Gho/Data/Themes/Topics/Indicator-Groups/Insufficient-Physical-Activity-Indicator-Group'

def endpoint_admission():
    rows=[]
    for disease in ['IHD','IS']:
        for endpoint in ['Incidence','Deaths','YLD','YLL','DALY','Prevalence','Prevalent_equivalent_patient_years']:
            incidence=endpoint=='Incidence'
            reason=('Kyu protocol p2 includes new diagnoses and mortality; no incidence-only fitted curve identified. '+('Exact GBD2023 MI first/recurrent event aggregation needs primary appendix verification; IHD cause-name match is insufficient.' if disease=='IHD' else 'GBD2023 stroke first-ever lifetime definition corroborated by GBD authors 2026 Methods; pooled Kyu outcome selection still unresolved.')) if incidence else 'No endpoint-specific admitted risk function or approved public cross-endpoint CRA mapping; GBD availability alone does not admit attribution.'
            rows.append(dict(disease=disease,endpoint=endpoint,source_status='SOURCE_VERIFIED',rr_source=KYU_URL,rr_location='Protocol appendix1 p2; appendix4 Tables D/E p43-66; Table F p79-80',risk_exposure='total activity; gross MET-min/week; 0 reference for continuous grid; <600 reference for category RR',rr_effect_type='pooled RR from prospective RR/HR/OR reports',rr_source_outcomes='new diagnoses and mortality eligible; not a separately verified incidence-only curve',age_sex_applicability='adult cohorts >=15 eligibility; apply China20+ only after mapping review; no fine-age/sex RR provided',GBD_source=GBD_URL,GBD_definition_source=GBD_CVD if disease=='IHD' else STROKE_URL,GBD_definition_status='PRIMARY_APPENDIX_PENDING' if disease=='IHD' else 'FIRST_EVER_CORROBORATED_PRIMARY_APPENDIX_PENDING',admission_status='BLOCKED_ENDPOINT_ALIGNMENT' if incidence else 'BLOCKED_OUTCOME_RISK_MAPPING',reason=reason,release_condition='Obtain audited incidence-only pooled RR/function with matching first/recurrent event definition' if incidence else 'Admit an endpoint-specific function or separately approved structural CRA mapping; never restore natural-history model'))
    return rows

def exposure_inventory():
    return [
        dict(input_id='CCDRFS2018_INACTIVE',source_file=PA,source_year=2018,domain='total work/transport/recreation',unit='probability below 600 total MET-min/week',energy_convention='GPAQ conventional gross scoring; not marginal MET',population='China adults18+ source; 20+ model crosswalk',stratification='Male/Female x 6 coarse ages; mapped to five-year groups',availability='AVAILABLE_AGGREGATE',admission_status='SOURCE_VERIFIED',limitation='No individual x, no zero mass, no fine distribution; shared coarse-age CI parameters'),
        dict(input_id='MODEL2025_BASELINE',source_file='round2 population whitelist + exposure crosswalk',source_year='2018 exposure; WPP2025',domain='total',unit='model prevalence',energy_convention='same source scoring',population='China20+',stratification='age x sex',availability='AVAILABLE_DERIVED',admission_status='DERIVED_FROM_VERIFIED_SOURCE',limitation='21.9660515% is population-weighted model start, not observed2025 survey'),
        dict(input_id='CHINA_ACTIVITY_DISTRIBUTION',source_file='',source_year='',domain='total required',unit='MET-min/week',energy_convention='gross required',population='China20+',stratification='sex x age x measured activity',availability='MISSING',admission_status='BLOCKED_NO_SOURCE',limitation='Need approved weighted exposure atoms or sufficiently fine histograms, zero mass, tails and survey design; no raw microdata upload'),
        dict(input_id='ACTIVE_THREE_CATEGORY_SHARES',source_file='',source_year='',domain='total',unit='normalized category weights',energy_convention='gross',population='China20+',stratification='sex x age',availability='MISSING',admission_status='BLOCKED_NO_SOURCE',limitation='Only p<600 known. Do not fabricate 600-3999/4000-7999/>=8000 shares'),
        dict(input_id='RAND_GENERIC_SHAPE',source_file=RAND,source_year=2019,domain='survey activity shape',unit='MET-min/week',energy_convention='not validated as CCDRFS total gross distribution',population='European template extrapolation',stratification='generic shape shifted to country inactivity',availability='METHOD_DESCRIBED_NOT_CHINA_DATA',admission_status='NOT_APPLICABLE',limitation='Appendix C.1 p150-151 (PDF176-177); not substituted for China measured distribution'),
        dict(input_id='MARGINAL_OR_LEISURE_RR',source_file='',source_year='',domain='different exposure domain',unit='marginal MET or leisure-only MET',energy_convention='incompatible without intensity-duration information',population='not admitted',stratification='',availability='NOT_USED',admission_status='NOT_APPLICABLE',limitation='Do not subtract one MET or convert a scalar without duration/intensity and domain information')]

def register_parameters(grid,categories,rates,baseline):
    rows=[]
    def add(parameter_id,definition,unit,value,source,year,location,status,**kw):
        row=dict(parameter_id=parameter_id,definition=definition,unit=unit,disease=kw.pop('disease','ALL'),age=kw.pop('age','20+'),sex=kw.pop('sex','Male/Female'),value_or_function=value,source=source,source_year=year,source_location=location,conversion_formula=kw.pop('conversion','none'),applicability=kw.pop('applicability',''),uncertainty=kw.pop('uncertainty','not propagated; no PSA'),admission_status=status,notes=kw.pop('notes',''))
        if kw:raise ValueError(kw)
        rows.append(row)
    add('POP_WPP2024','WPP model-estimated July1 Medium sex-age population','persons',POP,'UN WPP2024 official; see locked round2 provenance',2024,'PopMale/PopFemale columns; five-year ages20-24 through100+','SOURCE_VERIFIED',conversion='95+=sum(95-99,100+); no high-age rate disaggregation',applicability='2025-2050 China20+')
    add('CCDRFS_THRESHOLD_EQUIVALENCE','Gao source defines insufficient activity as <150 moderate-equivalent minutes/week','threshold equivalence only','4*(moderate_minutes+2*vigorous_minutes)<600','https://html.rhhz.net/zhlxbx/20230803.htm',2018,'Methods sections2-3; publication2023','DERIVED_FROM_VERIFIED_SOURCE',conversion='Conventional gross scoring 4MET moderate and8MET vigorous yields same binary threshold; no continuous activity distribution recovered',applicability='Total work/transport/recreation; retains source bouts>=10min',notes='Not a conversion from marginalMET or a claim that Gao directly published continuous MET doses')
    for r in baseline:
        if r['year']!=2025:continue
        add('PA_'+r['sex']+'_'+r['age'],'model inactive fraction from 2018 coarse survey estimate','probability',r['p_inactive'],PA,2018,'Gao2023 Table2; '+r['source_age'],'DERIVED_FROM_VERIFIED_SOURCE',age=r['age'],sex=r['sex'],conversion='copy coarse age rate; WPP2025 weights for national summary',uncertainty=f"source95CI={r['lower_95']},{r['upper_95']}; shared={r['shared_parameter_id']}; not independent draws",notes='2025 model baseline, not measured2025')
    for r in grid:
        add(f"KYU_F_{r['disease']}_{r['dose']}",'published continuous-dose RR grid point','RR vs zero total activity',r['estimate'],KYU_URL,2016,f"appendix4 TableF p{r['source_page']}; dose={r['dose']}",'SOURCE_VERIFIED',disease=r['disease'],age='adult cohorts15+ eligibility',uncertainty=f"lower={r['lower']};upper={r['upper']}; pointwiseUI; joint spline draws unavailable",applicability='Source value verified; endpoint alignment and continuous exposure distribution not admitted',notes='600 point differs from 600-3999 category RR; no tail extrapolation')
    for disease,rr in categories.items():
        for cat,v in zip(['<600','600-3999','4000-7999','>=8000'],rr):
            add(f'KYU_CAT_{disease}_{cat}','category-average RR','RR vs <600',v,KYU_URL,2016,'main Table1','SOURCE_VERIFIED',disease=disease,uncertainty='Original category UI retained in round4 kyu_category_rr.csv; not propagated',applicability='Categorical diagnostic envelope only; not exact-dose RR')
    for (disease,sex,age),(v,lo,hi) in sorted(rates.items()):
        add(f'GBD_INC_{disease}_{sex}_{age}','GBD2023 population incidence rate','reported incident units/100000 person-years',v,GBD_URL,2023,'SHA-verified original incidence export','SOURCE_VERIFIED',disease=disease,age=age,sex=sex,conversion='baseline expected units=WPP_population*rate/100000',uncertainty=f'GBD marginal UI={lo},{hi}; not cohort observations',applicability='B0 descriptive projection; intervention endpoint admission pending')
    for scenario,definition in [('B0','age-sex exposure fixed'),('P15','proportional weighted share of original <600 moves to600; fraction .03*(year-2025), capped .15'),('R1','max(x,600)'),('R2','1.2*x including zeros'),('R3','600 if original x<600 else1.2*x')]:
        add('SCENARIO_'+scenario,definition,'total gross MET-min/week transformation',definition,'Researcher Work round6 decision',2026,'pasted instructions section3','SCENARIO_ASSUMPTION',applicability='Observed activity distribution required for point risk estimation')
    add('COMMON_PATH','baseline-target distribution mixture','completion fraction','c=(year-2025)/5 clamped0-1','Researcher Work round6',2026,'section4','SCENARIO_ASSUMPTION',conversion='distribution=(1-c)*baseline+c*target; never RR interpolation')
    add('FIXED_DISEASE_RATES','hold 2023 age-sex rates fixed','rate projection','rate_y=rate_2023','Researcher Work round6',2026,'section8','SCENARIO_ASSUMPTION')
    add('INSTANT_RESPONSE','no risk-effect lag quantified','cumulative interpretation','instant risk response assumption; lag remains unestimated','Researcher Work round6',2026,'section8','SCENARIO_ASSUMPTION',notes='Endpoint counterfactual is separate from calendar-year realised benefit')
    add('CATEGORY_BOUND','envelope over unknown active category allocations','PIF interval','alpha*p*(1-r_low)/(p+(1-p)*r_active_extreme)','Algebra derived from category PIF',2026,'METHODS_MULTISCENARIO_CRA','STRUCTURAL_SENSITIVITY_ONLY',notes='Identification envelope, not95%UI; no active category proportions imputed; not mapped to GBD health outcomes')
    for disease,value in LEGACY_RR.items():
        add('LEGACY_BINARY_RR_'+disease,'fixed historical RR literal used only in independent oldP15 regression','RR inactive vs low-active category',value,'round3 health_pilot.py RR constants; Kyu2016 category source',2016,'old binary regression interface','STRUCTURAL_SENSITIVITY_ONLY',disease=disease,conversion='Historical rounded reciprocal of low-active category RR; all active people assigned the low-active reference in old denominator',applicability='Regression only, never current clinical admission',notes='Retained as a code consistency vector; not a newly admitted exact600 effect')
    return rows
