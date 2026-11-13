import contextlib,csv,io,json,math,re,shutil,subprocess,sys,time,zipfile
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
from xml.etree import ElementTree as ET
import numpy as np
from .model import HERE,ROOT,AGES,Blocked,read,write,jwrite,sha,population,gbd,rr,transformed,alpha,pif_atoms,admission,bounds

BASE='1a2a8f11a0dd5c813d2cd35b18e906ea66dedc50'
BRANCH='codex/burden-evidence-round7'
KYU='new_study/round1_20261112/raw/pmc_cloud/PMC4979358/kyuh031211.ww4_2kb.pdf'
KYU_URL='https://doi.org/10.1136/bmj.i3857'
BRAZIL='https://doi.org/10.1093/pubmed/fdy183'
CKB='https://pmc.ncbi.nlm.nih.gov/articles/PMC12277735/'
CHNS='https://pmc.ncbi.nlm.nih.gov/articles/PMC5850940/'
STROKE='https://doi.org/10.1136/svn-2023-002296'
NBS='https://www.stats.gov.cn/sj/zxfb/202605/t20260515_1963707.html'
def textfile(path,text):
    p=HERE/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text.strip()+'\n',encoding='utf-8',newline='\n')
def setup():
    for p in ['inputs','registers','results','reports','figures','notebooks','logs']: (HERE/p).mkdir(exist_ok=True)
    c=dict(base_commit=BASE,branch=BRANCH,population='new_study/round2_20261112/registers/population_input_whitelist_v1.csv',exposure='new_study/round2_target_prep_20261112/registers/exposure_crosswalk_ci_v2.csv',gbd=['new_study/round1_20261112/handoff/continuation/source_data/gbd/IHME-GBD_2023_DATA-85af7c45-1.zip','new_study/round4_dynamic_health_model_20261112/raw/IHME-GBD_2023_DATA-353a02a2-1.zip'],main_year=2030,scenarios=dict(B0='identity',P15='proportional split: inactive fraction alpha(year) moves to EXACT 600',R1='max(x,600)',R2='1.2*x',R3='600 if baseline x<600 else 1.2*x'),P15_alpha='min(0.15,max(0,0.03*(year-2025)))',primary_point_results='NOT_IDENTIFIED_WITH_BINARY_MARGIN_ONLY',mortality_sensitivity_age='30-69 only; public CRA precedent; no direct mortality curve claimed',instantaneous_risk_response='STRUCTURAL_ASSUMPTION_NO_LAG',cumulative_windows=[[2025,2029],[2025,2030],[2025,2034],[2025,2050]])
    jwrite(HERE/'config.json',c)
    locks=json.loads((ROOT/'new_study/round6_multiscenario_cra/config/source_lock.json').read_text('utf-8'))
    jwrite(HERE/'inputs/source_locks.json',locks)
    for p,h in locks.items():
        if sha(ROOT/p)!=h:raise Blocked('historical locked input changed: '+p)
    shutil.copyfile(ROOT/'new_study/round4_dynamic_health_model_20261112/inputs/kyu_category_rr.csv',HERE/'inputs/kyu_category_rr.csv')

def extract_evidence():
    from pypdf import PdfReader
    reader=PdfReader(ROOT/KYU);grid=[];names=['breast_cancer','colon_cancer','T2D','IHD','IS']
    for d in names:grid.append(dict(disease=d,dose=0,estimate=1.,lower='',upper='',source=KYU,table='F',page=79))
    for page in [78,79]:
        for line in reader.pages[page].extract_text().splitlines():
            m=re.match(r'^([\d,]+)\s+(.+)',line.strip())
            if not m or '(' not in m[2]:continue
            dose=int(m[1].replace(',',''))
            if not 600<=dose<=30600 or dose%600:continue
            cells=re.findall(r'([\d.][\d.\s]*)\(([^)]+)\)',m[2])
            if len(cells)!=5:raise Blocked('Table F parse')
            for index,d in enumerate(names):
                point=float(re.sub(r'\s','',cells[index][0]));lo,hi=[float(re.sub(r'\s','',x)) for x in cells[index][1].split(',')]
                if not 0<lo<=point<=hi:raise Blocked('Table F bounds')
                grid.append(dict(disease=d,dose=dose,estimate=point,lower=lo,upper=hi,source=KYU,table='F',page=page+1))
    if len(grid)!=260:raise Blocked('five published grids incomplete')
    write(HERE/'inputs/kyu_published_grid.csv',grid)
    registers=[]
    for d in names:
        registers.append(dict(rr_id='KYU_CONT_'+d,outcome_id=d,source=KYU_URL,source_file=KYU,source_sha256=sha(ROOT/KYU),location='Appendix4 Table F pp79-80; Tables A-E; protocol appendix1 p2',source_status='VERIFIED_PUBLISHED_GRID',exposure='total activity gross MET-min/week; domain-specific studies were mapped by original authors',reference='zero total activity; NOT inactive-vs-low category RR',support_min=0,support_max=30600,effect_measure='pooled RR derived from prospective RR/HR/OR reports',dose_interpolation='piecewise linear log RR within published grid only',age_sex='pooled adult cohorts; not age/sex specific; transport to China20+ is an assumption; breast female only',event_use='STRUCTURAL_CRA_ENVELOPE' if d in ['IHD','IS'] else 'CONDITIONAL_NO_CURRENT_2023_BURDEN',mortality_use='PUBLIC_CRA_PRECEDENT_STRUCTURAL_SENSITIVITY_30_69' if d in ['IHD','IS'] else 'NOT_RELEASED',burden_mapping='No automatic YLD/YLL/DALY/prevalence application',source_selection_review='Tables D/E include prospective event studies and cause-specific mortality; no incidence-only or mortality-only fitted grid supplied',tail_rule='NONE; observed tail weight UNKNOWN; support-free envelopes do not evaluate any tail RR',remaining_gap='China weighted dose distribution including zero/within<600 and active tail; first/recurrent endpoint transport remains structural'+('; Carlsson2007 title mentions LADA but abstract also reports T2D738 cases; need exact selected PA row, not exclusion by title' if d=='T2D' else '')))
    for d,source,why in [('IHD','https://pubmed.ncbi.nlm.nih.gov/30770126/','ACS cost evidence, NOT a PA risk function'),('all_cause',CKB,'CKB incidence and mortality separately measured, total includes light activity, 31st percentile inactivity threshold; NOT a 600 MET threshold curve'),('stroke_subtypes','https://academic.oup.com/jpubhealth/article/47/3/567/8118854','2025 total/leisure subtype meta-analysis candidate; extraction and gross/marginal/support audit pending')]:
        if d=='IHD':continue
        registers.append(dict.fromkeys(registers[0],''));registers[-1].update(rr_id='ALTERNATIVE_'+d,outcome_id=d,source=source,source_status='PUBLIC_TEXT_SCREENED',exposure='requires exact domain/energy review',event_use='NOT_ADMITTED',mortality_use='NOT_ADMITTED',remaining_gap=why)
    for d,source,measure,estimate,lo,hi,comparison,gap in [
       ('hypertension','https://pubmed.ncbi.nlm.nih.gov/28348016/','RR',.94,.92,.96,'per10MET-h/week leisure-time increment; not binary total inactivity','leisure exposure; need total PA curve and hypertension first-incidence source'),
       ('depression','https://pubmed.ncbi.nlm.nih.gov/29690792/','adjusted OR',.78,.70,.87,'adult subgroup high-vs-low source-defined PA; not <600 vs600','adult age cutoff and exposure scale; OR not converted toRR; separate older subgroup'),
       ('bladder_cancer','https://pmc.ncbi.nlm.nih.gov/articles/PMC8478970/','legacy candidate RR','','','','leisure PA proxy per historical source trace','primary contrast/dose/outcome extraction and total-domain match'),
       ('endometrial_cancer','https://pmc.ncbi.nlm.nih.gov/articles/PMC8478970/','legacy candidate RR','','','','leisure PA proxy; female only','histologic endometrium vs Uterine cancer burden; exposure domain'),
       ('kidney_cancer','https://pmc.ncbi.nlm.nih.gov/articles/PMC8478970/','legacy candidate RR','','','','leisure PA proxy','domain and original primary risk source'),
       ('oesophageal_adenocarcinoma','https://pmc.ncbi.nlm.nih.gov/articles/PMC8478970/','legacy candidate RR','','','','adenocarcinoma leisure PA proxy','adenocarcinoma burden; no all-esophageal substitution'),
       ('gastric_cardia_cancer','https://pmc.ncbi.nlm.nih.gov/articles/PMC8478970/','legacy candidate RR','','','','cardia leisure PA proxy','cardia-specific burden; no whole-stomach substitution'),
       ('dementia','https://pmc.ncbi.nlm.nih.gov/articles/PMC6468884/','HR exclusion evidence','','','','long followup evidence; historical1.40source inconsistent','no admitted totalPA600 curve; distinguish AD from dementia; no source-value substitution')]:
        row=dict.fromkeys(registers[0],'');row.update(rr_id='CANDIDATE_'+d,outcome_id=d,source=source,source_status='PUBLIC_PRIMARY_ABSTRACT_VERIFIED' if d in ['hypertension','depression'] else 'HISTORICAL_SOURCE_TRACE_NOT_NEW_NUMERIC_REVERIFICATION',exposure=comparison,effect_measure=measure,event_use='CONDITIONAL_NOT_ADMITTED',mortality_use='NOT_ADMITTED',remaining_gap=gap)
        abstract_file='Liu2017_abstract.json' if d=='hypertension' else 'Schuch2018_abstract.json' if d=='depression' else ''
        if abstract_file and (HERE/'raw'/abstract_file).exists():row.update(source_file='raw/'+abstract_file,source_sha256=sha(HERE/'raw'/abstract_file),location='original article abstract in EuropePMC MED core metadata; NOT full text')
        elif d not in ['hypertension','depression']:row.update(source_file='new_study/round1_20261112/registers/rr_numeric_provenance.csv',source_sha256=sha(ROOT/'new_study/round1_20261112/registers/rr_numeric_provenance.csv'),location='historical source trace only; no new primary effect extraction')
        registers.append(row)
        for a in registers:
            for f in ['source_reported_estimate','source_reported_lower','source_reported_upper']:a.setdefault(f,'')
        row.update(source_reported_estimate=estimate,source_reported_lower=lo,source_reported_upper=hi)
    write(HERE/'registers/rr_function_register.csv',registers)
    # Published, non-identifiable participant summary, NOT individual records or nationally weighted data.
    root=ET.parse(HERE/'raw/China_CKB_PA_phenome.xml');table=next(n for n in root.iter('table-wrap') if n.attrib.get('id')=='tbl1') if any(n.attrib.get('id')=='tbl1' for n in root.iter('table-wrap')) else next(root.iter('table-wrap'))
    counts=[101896,102497,102242,102200,102253]
    if not all(str(n) in ''.join(table.itertext()).replace(',','') for n in counts):raise Blocked('CKB published quintile counts')
    write(HERE/'inputs/china_ckb_published_quintiles.csv',[dict(quintile=i+1,range_MET_h_day=s,participants=n,sample_fraction=n/511088,mean_MET_h_day=m,source=CKB,source_location='Table1',representativeness='unweighted 10-region cohort age30-79 baseline2004-2008; NOT China20+ national',domain='occupation commuting housework leisure including LIGHT activity',admission='METHOD_COMPARISON_ONLY; no conversion to GPAQ MVPA or within-bin distribution') for i,(s,n,m) in enumerate(zip(['<=8.59','8.60-13.99','14.00-21.24','21.25-31.89','>=31.90'],counts,[5.6,11.3,17.3,26.2,41.9]))])
    inventory=[r for r in read(HERE/'registers/exposure_candidate_inventory.csv') if not r['candidate_id'].startswith('PUB-')]
    for id,file,source,year,sample,domain,vars in [('PUB-CKB','China_CKB_PA_phenome.xml',CKB,'2004-2008; resurvey2013-2014','511088; age30-79; 10 regions','all four domains INCLUDING LIGHT','five PA quintile boundaries counts means; zero and within-bin distribution not reported'),('PUB-CHNS','China_CHNS_CVD_projection.html',CHNS,'1991-2011','9 provinces; >=35; nonpregnant; 20 age-sex-urbanicity groups','occupational and domestic detail; total activity assessment requires domain review','4-category definition documented; joint category proportions NOT recovered from main article')]:
        p=HERE/'raw'/file
        inventory.append(dict(candidate_id=id,path=str(p),sha256=sha(p),size_bytes=p.stat().st_size,source=source,year=year,sample=sample,population='Chinese cohort',national_representativeness='NOT_NATIONAL_20PLUS_WEIGHTED',variables_or_members=vars,weights='CKB unweighted published counts; CHNS stratified sample not national survey calibration',activity_domain=domain,authorization='PUBLIC_AGGREGATE_ARTICLE; no individual access',record_access='PUBLISHED_SUMMARIES_ONLY'))
    write(HERE/'registers/exposure_candidate_inventory.csv',inventory)

def matrix():
    # One row per endpoint, explicit permission and scope; no automatic carry-over of Round6 blocks.
    families=[('IHD','IHD','Kyu','verified detailed2023'),('IS','stroke','Kyu; ischemic ONLY','verified detailed2023'),('T2D','T2D','Kyu; exact selected T2D rows still unresolved','originals2010-2017 only'),('breast_cancer','breast_cancer','Kyu female only','originals2010-2017; recent candidate not raw verified'),('colon_cancer','colon_cancer','Kyu colon only; not combinedCRC','only Colon and rectum cancer export; subtype mismatch'),('hypertension','hypertension','Liu RR.94 per10MET-h/week leisure verified; not total600','no qualified first-incidence/prev interface'),('depression','depression','Schuch adult adjustedOR.78(.70,.87) high vs low verified; ORnotRR and no600 contrast','2010-2017 original; recent original missing'),('bladder_cancer','bladder_cancer','leisure activity proxy','originals2010-2017 only'),('endometrial_cancer','endometrial_cancer','leisure activity proxy female only','Uterine cancer export not necessarily endometrial histology'),('kidney_cancer','kidney_cancer','leisure activity proxy','originals2010-2017 only'),('oesophageal_adenocarcinoma','oesophageal_cancer','adenocarcinoma not all oesophageal cancer','all esophageal cancer export subtype mismatch'),('gastric_cardia_cancer','gastric_cancer','cardia not all stomach cancer','all stomach cancer export subtype mismatch'),('dementia','dementia','legacy1.40 source mismatch; no silent substitution','Alzheimer disease AND other dementias combined; not AD only'),('ICH','stroke','no transfer of IS curve','originals2010-2017 only'),('SAH','stroke','no transfer of IS curve','originals2010-2017 only')]
    rows=[]
    for d,f,risk,burden in families:
        for ep in ['Incidence','Deaths','YLD','YLL','DALY','Prevalence']:
            allowed='';status='BLOCKED';reason=risk+'; '+burden
            if d in ['IHD','IS'] and ep in ['Incidence','Deaths']:
                allowed='SUPPORT_FREE_CONTINUOUS|CATEGORY_TARGET_SENSITIVITY';status='PARTIALLY_IDENTIFIED_STRUCTURAL_CRA'
                reason='pooled clinical event curve; cause-event transport is explicit structural sensitivity' if ep=='Incidence' else 'public cause-specific mortality CRA precedent; 30-69 only; not a separately measured mortality RR'
            if (d=='hypertension' and ep in ['Deaths','YLD','YLL','DALY']) or (d=='depression' and ep in ['Deaths','YLL']):status='NOT_APPLICABLE';reason='separate module exclusion; avoid duplicated deaths/burden'
            source=KYU_URL+(' ; '+BRAZIL if ep=='Deaths' and d in ['IHD','IS'] else '') if d in ['IHD','IS','T2D','breast_cancer','colon_cancer'] else 'https://pubmed.ncbi.nlm.nih.gov/28348016/' if d=='hypertension' else 'https://pubmed.ncbi.nlm.nih.gov/29690792/' if d=='depression' else 'https://pmc.ncbi.nlm.nih.gov/articles/PMC6468884/' if d=='dementia' else 'new_study/round1_20261112/registers/rr_numeric_provenance.csv ; https://pmc.ncbi.nlm.nih.gov/articles/PMC8478970/'
            rows.append(dict(evidence_id=f'{d}-{ep}',outcome_id=d,candidate_family=f,endpoint=ep,source_status='VERIFIED_2023' if d in ['IHD','IS'] else 'OLDER_OR_MISMATCHED_SOURCE',exposure_match='BINARY_MARGIN_ONLY',risk_function='KYU_CONT_'+d if d in ['IHD','IS','T2D','breast_cancer','colon_cancer'] else 'CANDIDATE_'+d,endpoint_match='STRUCTURAL_TRANSPORT_NOT_DIRECT_ENDPOINT_RR' if allowed else 'NOT_RELEASED',allowed_uses=allowed,structural_assumptions=reason,source=source,gbd_source=burden,population_scope='China30-69' if d in ['IHD','IS'] and ep=='Deaths' else 'China20+; female only' if d in ['breast_cancer','endometrial_cancer'] else 'China20+',economic_status='NOT_ESTIMATED',model_ready=status,main_point_ready='FALSE',remaining_gap='dose distribution and endpoint transport decision; no YLD/YLL/DALY mapping is implied' if d in ['IHD','IS'] else reason))
    for r in rows:
        if r['outcome_id'] in ['ICH','SAH']:r.update(risk_function='NONE_SUBTYPE_RR',source='new_study/round2_20261112/registers/rr_admission_work_v1.csv')
    write(HERE/'registers/disease_endpoint_evidence_matrix.csv',rows)
    return rows

def economies():
    root=ET.parse(HERE/'raw/China_first_year_IS_CNSR3.xml')
    tables=[''.join(x.itertext()) for x in root.iter('table-wrap')]
    t=next(x for x in tables if 'Cost breakdowns' in x)
    if not all(n in t.replace(' ','').replace('\u2009','') for n in ['26612.67','18143.79','8468.88','28167.25']):raise Blocked('IS economic Table3 extraction')
    medical=[]
    for cid,amount,lo,hi,definition in [('IS-CNSR3-FIRSTYEAR-DM',26612.67,24512.87,28712.46,'12-month stroke-related direct medical cost; index admission plus follow-up'),('IS-CNSR3-INDEX-HOSP',18143.79,16990.97,19296.61,'index hospitalisation ONLY; component of first-year cost; do not add twice'),('IS-CNSR3-FOLLOWUP-DM',8468.88,6860.64,10077.11,'12-month follow-up direct medical; component; do not add twice')]:
        medical.append(dict(cost_id=cid,evidence_id='CNSR3-SVN-2023-002296-T3',disease='IS',estimate=amount,lower=lo,upper=hi,currency='CNY',unit='per first-ever hospitalized surviving patient',observation='index event Feb2017-Feb2018; subsequent12months',original_price_year='NOT_EXPLICITLY_UNIFORM',legacy_assumed_price_year='',sample='520 of2454 screened; survivors; age18-80;20 sites;69.6%male;mean61.64',region='20 geographically diverse Chinese sites; selected subset of CNSRIII',perspective='stroke-related medical resource expenditure; not patient OOP share',coverage='inpatient+followup medical for firstyear total; see component definition',definition=definition,comorbidities='HTN78.8%; AF6%; stroke-related charges; not guaranteed comorbidity-free',representativeness='registry broad geography; selected survivor respondents; not all national cases',source=STROKE,source_file='raw/China_first_year_IS_CNSR3.xml',source_sha256=sha(HERE/'raw/China_first_year_IS_CNSR3.xml'),location='Table3; Methods Patients and Cost data collection',evidence_status='SOURCE_VALUE_VERIFIED',admission='CANDIDATE_MATCHED_SCOPE_ONLY',remaining_gap='calendar-price harmonisation to2025; survivor/treated case coverage; age>80; incident definition alignment; no unconditional national multiplier'))
    medical.append(dict.fromkeys(medical[0],''));medical[-1].update(cost_id='ACS-OMT-FIRSTYEAR-2019',evidence_id='PMID30770126',disease='IHD',estimate=20771,currency='CNY',unit='per treated ACS patient OMT subgroup; all-cause cost',observation='one-year',original_price_year='NOT_CONFIRMED; year2014 FX is NOT proof of uniform price year',sample='Tianjin urban employee claims; OMT vs non-OMT ACS comparison',definition='not incident IHD average; treatment group specific all-cause costs',source='https://pubmed.ncbi.nlm.nih.gov/30770126/',source_file='',location='public abstract Findings',evidence_status='PUBLIC_TEXT_VERIFIED_NO_VALID_LOCAL_FULLTEXT',admission='NOT_ESTIMATED',remaining_gap='fulltext; first-ever event confirmation; IHD vs ACS scope; attributable medical categories; treatment-selection representativeness')
    medical.append(dict.fromkeys(medical[0],''));medical[-1].update(cost_id='T2D-COMPLICATION-MI-QUARTER',evidence_id='HE2020-TIANJIN-INCIDENT-COMPLICATION',disease='T2D',estimate=19633,currency='CNY',unit='incremental MI-complication onset quarter in newly diagnosed T2D; NOT T2D firstyear cost',observation='2009-2014 newly diagnosed T2D followed through2015; onset quarter90days',original_price_year='NOT_CONFIRMED; calendar2008-2015 claims not automatically2025',sample='114847 adult E11; Tianjin UEBMI; mean56.9;45.5%female;12month clean window',region='Tianjin urban employees and retirees',perspective='medical insurance plus patient direct medical payments',coverage='inpatient/outpatient; acuteMI primary inpatient diagnosis',definition='comorbidity-adjusted marginal complication cost; exclude from T2D-own-cost mainline and do not duplicate IHD',source='https://doi.org/10.1007/s13300-020-00967-y',source_file='raw/China_T2D_incident_complications.html' if (HERE/'raw/China_T2D_incident_complications.html').exists() else '',location='Abstract Results; Methods Study Population and Statistical Analysis',evidence_status='PUBLIC_PRIMARY_TEXT_VERIFIED',admission='NOT_ESTIMATED',remaining_gap='T2D-own firstyear management cost without cardiovascular complication; national coverage; uniform priceyear')
    for d in ['T2D','breast_cancer','colon_cancer','hypertension','depression','bladder_cancer','endometrial_cancer','kidney_cancer','oesophageal_adenocarcinoma','gastric_cardia_cancer','dementia']:
        row=dict.fromkeys(medical[0],'');row.update(cost_id='REQUEST-FIRSTYEAR-'+d,evidence_id='NO_MATCHED_FIRSTYEAR_VALUE',disease=d,admission='NOT_ESTIMATED',evidence_status='MATCHED_INCIDENT_COST_MISSING',unit='CNY per Chinese first diagnosis/event; medical only',remaining_gap='retrieve Chinese first diagnosis12-month outpatient+inpatient medical cost; price year, treated coverage, disease subtype and comorbidity scope; do not multiply legacy annual prevalent costs by incident cases');medical.append(row)
    for r in medical:
        if r['cost_id']=='ACS-OMT-FIRSTYEAR-2019' and (HERE/'raw/ACS2019_abstract.json').exists():r.update(source_file='raw/ACS2019_abstract.json',source_sha256=sha(HERE/'raw/ACS2019_abstract.json'),location='original article abstract mirrored in EuropePMC MED core metadata; NOT fulltext')
    write(HERE/'registers/medical_cost_evidence_register.csv',medical)
    prod=[]
    for pid,val,unit,scope,source,loc,status,gap in [
      ('WAGE-2025-URBAN-NONPRIVATE',129441,'CNY per employee-year','urban nonprivate legal entity employment, NOT all Chinese workers age-sex wage',NBS,'Table1 total2025','SOURCE_VERIFIED_SCOPE_LIMITED','national age-sex employment probabilities, private/self-employed/rural composition; no uniform national multiplier'),
      ('WAGE-2025-URBAN-PRIVATE',71590,'CNY per employee-year','urban private legal entity employment; NOT self-employed or all population',NBS,'Table4 total2025','SOURCE_VERIFIED_SCOPE_LIMITED','age-sex employee coverage and wage mix'),
      ('IS-PATIENT-INDEX-LOST-WAGES',1767.05,'CNY per selected first-ever IS survivor','index patient productivity, not informal caregiver loss',STROKE,'Table3 index patient productivity loss','SOURCE_VALUE_VERIFIED_CANDIDATE','original study uses2020 urban nonprivate wage97379/250; not transferable to all China2025 cases'),
      ('IS-PATIENT-FOLLOWUP-LOST-WAGES',14669.77,'CNY per selected first-ever IS survivor','follow-up patient productivity only; indirect total28167.25 includes informal care',STROKE,'Table3 follow-up patient productivity loss','SOURCE_VALUE_VERIFIED_CANDIDATE','work status selection; actual days by age-sex; wage weighting and retirement; no caregiver cost duplication'),
      ('RAND-ABSENCE-PRESENTEEISM','0.8-1.2','percentage points of work impairment','voluntary employer surveys UK and six Asia-Pacific locations; mainland China NOT sampled','https://pmc.ncbi.nlm.nih.gov/articles/PMC7719903/','Methods Workplace productivity; Table2; N120143','METHOD_COMPARISON_ONLY','China total PA dose response, causal interpretation, WPAI and workforce representativeness; do not import as China main effect'),
      ('EMPLOYMENT-AGE-SEX','','probability','China20+ fiveyear age Male/Female employment and participation separately','https://www.stats.gov.cn/sj/ndsj/','China Population and Employment Statistics Yearbook; exact table/access pending','MISSING_JOINT_TABLE','obtain year2025 or nearest survey employment/population by sex age; education/sector optional; participation is not employment'),
      ('PREMATURE-DEATH-LABOUR','','person-years and wages or output','national labour loss with survival retirement and replacement','','human-capital vs friction-cost methods; no current calculation','METHOD_AND_DATA_BLOCKED','endpoint-specific mortality; age-sex employment/wages; survival; retirement transition schedule; replacement/friction assumptions; wage loss not macro GDP'),
      ('CHINA-HEALTH-ABSENCE','','days / WPAI percent','older Chinese workers; health-status study not a total PA causal function','https://doi.org/10.1136/bmjopen-2018-024115','Methods/abstract; CHARLS cohort','SOURCE_SCREENED_NOT_ADMITTED','PA-specific absenteeism and presenteeism; younger workers; farm/nonfarm and sex differences')]:
        prod.append(dict(parameter_id=pid,estimate=val,unit=unit,population_scope=scope,source=source,source_location=loc,evidence_status=status,admission='NOT_ESTIMATED',price_year='2025' if pid.startswith('WAGE') else '2020 wage input only' if pid.startswith('IS-') else '',measure_interpretation='wage-based opportunity loss; NOT actual macroGDP' if pid.startswith('IS-') else 'earnings not GDP perworker' if pid.startswith('WAGE') else 'no CGE/GDP calculation',remaining_gap=gap))
    write(HERE/'registers/productivity_evidence_register.csv',prod)
    write(HERE/'results/economic_module_status.csv',[dict(module=m,status='NOT_ESTIMATED',value='',reason=reason) for m,reason in [('direct_medical','new first-year IS evidence extracted; selected survivors, source calendar prices and treated coverage need alignment'),('absenteeism_presenteeism','no admitted China causal PA dose-to-WPAI function; RAND mainland extrapolation not assumed'),('premature_mortality_labour','mortality source mapping plus employment-age-sex and retirement/replacement unresolved'),('GDP_equivalent','not calculated; wages do not equal output'),('macro_GDP','NOT_APPLICABLE; CGE excluded')]])
    return medical,prod

def calculate():
    pop=population();rates,source_rows=gbd();write(HERE/'inputs/gbd_2023_verified_rates.csv',source_rows)
    metadata=[]
    for relative in json.loads((HERE/'config.json').read_text('utf-8'))['gbd']:
        with zipfile.ZipFile(ROOT/relative) as z:
            citations={n:z.read(n).decode('utf-8-sig',errors='replace') for n in z.namelist() if 'citation' in n.lower() and not n.endswith('/')}
        selected=[r for r in source_rows if r['source']==relative]
        metadata.append(dict(original_zip=relative,sha256=sha(ROOT/relative),GBD_version='2023',rate_year=2023,location='China',population_group='All Population',sex=sorted({r['sex'] for r in selected}),age=AGES,measure=sorted({r['endpoint'] for r in selected}),cause=sorted({r['disease'] for r in selected}),metric='Rate per100000',required_columns=['val','lower','upper'],verified_selected_rate_rows=len(selected),citation=citations,query_evidence='verified file dimensions; prior query records preserved in Round4; no new authenticated download claimed'))
    jwrite(HERE/'inputs/gbd_source_metadata.json',metadata)
    write(HERE/'inputs/scenario_age_sex_2025_2050.csv',[dict(**r,p_P15=r['p_inactive']*(1-alpha(r['year'])),P15_fraction_of_inactive_shifted=alpha(r['year']),p_R1=0,R2_p_inactive='',R3_p_inactive=0,R2_status='BLOCKED_WITHIN_INACTIVE_DOSES',R3_dose_distribution_status='BLOCKED_ACTIVE_DOSE_SHAPE') for r in pop])
    details=[]
    for r in pop:
        for d in ['IHD','IS']:
            for endpoint in ['Incidence','Deaths','YLD','YLL','DALY','Prevalence']:
                v,lo,hi=rates[(d,endpoint,r['sex'],r['age'])];scale=r['population']/1e5
                details.append(dict(year=r['year'],disease=d,endpoint=endpoint,sex=r['sex'],age=r['age'],population=r['population'],baseline_total=v*scale,gbd_component_lower=lo*scale,gbd_component_upper=hi*scale,status='DISEASE_TOTAL_NOT_PA_ATTRIBUTED',projection='constant2023_age_sex_rate;WPPdynamic'))
    write(HERE/'results/baseline_total_burden_age_sex.csv',details)
    base=defaultdict(float)
    for r in details:base[(r['year'],r['disease'],r['endpoint'])]+=r['baseline_total']
    write(HERE/'results/baseline_total_burden.csv',[dict(year=y,disease=d,endpoint=e,baseline_total=v,unit='persons' if e in ['Incidence','Deaths','Prevalence'] else 'years',status='DISEASE_TOTAL_NOT_PA_ATTRIBUTED',aggregate_lower='',aggregate_upper='',uncertainty='marginal GBD age-sex UIs NOT summed to national95%UI') for (y,d,e),v in sorted(base.items())])
    # Independent disease/endpoint permissions are loaded from the register.
    all_bounds=[];annual={};attribution=[]
    for d in ['IHD','IS']:
        for endpoint in ['Incidence','Deaths']:
            for mode in ['SUPPORT_FREE_CONTINUOUS','CATEGORY_TARGET_SENSITIVITY']:
                gate=admission(d,endpoint,mode)
                for year in range(2025,2051):
                    cells=[]
                    for r in pop:
                        if r['year']!=year:continue
                        if endpoint=='Deaths' and not 30<=int(r['age'].split('-')[0].removesuffix('+'))<70:continue
                        total=rates[(d,endpoint,r['sex'],r['age'])][0]*r['population']/1e5
                        lo,hi=bounds(d,r['p_inactive'],mode);cells.append((r,total,lo,hi))
                    n=sum(r['population'] for r,_,_,_ in cells);total=sum(v for _,v,_,_ in cells);rl=sum(v*l for _,v,l,h in cells);rh=sum(v*h for _,v,l,h in cells)
                    for scenario,factor in [('R1',1.),('P15',alpha(year))]:
                        name=scenario if mode=='SUPPORT_FREE_CONTINUOUS' else scenario+'_category_proxy'
                        lo,hi=rl*factor,rh*factor
                        annual[(d,endpoint,mode,year,scenario)]=(lo,hi,total)
                        row=dict(year=year,disease=d,endpoint=endpoint,population_scope=gate['population_scope'],analysis_mode=mode,scenario=name,baseline_total=total,population=n,benefit_point='',benefit_lower_bound=lo,benefit_upper_bound=hi,benefit_rate_lower_per100000=lo/n*1e5,benefit_rate_upper_per100000=hi/n*1e5,benefit_pct_lower=lo/total*100,benefit_pct_upper=hi/total*100,increment_vs_P15_lower=(1-alpha(year))*rl if scenario=='R1' else 0.,increment_vs_P15_upper=(1-alpha(year))*rh if scenario=='R1' else 0.,remaining_disease_burden_lower=total-hi,remaining_disease_burden_upper=total-lo,remaining_R1_attributable_lower=(1-factor)*rl,remaining_R1_attributable_upper=(1-factor)*rh,status='IDENTIFICATION_ENVELOPE_STRUCTURAL_SENSITIVITY_NOT_POINT_OR_95UI',implementation='full counterfactual each year' if scenario=='R1' else 'linear mover fraction2025-2030; held thereafter',mapping='exact600; others unchanged' if mode=='SUPPORT_FREE_CONTINUOUS' else 'pooledLOWcategory average; NOT exact600',causal_mapping=gate['endpoint_match'])
                        all_bounds.append(row)
                        if year==2025 and scenario=='R1':attribution.append(dict(**row,attribution_label='minimum_recommendation_CF_600' if mode=='SUPPORT_FREE_CONTINUOUS' else 'LOW_CATEGORY_PROXY_NOT_MINIMUM_600_CF'))
                        for r,v,l,h in cells:
                            all_bounds_row=dict(year=year,disease=d,endpoint=endpoint,analysis_mode=mode,scenario=name,sex=r['sex'],age=r['age'],population_scope=gate['population_scope'],baseline_activity_source='original_inactive',benefit_point='',benefit_lower_bound=v*l*factor,benefit_upper_bound=v*h*factor,benefit_active_lower_bound=0.,benefit_active_upper_bound=0.,status='IDENTIFICATION_ENVELOPE; active zero follows R1/P15 definition, not missing imputation')
                            # These cells are correlated identification limits, not independent CI samples.
                            all_bounds_row['shared_parameter_id']=r['shared_parameter_id']
                            if 'decomp' not in locals():decomp=[]
                            decomp.append(all_bounds_row)
    # R2/R3 health benefits are explicitly unidentifiable, not zero.
    template=dict.fromkeys(all_bounds[0],'')
    for year in [2030,2034,2050]:
        for d in ['IHD','IS']:
            for scenario in ['R2','R3']:
                row=dict(template);row.update(year=year,disease=d,endpoint='Incidence',scenario=scenario,analysis_mode='FULL_DOSE_REQUIRED',status='BLOCKED_EXPOSURE_DISTRIBUTION',mapping='1.2*x including zero unchanged' if scenario=='R2' else '600 if original x<600 else1.2*x');all_bounds.append(row)
    write(HERE/'results/scenario_health_benefits.csv',all_bounds)
    write(HERE/'results/attributable_burden_2025.csv',attribution)
    write(HERE/'results/benefit_decomposition.csv',decomp)
    cumulative=[]
    for d in ['IHD','IS']:
        for mode in ['SUPPORT_FREE_CONTINUOUS','CATEGORY_TARGET_SENSITIVITY']:
            for scen in ['R1','P15']:
                for start,end in [(2025,2029),(2025,2030),(2025,2034),(2025,2050)]:
                    vals=[annual[(d,'Incidence',mode,y,scen)] for y in range(start,end+1)]
                    cumulative.append(dict(disease=d,endpoint='Incidence',analysis_mode=mode,scenario=scen,start=start,end=end,n_calendar_years=end-start+1,benefit_point='',benefit_lower_bound=sum(x[0] for x in vals),benefit_upper_bound=sum(x[1] for x in vals),status='CONDITIONAL_REPEATED_ANNUAL_COUNTERFACTUAL_NOT_COHORT',assumptions='constant2023rates;instantaneous_response;no_lag;R1fullfrom2025;P15ramp;no_natural_history'))
    write(HERE/'results/cumulative_incidence_conditional.csv',cumulative)
    return dict(baseline_cells=len(details),baseline_totals=len(base),scenario_rows=len(all_bounds),attributable_rows=len(attribution),decomposition_rows=len(decomp),population_2025=sum(r['population'] for r in pop if r['year']==2025),p2025=sum(r['population']*r['p_inactive'] for r in pop if r['year']==2025)/sum(r['population'] for r in pop if r['year']==2025))

def requests():
    rows=[
      ('EXPOSURE-A','China survey aggregate','2018CCDRFS weighted histogram, Male/Female x coarse source ages18-29,...70+, bins {0},(0,100),[100,200),[200,300),[300,400),[400,500),[500,600),[600,1000),[1000,2000),[2000,4000),[4000,8000),[8000,16000),[16000,25500),[25500,30600],>30600; bin weight, weighted mean or finer within-bin atoms; population denominator; design; domain and4/8MET scoring','unlock exact600 point and R2/R3; R2/R3 tail affected baseline>25500; source age70+ remains shared; do not fabricate fine-age independent estimates','request authorised deidentified weighted aggregates from CCDRFS authors/data custodian; no microdata upload'),
      ('EXPOSURE-B','China local shape proposal','CHNS>=35 nine provinces2011 or CKB30-79 tenregions2004-2008; weighted within-inactive and active dose bins excluding light activity as required; sex-age joint distribution','evaluate external transport only; not national main; missing20-29/30-34 and80+ must remain unsupported','submit shape+margin reweighting, domain harmonisation, calibration overlap and leave-region-out uncertainty to Work before analysis'),
      ('GBD-RISK','https://vizhub.healthdata.org/gbd-results/','GBD2023; China; Context/Risk (menu name NOT_CHECKED); Risk=Low physical activity; Causes=IHD,Ischemic stroke,T2D,Breast,Colon only IF actually selectable; Male,Female; age20-24,...90-94,95+ IF supported;2023;Deaths,YLDs,YLLs,DALYs;Number,Rate;val/lower/upper;rei_id,cause_id,age_id,sex_id,metric_id,measure_id','external benchmark only; inspect actual age support, mediation and2023TMREL; NEVER scale attributed counts15%','user logged-in menu verification required; save query text/screenshot,citation,ZIP; no login bypass; if20-24 unavailable do not fill0'),
      ('GBD-DISEASE','https://vizhub.healthdata.org/gbd-results/','GBD2023 China Male/Female2023 Rate+Number ages20-24,...90-94,95+;Incidence,Deaths,Prevalence,YLD,YLL,DALY;T2D;Breast(female);Colon only if supported','current originals for most other diseases stop2017; combinedCRC cannot stand for colon','save separate cause export; confirmed prior disease exports support IHD/IS and95+; finer colon cause support NOT_CHECKED'),
      ('GBD-METHOD','GBD2023 official appendix','low physical activity exposure calibration, RR source, mediation and TMREL exact2023 version; IHD MI first/recurrent relationship; IS first-ever definition','resolve endpoint transport and external benchmark','official2021PA PDF403/challenge;2019TMREL3000-4500 differs from2021 indexed3600-4400 objective; neither silently assigned2023'),
      ('KYU-T2D','https://doi.org/10.1007/s00125-006-0518-7','Carlsson2007 Table of physical inactivity: distinguish LADA vs T2D; match RR2.03(1.52,2.71),1.61(1.24,2.10),1.24(.94,1.62),1.21(.92,1.59) to Kyu Appendix4p22','source includes738T2D cases and81LADA; title alone NOT rejection evidence','public abstract checked; subscription fulltext unavailable; request author-accepted public manuscript or exact table via researcher; no institutional bypass'),
      ('COST-IS','CNSRIII authors','520survivors price-year accounting, interview timing, monetary calendar harmonisation, cost of deceased and untreated first events, age-sex cost/coverage including>80','matched firstyear source ready for followup; national2025 cost result blocked','request supplementarycostingprotocol and coverage; retain26612.67CNY source amount, no guessedpriceyear'),
      ('COST-ACS','https://pubmed.ncbi.nlm.nih.gov/30770126/','original ACS claims article: first vs recurrent, allcause vs disease cost, priceyear, admissions vs all incidentIHD','OMT subgroup20771CNY not nationalincidentIHD','publisher abstract public; localPubMed response waschallenge, not fulltextverified'),
      ('PRODUCTIVITY-CHINA','NBS and Chinese labour cohort sources','2025 or nearest employment/population and participation separately by Male/Female fiveyear20+; wages by employment sector, unemployment; PA-specific days missed/WPAI; retirement transition and replacement mechanism','urban wage129441/71590 alone not national age-sex productivity function','NBS Population/Employment Yearbook tables require actual extraction; no universal retirement cutoff or internationalWPAI coefficient'),
    ]
    write(HERE/'registers/remaining_data_requests.csv',[dict(request_id=i,source_or_tool=s,exact_data=q,purpose_or_block=b,next_action=n) for i,s,q,b,n in rows])

def checks():
    result=[]
    def check(i,func,category='FILE_AND_COMPUTATION'):
        try:info=func();result.append(dict(id=i,status='PASS',category=category,evidence=info if isinstance(info,(str,int,float)) else 'executed assertion'))
        except Exception as e:result.append(dict(id=i,status='FAIL',category=category,evidence=repr(e)))
    def yes(b,message=''):
        if not b:raise AssertionError(message)
    pop=population();p25=[r for r in pop if r['year']==2025]
    check('POP2025',lambda:yes(sum(r['population'] for r in p25)==1113252964))
    check('EXPOSURE2025',lambda:yes(abs(sum(r['population']*r['p_inactive'] for r in p25)/1113252964-.219660515)<1e-9))
    check('GRID_NO_BOTH_OR_DUPLICATES',lambda:yes(len({(r['year'],r['sex'],r['age']) for r in pop})==832 and {r['sex'] for r in pop}=={'Male','Female'}))
    check('FIXED2025_WEIGHT_TARGET',lambda:yes(abs(sum(r['population']*r['p_inactive']*.85 for r in p25)/1113252964-.186711438)<1e-9))
    def prevalence_checks():
        for r in pop:yes(0<=r['lower_95']<=r['p_inactive']<=r['upper_95']<=1)
        for r in read(HERE/'inputs/scenario_age_sex_2025_2050.csv'):
            p=float(r['p_inactive']);after=float(r['p_P15']);year=int(r['year'])
            yes(0<=after<=p<=1);yes(math.isclose(after,p*(1-alpha(year)),abs_tol=1e-14))
            if year>=2030:yes(math.isclose(after,.85*p,abs_tol=1e-14))
        fine=read(ROOT/'new_study/round2_target_prep_20261112/registers/exposure_crosswalk_ci_v2.csv')
        for sex in ['Male','Female']:
            young=[r for r in fine if r['sex']==sex and r['age_group'] in ['20-24','25-29']]
            yes(len(young)==2 and len({r['p_inactive'] for r in young})==1 and len({r['shared_parameter_id'] for r in young})==1)
    check('PROBABILITIES_PATH_SHARED_OBSERVATIONS',prevalence_checks)
    def nodecheck():
        for d in ['IHD','IS','breast_cancer','colon_cancer','T2D']:
            g=sorted((r for r in read(HERE/'inputs/kyu_published_grid.csv') if r['disease']==d),key=lambda r:float(r['dose']))
            x=np.array([float(r['dose']) for r in g]);v=np.array([float(r['estimate']) for r in g])
            yes(np.allclose(rr(d,x),v,rtol=1e-12));yes(np.all(rr(d,np.arange(0,30601,50))>0));yes(np.all(np.diff(v)<=1e-12))
    check('PUBLISHED_NODES_POSITIVE_MONOTONE',nodecheck)
    sensitivity=[]
    for d in ['IHD','IS','breast_cancer','colon_cancer','T2D']:
        x=np.arange(0,30601,10);a=rr(d,x,'log_linear');b=rr(d,x,'linear')
        sensitivity.append(dict(disease=d,evaluated_doses=len(x),max_absolute_RR_difference=float(np.max(np.abs(a-b))),max_relative_difference=float(np.max(np.abs(a-b)/a)),effect_on_exact600_bounds=0.,interpretation='numerical interpolation sensitivity only;600 is an original node; no exposure-weighted result sensitivity claimed'))
    write(HERE/'results/interpolation_method_sensitivity.csv',sensitivity)
    check('INTERPOLATION_COMPARISON_EXECUTED',lambda:yes(all(r['max_relative_difference']<.01 for r in sensitivity)))
    def mustblock(fn):
        try:fn()
        except Blocked:return
        raise AssertionError('invalid input allowed')
    check('SUPPORT_NO_EXTRAPOLATION',lambda:mustblock(lambda:rr('IHD',[30601])))
    check('VALID_GATE_ACTUALLY_PASSES',lambda:admission('IHD','Incidence','SUPPORT_FREE_CONTINUOUS'),'SCIENTIFIC_PERMISSION_TEST')
    check('INVALID_ENDPOINT_REJECTED',lambda:mustblock(lambda:admission('IHD','DALY','SUPPORT_FREE_CONTINUOUS')),'SCIENTIFIC_PERMISSION_TEST')
    check('ICH_SAH_REJECT_IS_CURVE',lambda:[mustblock(lambda d=d:admission(d,'Incidence','SUPPORT_FREE_CONTINUOUS')) for d in ['ICH','SAH']],'SCIENTIFIC_PERMISSION_TEST')
    def numerical():
        # Explicit toy atoms only for algebraic unit checks, NEVER national exposure inputs.
        x=np.array([0.,100.,550.,600.,1000.,8000.]);w=np.ones(6)/6
        for d in ['IHD','IS']:
            yes(abs(pif_atoms(d,x,w,'B0'))<1e-14)
            a=pif_atoms(d,x,w,'R1');b=pif_atoms(d,x,w,'P15');yes(a>=0 and math.isclose(b,.15*a,abs_tol=1e-14))
            yes(pif_atoms(d,x,w,'R3')>=a-1e-14)
        yes(transformed([550],'R2')[0]==660 and transformed([550],'R3')[0]==600)
        yes(float(rr('IHD',[660])[0])<float(rr('IHD',[600])[0]));yes(not math.isclose(float(rr('IHD',[600])[0]),float(rr('IS',[600])[0]),rel_tol=1e-6))
    check('P15_IDENTITY_R3_GE_R1_AND_R2_COUNTEREXAMPLE',numerical)
    def reconcile():
        sums=defaultdict(lambda:[0.,0.])
        for r in read(HERE/'results/benefit_decomposition.csv'):
            k=tuple(r[f] for f in ['year','disease','endpoint','analysis_mode','scenario']);sums[k][0]+=float(r['benefit_lower_bound']);sums[k][1]+=float(r['benefit_upper_bound'])
        for r in read(HERE/'results/scenario_health_benefits.csv'):
            if not r['benefit_lower_bound']:continue
            k=tuple(r[f] for f in ['year','disease','endpoint','analysis_mode','scenario']);lo,hi=sums[k]
            yes(math.isclose(lo,float(r['benefit_lower_bound']),abs_tol=1e-6));yes(math.isclose(hi,float(r['benefit_upper_bound']),abs_tol=1e-6));yes(0<=lo<=hi<=float(r['baseline_total'])+1e-8)
    check('DETAIL_TOTAL_RECONCILIATION_AND_BOUNDS',reconcile)
    def missing():
        for r in read(HERE/'results/scenario_health_benefits.csv'):
            if r['status'].startswith('BLOCKED'):yes(r['benefit_point']==r['benefit_lower_bound']==r['benefit_upper_bound']=='')
        for r in read(HERE/'results/economic_module_status.csv'):yes(r['value']=='')
    check('MISSING_NOT_ZERO',missing)
    def ids():
        for f,key in [('disease_endpoint_evidence_matrix.csv','evidence_id'),('rr_function_register.csv','rr_id'),('medical_cost_evidence_register.csv','cost_id'),('productivity_evidence_register.csv','parameter_id'),('remaining_data_requests.csv','request_id'),('exposure_candidate_inventory.csv','candidate_id')]:
            rows=read(HERE/'registers'/f);yes(len(rows)==len({r[key] for r in rows}),f)
    check('UNIQUE_REGISTER_IDS',ids)
    def legacy():
        p=subprocess.run(['git','diff',BASE,'--name-only'],cwd=ROOT,capture_output=True,text=True,check=True)
        yes(all(n.startswith('new_study/round7_burden_evidence/') for n in p.stdout.splitlines()),p.stdout)
        for p,h in json.loads((HERE/'inputs/source_locks.json').read_text('utf-8')).items():yes(sha(ROOT/p)==h,p)
    check('HISTORICAL_FILES_AND_HASHES_UNCHANGED',legacy)
    result.extend([dict(id='NATIONAL_FINE_EXPOSURE',status='FAIL',category='SCIENTIFIC_EVIDENCE_GATE',evidence='No applicable weighted dose distribution recovered; national point estimates not identified'),dict(id='MORTALITY_CURVE_DIRECT',status='FAIL',category='SCIENTIFIC_EVIDENCE_GATE',evidence='No mortality-only fitted Kyu grid; public CRA precedent supports labelled structural sensitivity only'),dict(id='GBD_RISK_FILTER_MENU',status='NOT_CHECKED',category='SCIENTIFIC_EVIDENCE_GATE',evidence='No authenticated risk-menu interaction performed this round; supported filters not invented'),dict(id='MEDICAL_NATIONAL2025',status='FAIL',category='SCIENTIFIC_EVIDENCE_GATE',evidence='Source amount verified, national treated/survivor coverage and uniform priceyear unresolved'),dict(id='NATURAL_HISTORY_CEA_PSA',status='NOT_APPLICABLE',category='SCOPE',evidence='No such functions/modules imported or executed')])
    jwrite(HERE/'results/validation_report.json',dict(base_commit=BASE,branch=BRANCH,checks=result,computational_failures=sum(r['status']=='FAIL' and r['category']=='FILE_AND_COMPUTATION' for r in result),scientific_gate_failures=sum(r['status']=='FAIL' and r['category']=='SCIENTIFIC_EVIDENCE_GATE' for r in result),scientific_point_release='BLOCKED_EXPOSURE_AND_ENDPOINT_SPECIFIC_RELEASE',test_pass_is_not_scientific_admission=True))
    if any(r['status']=='FAIL' and r['category'] in ['FILE_AND_COMPUTATION','SCIENTIFIC_PERMISSION_TEST'] for r in result):raise Blocked('executed checks failed')
    return result

def figures():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none','pdf.fonttype':42})
    data=read(HERE/'results/scenario_health_benefits.csv')
    # Figure contract: show precisely the consequence of unidentified dose distribution.
    # Interval graphic, not a bar of a selected bound. No invented point markers or95%UI.
    selected=[r for r in data if r['year']=='2030' and r['endpoint']=='Incidence' and r['analysis_mode']=='SUPPORT_FREE_CONTINUOUS' and r['scenario'] in ['R1','P15']]
    fig,ax=plt.subplots(figsize=(6.5,3.1));colors={'IHD':'#0072B2','IS':'#D55E00'}
    for i,r in enumerate(selected):
        lo,hi=[float(r[k])/1000 for k in ['benefit_lower_bound','benefit_upper_bound']];ax.plot([lo,hi],[i,i],lw=3,color=colors[r['disease']]);ax.plot([lo,hi],[i,i],linestyle='',marker='|',ms=10,color=colors[r['disease']])
    ax.set_yticks(range(len(selected)),[r['disease']+' '+r['scenario'] for r in selected]);ax.invert_yaxis();ax.set_xlabel('Potential annual events: identification envelope (thousands)');ax.set_title('2030: binary exposure alone does not identify a point estimate',loc='left',fontsize=11);ax.text(0,-.32,'Structural cause-event transport; published central RR fixed.\nIntervals are conservative bounds, NOT 95% uncertainty intervals.',transform=ax.transAxes,fontsize=8);fig.subplots_adjust(bottom=.28,left=.17)
    for ext in ['svg','pdf','png']:fig.savefig(HERE/f'figures/2030_identification_envelopes.{ext}',dpi=200)
    plt.close(fig)
    fig,ax=plt.subplots(figsize=(6.5,3.0))
    for d in ['IHD','IS']:
        g=sorted((r for r in read(HERE/'inputs/kyu_published_grid.csv') if r['disease']==d),key=lambda r:float(r['dose']))
        x=np.array([float(r['dose']) for r in g]);ax.plot(x,np.array([float(r['estimate']) for r in g]),label=d,color=colors[d]);ax.plot(x[::4],rr(d,x[::4]),'o',ms=2,color=colors[d])
    ax.set_xlabel('Published total gross MET-min/week (no tail extrapolation)');ax.set_ylabel('RR relative to zero activity');ax.legend(frameon=False);ax.set_title('Published Kyu grid; interval interpolation is numerical only',loc='left',fontsize=11);fig.tight_layout()
    for ext in ['svg','pdf','png']:fig.savefig(HERE/f'figures/kyu_published_grid.{ext}',dpi=200)
    plt.close(fig)
    textfile('reports/FIGURE_CONTRACT_AND_QA.md','''# Figure contract and executed QA
Python/matplotlib only. Figure1 communicates incomplete identification using real GBD/WPP and fixed published RR; interval lines with end caps, no selected-bound point estimate. The zero end is a mathematical infimum, not imputation. Figure2 reproduces published nodes and supported-range interpolation, not the original Bayesian fit. Colourblind-safe blue/orange, vector SVG/PDF and200dpi PNG; no individual records. Preview both PNGs before delivery. Neither chart is a national point benefit estimate or a95%UI. Numerical node reproduction, positivity, monotonicity and group reconciliation are executed in validation_report.json. Visual QA is recorded separately after actual inspection.''')

def notebooks():
    import nbformat
    sections=[('01_evidence_review','Evidence review and concrete recoveries',"import pandas as pd\nfor f in ['exposure_candidate_inventory','rr_function_register','disease_endpoint_evidence_matrix']:\n    df=pd.read_csv(HERE/'registers'/f'{f}.csv'); print(f,len(df)); display(df.head(8))\ndisplay(pd.read_csv(HERE/'inputs/china_ckb_published_quintiles.csv'))"),('02_baseline_attributable_burden','Disease total and minimum600 counterfactual envelopes',"import pandas as pd\ndisplay(pd.read_csv(HERE/'results/baseline_total_burden.csv').query('year==2025'))\ndisplay(pd.read_csv(HERE/'results/attributable_burden_2025.csv'))"),('03_multiscenario_benefits','P15 R1 identifiable ranges; R2 R3 exposure gaps',"import pandas as pd\ndf=pd.read_csv(HERE/'results/scenario_health_benefits.csv');display(df[df.year.isin([2030,2034,2050])])\ndisplay(pd.read_csv(HERE/'results/cumulative_incidence_conditional.csv'))"),('04_economic_evidence','Chinese first-event costs and wage evidence, no unsupported multiplication',"import pandas as pd\nfor f in ['medical_cost_evidence_register','productivity_evidence_register']:\n    display(pd.read_csv(HERE/'registers'/f'{f}.csv'))\ndisplay(pd.read_csv(HERE/'results/economic_module_status.csv'))"),('05_validation_and_figures','Executed gates, reconciliation and real nonempty interval figures',"from src.pipeline import checks,figures\nimport pandas as pd\ndisplay(pd.DataFrame(checks())); figures()\nfrom IPython.display import display,Image\ndisplay(Image(filename=str(HERE/'figures/2030_identification_envelopes.png')))\ndisplay(Image(filename=str(HERE/'figures/kyu_published_grid.png')))" )]
    for stem,title,code in sections:
        nb=nbformat.v4.new_notebook(cells=[nbformat.v4.new_markdown_cell('# '+title+'\n\nIdentification envelopes are not point estimates or95%UIs. Main point results remain blocked where evidence is insufficient.'),nbformat.v4.new_code_cell("from pathlib import Path\nimport sys\nHERE=Path.cwd()\nif HERE.name=='notebooks': HERE=HERE.parent\nif HERE.name!='round7_burden_evidence': raise RuntimeError('Run from Round7 or its notebooks directory')\nsys.path.insert(0,str(HERE))\nfrom src.model import population,gbd\nprint('Population cells:',len(population()),'Verified GBD rates:',len(gbd()[0]))"),nbformat.v4.new_code_cell(code)],metadata={'kernelspec':{'display_name':'Python3','language':'python','name':'python3'}})
        (HERE/'notebooks'/f'{stem}.ipynb').write_text(nbformat.writes(nb)+'\n',encoding='utf-8',newline='\n')

def execute_notebooks():
    import nbformat
    from nbclient import NotebookClient
    logs=[]
    for p in sorted((HERE/'notebooks').glob('*.ipynb')):
        start=time.time();nb=nbformat.read(p,as_version=4)
        NotebookClient(nb,timeout=180,kernel_name='python3',resources={'metadata':{'path':str(HERE)}}).execute()
        p.write_text(nbformat.writes(nb)+'\n',encoding='utf-8',newline='\n')
        logs.append(dict(file=p.name,status='EXECUTED',seconds=round(time.time()-start,2),executed_cells=sum(c.cell_type=='code' and c.execution_count is not None for c in nb.cells)))
        print('EXECUTED',p.name,flush=True)
    jwrite(HERE/'logs/notebook_execution.json',logs)

def reports(summary):
    textfile('reports/ROUND6_AUDIT_RESPONSE.md',f'''# Round6 audit response
Base `{BASE}`; isolated branch `{BRANCH}`. No historical directory edited.

Round6's inference “protocol admits mortality therefore the entire fitted risk curve is unusable” is withdrawn. Actual published grids and study tables are reviewed: pooled event evidence remains usable for explicitly labelled CRA structural sensitivity; an incidence-only or mortality-only fitted curve was not recovered. A primary Brazilian CRA applies Kyu to cause-specific premature mortality ({BRAZIL}, Methods Relative risk estimates and Number of NCD premature deaths). It establishes published precedent, not validation of all endpoints or China transport. Its erroneous stroke ICD grouping is not copied: our data remain IS only. We restrict the mortality illustration to its30–69 scope. YLD/YLL/DALY/prevalence remain unapproved, independently of incidence.

Deleted universal R3>=R2 requirement:550 maps to660 underR2 and600 underR3. Under monotone supported risk, R3>=R1 is checked. P15=.15R1 at completed target is an algebraic identity, not an empirical discovery. Prior all-active=low-category binary calculation is not promoted to main.

Interpolation is now allowed: piecewise linear logRR within0–30600; exact nodes reproduced. No original Bayesian model reconstruction, tail extrapolation or independent knot-CI sampling. Permissions are loaded from disease_endpoint_evidence_matrix.csv; both successful valid use and rejection of invalid endpoints execute.

New results: nonempty disease totals; conservative exact600 identification envelopes and separate low-category structural sensitivity ranges; no national point claim. Test passes are separate from failed scientific evidence gates. Root runners and R1–6 unchanged.''')
    textfile('reports/EXPOSURE_RECOVERY_AND_APPLICABILITY.md',f'''# Exposure recovery and applicability
## Actual inventory
`recover_evidence.py` searched the official repository, registered E:/工作目录/China-PA-13/Data handoff packages, prior C research repository, and Downloads.27 local candidate files were recorded initially, plus2 public aggregate articles. Zip member names, workbook metadata and CSV headers were examined before authorised aggregate sources were read. No individual records were accessed. Workbook sheets/source-code use confirm the old analysis consumed22 binary inactivity/active records; n/psa_precision_n does not recover observed national dose distribution or survey sample size.13 ZIP-member exports inspected (including duplicates), zero risk-dimension exports. SHA duplicates are retained as aliases, not independent studies. No original ZIP was overwritten. The exact latest20261113 research-pre-report DOCX was not found in checked locations; this user prompt governs.

## New recoveries
CKB2025 article Table1 supplies five sample quintile boundaries/counts and means, actually extracted to china_ckb_published_quintiles.csv. Sample511088, baseline2004–2008, age30–79 in10areas; counts are NOT nationally weighted. Total includes light activity; inactivity was defined via31st percentile in its analysis, not600. Thus neither quintile means nor sample fractions are substituted into national GPAQ exposure. {CKB}
CHNS China CRA article documents four categories and9-province sampling age>=35 and methods, but main text does not recover the required joint category proportions. It covers occupational/domestic detail and is not a national2018 distribution. Public main HTML was archived; supplementary NIHMS800634-supplement-supplement_1.pdf direct PMC fetch failed and cloud path404; not recovered. {CHNS}

## Tier decisions
A: no applicable national weighted fine distribution recovered; exact dose point estimates remain unidentified.
B: possible local-shape-plus-national-margin study must first resolve domain/light-intensity differences, missing younger/older support, survey weighting and calendar shifts. Proposed q_b(x|sex,age) reweight separately below/above600 to national p; test shape transports across regions, urbanisation and age with alternative sources. Preserve observed zeros and tails. No weights or bin values are created now, and no B-series national health result is released.
C: national binary margins identify a set of possible600-counterfactual effects. Exact600 outer envelopes are computed without a tail rule. Low-category ranges are separately labelled structural sensitivity, not exact600. R2 needs within-inactive atoms near500–600, active dose distribution and zeros; R3 still needs active shape. Four category totals alone do not identify either20% scaling scenario.

Specific aggregate bins, survey design/weights and tail needs are in remaining_data_requests.csv. A raw microdata authorisation request is unnecessary if custodians can supply authorised weighted aggregates.''')
    textfile('reports/RR_AND_CRA_ADMISSION_REVIEW.md',f'''# RR and CRA admission review
Kyu original main text, protocol and Appendix4 were re-read. Five continuous TableF grids260rows were extracted, extending the former2-disease inventory to breast/colon/diabetes. This is source verification, not five-disease model admission. Input support0–30600 total gross MET-min/week; disease-specific risks relative to zero. Main Table1 category averages are a different parameterisation. Author mapping of domain-specific measures via SAGE/NHANES adds transport error; it does not authorise us to convert leisure or marginal MET to total gross MET. {KYU_URL}

Actual Appendix4 TablesD/E pp43–66 contain events and mortality-related cohorts, not only a permissive protocol: Whitehall/Batty row, prospective MillionWomen event reports and Reykjavik/Agnarsson ischemic-stroke row are inspected. Tables report RR,HR andOR selected by original authors; no separate outcome-specific fitted curve or consistent first/recurrent definition is supplied. Therefore incidence use is an explicit cause-event CRA transport sensitivity rather than a directly measured GBD first-event risk. A public CRA mortality precedent using Kyu was verified and archived at {BRAZIL}; restrict illustration to30–69 and do not relabel the curve as directly measured mortalityRR. No automatic mapping to DALY,YLL,YLD or prevalence. Do not copy that article's total-stroke/CRC definitions.

Diabetes: Carlsson2007 Appendix4p22 is actually included, with PA rows; referencep68 mentions LADA. The original public abstract ({'https://pubmed.ncbi.nlm.nih.gov/17096113/'}) also includes738T2D cases and81LADA. Thus title alone cannot exclude the study or establish contamination. Exact selected-row subtype needs the original table; maintain CONDITIONAL rather than claim recovered. Breast female only; colon requires colon burden, not combinedCRC. Alternative CKB prospective disease and death definitions were examined: first event per disease, domain/light-intensity and percentile threshold differ; not admitted as a600 curve.

Review tiers: (1) published disease-event risk functions: Kyu five, only IHD/IS have verified current burden for labelled event sensitivity; (2) direct mortality-only fitted function matching this interface: none admitted; (3) public CRA mortality precedent: Brazilian30–69 Kyu application; (4) current structural sensitivities: cause-event transport, mortality30–69, low-category proxy; (5) unmatched: other endpoints, subtype conflicts, alternate domains and exposure distribution. No re-meta-analysis is required by default. All13 candidate disease families plus ICH/SAH are in the endpoint matrix.

Official2021lowPA methods indexed text describes objective calibration and3600–4400TMREL; direct PDF returned challenge/403. The downloaded2019GBD reference reports3000–4500. These versions must not be mixed or labelled verified2023. There is no local risk-attributed export. GBD benchmark is external, its nativeTMREL retained, never multiplied15% forP15.''')
    textfile('reports/METHODS_BURDEN_AND_BENEFITS.md',r'''# Methods: burden and benefits
Population is China20+, Male/Female, WPP2024Medium July1,2025–2050,95–99 and100+ population combined to95+ matching observedGBD menus. Rates are raw-verifiedGBD2023 detailed age-sex rates, held fixed. Projection is a demographic counterfactual, not a cohort. Baseline exposures are2018CCDRFS observations mapped to2025; no2025 observed claim. Shared coarse-source parameters and original CIs are preserved.

B0 preserves the unknown dose distribution within each age-sex layer. R1 maps max(x,600);R2 maps1.2x including0->0;R3 maps original x<600 to600, otherwise1.2x. P15 proportionally splits alpha(year) of each originally inactive dose atom to600, alpha=0,.03,.06,.09,.12,.15 for2025–2030 and.15thereafter. It is WHO-target-magnitude-aligned, not direct WHO18+ standardised monitoring attainment. Common-year comparisons use identical population/rates. FullR1 counterfactual is evaluated each calendar year; its implementation path is not silently equated toP15. Cumulative windows are2025–2029(5),2025–2034(10),2025–2050(26), with2025–2030 additionally labelled6years. All assume immediate risk response/no lag and constant2023rates; no observed cohort interpretation.

## Exact600 partial identification
Let p=P(x<600), A=E[r(x)|x<600],B=E[r(x)|x>=600],c=r(600),r(0)=1. For a monotone published central curve on[0,600], c<=A<=1 and B>0. R1 PIF=p(A-c)/(pA+(1-p)B). Without unknown tail weights or a floor on B, a conservative outer identification envelope is[0,1-c] for p>0 (p=0 yields exactly0). The zero is an infimum as inactive doses approach600; NOT missing-value imputation. The upper is a weak extremal bound, NOT a credible estimate. It intentionally becomes weak with unknown denominator, even at lowp. No risk outside the published support is evaluated. There is no claim that this broad set is a useful policy point estimate. All empirical inputs and the central RR are fixed; these are NOT95%UI or confidence limits.

P15 PIF=alpha*R1 PIF identically with proportional within-inactive shifting; paired R1-P15 difference=(1-alpha)*R1 PIF. Bounds and remaining attributable burden use this coupling, not subtraction of independent marginal extremes. At2030+alpha=.15 regardless of demographic weights. Annual national crude inactivity may change with population structure; it is not fixed to18.6711438% each future year.

## Distinct low-category sensitivity
Kyu category parameters compare<600 with600–3999,4000–7999,>=8000 category averages. With inactive RR1 and unknown active category fractions, the low-category-shift envelope is p(1-rLow)/(p+(1-p)*max(activeRR)) through p(1-rLow)/(p+(1-p)*min(activeRR)). This has nonzero lower bound but is NOT exact600 and is named*_category_proxy. Do not pool these rows with main minimum600 counterfactual. No active-bin proportions or within-bin means are invented.

## Endpoint permissions
Numerical envelopes times age-sex total burden are displayed only for cause-event structural sensitivity and public-precedent30–69 mortality sensitivity. No national point benefit is claimed; no direct RR for death,YLD,YLL,DALY or prevalence is inferred from a cause name. YLD/YLL/DALY/prevalence mappings remain unapproved independently. Health results for these endpoints are not filled0. Disease totals are separate outputs. Main-year2030, extension2034/2050, per100000 and percentages, pairedP15differences, remaining total and attributable burden, age-sex detail are provided where bounded use is admitted. R2/R3 point results remain empty with specific dose requirements; no universalR3>=R2 sorting. R3 original-inactive/active decomposition awaits its distribution; do not fabricate a decomposition chart.

## Interpolation and uncertainty
Published TableF logRR is piecewise linear inside0–30600, numerical approximation only. Alternate linearRR is compared numerically, positivity and monotonicity are checked. Unsupported tails fail closed. Baseline exposures above25500 would exceed30600 after20%shift; their weight is UNKNOWN, not zero. GBD rawpoint/lower/upper are retained at cell level; marginalUIs are not added to produce national95%UI. Knot intervals are not independently sampled; noPSA is run. No patient-years or natural-history transitions are generated.''')
    textfile('reports/ECONOMIC_EVIDENCE_REVIEW.md',f'''# Chinese economic evidence: actual extraction and use limits
New first-everIS source {STROKE}, Table3: firstyear direct medical26612.67CNY (24512.87–28712.46); indexhospital18143.79 and followup8468.88 are components, not additional costs.520selected survivors18–80,20sites, index2017–2018; no uniform2025price basis established. Registry geography does not make this selected survivor sample representative of all incidentGBDcases. This source is a concrete firstyear medical candidate; no all-case multiplier is released. Patient wage-loss amounts are separate from informal care and total indirect cost.

ChinaACS one-year claims source PMID30770126 public abstract was screened: OMT subgroup20771CNY is all-cause treatedACS, not average newIHD; localPubMed download was a challenge page, so no fulltext/hash claim. FXyear2014 does not automatically assign a priceyear. Original fulltext and disease-related scope are needed.

Official2025NBS urban nonprivate/private employee wages129441/71590CNY were verified from {NBS}, Tables1/4. They are earnings for different employment universes, not all-worker age-sex wages or output per worker. Never multiply the entire adult population by either wage. RAND's actual proprietary productivity samples exclude mainlandChina; its WPAI associations0.8–1.2percentage points are method-comparison evidence only, not Chinese main parameters. China older-worker health/absence evidence is identified but does not supply a causal totalPA function.

13families have matched firstyear-cost evidence or specific missing-source records; annual prevalent costs, inpatient-only costs, social dementia costs and cancer proxies are not substituted for incident firstyear costs. No71.3%payer proxy, currency/year conversion, cost benefit multiplication, human-capital total orGDP/CGE analysis is performed. Needed: sourcecalendar-to2025price harmonisation, coverage/survivor weights, event definition, age-sex employment and wages, PA-specific absence/presenteeism, and retirement/replacement rules. Wage loss, productivity loss, GDP-equivalent output and macroGDP remain distinct.''')
    textfile('reports/HANDOFF_ROUND7.md',f'''# Round7 handoff
Local path: `{HERE}`
Branch: `{BRANCH}`
Base: `{BASE}`
Publication commit: obtain full SHA from the isolated branch tip / final delivery message; no self-referential commit hash embedded in its own contents.

## What changed
Only this new directory. Inventory acquisition scripts, src/model.py + src/pipeline.py, run_round7.py, config, evidence registers, source-locked aggregate inputs,5executable Notebooks, computed totals and identification envelopes, figures, reports, run logs, dependency versions and SHA manifest. Raw new public documents remain local in raw/; links, hashes and metadata are published, original source files stay untouched.

## New evidence actually obtained
Downloaded CKB published aggregate quintile data and extracted5rows; CHNS public main text recovered category definitions/sampling, but required joint proportions and supplement were not recovered. Kyu TableF expanded from104to260rows covering5diseases, and the incorrect blanket endpoint veto was revised. Brazilian Kyu mortalityCRA public primary text archived; new Chinese firsteverIS firstyear medical and patient productivity amounts verified; official2025urban wage parameters verified. RAND workplace sample is confirmed not mainlandChina.

## Results actually generated
{summary['baseline_cells']} age-sex-year disease total cells, {summary['baseline_totals']} national disease-endpoint-year totals; {summary['attributable_rows']}2025attribution rows; {summary['scenario_rows']}annual bounded/blocked scenario rows and {summary['decomposition_rows']}age-sex decomposition rows. The new calculations comprise conservative exact600 identification envelopes and separate low-category proxy sensitivities for IHD/IS events and30–69mortality. They are real executed numeric analyses, NOT national point estimates or95%UIs. Baseline disease burden is never labelled alreadyPAattributed. R2/R3national benefits remain unidentified. YLD/YLL/DALY/Prevalence attribution is not released; their disease totals exist separately.

Population2025={summary['population_2025']:,}; weighted inactivity={summary['p2025']:.10%}. Fixed2025weights at85%={summary['p2025']*.85:.10%}; future crude rates vary. P15=.15R1 completed-target identity is algebra, not a finding. Both inactive/active decomposition, zero/within-inactive shape and active tail remain needed forR3.

## Remaining actions
1. Request the precise authorised China weighted dose-bin aggregates specified in remaining_data_requests.csv, including zeros, below600, active support and tail>25500/30600. No need to upload individual records. No nationwide fine distribution recovered in checked inventory.
2. Work decides whether event endpoint transport, public-precedent30–69 mortality sensitivity and proposed local-shape calibration are appropriate for manuscript analyses. No sensitivity is silently promoted to main.
3. User-login GBD2023risk-attributed export query is specified with unverified filter capabilities labelled.13local export members contain no risk dimensions. Need actual2023TMREL/method source, not2019/2021assumption; externalGBD attribution must remain separate.
4. Obtain recent rawT2D/breast and colon-only burden (if tool supports); resolve Carlsson selectedT2DvsLADA table; preserve all13candidate disease distinctions.
5. Follow up CNSRIII pricecalendar/survivor coverage and Chinese age-sex employment/wage/WPAI inputs. No economic aggregate qualifies yet.

## Reproduce and scope
From repo `.venv/Scripts/python.exe new_study/round7_burden_evidence/run_round7.py --execute-notebooks`. Evidence download scripts are optional acquisition only; computational run is offline with local locked inputs. Checks distinguish software/data integrity from scientific gates. See validation_report.json and notebook_execution.json for actual statuses. Figures show observed grid/identified ranges only.
No R1–6 or original ZIP modifications; no individual-record access, natural-history, patient-years, CEA, policy cost, CGE orPSA run; no main merge. Some objectives remain evidence-blocked and must not be described as full national scenario point-result completion.''')
    textfile('README.md',f'''# Round7 burden and evidence
Isolated `{BRANCH}` based on `{BASE}`. Read reports/HANDOFF_ROUND7.md first.

Run offline: `../../.venv/Scripts/python.exe run_round7.py --execute-notebooks` from this directory, or repo `.venv/Scripts/python.exe new_study/round7_burden_evidence/run_round7.py --execute-notebooks`.

Delivered: real GBD/WPP disease totals; exact600 conservative identification envelopes (NOT point estimates/95%UI); separate category-proxy sensitivities; five source grids; Chinese firstyearIS and wage evidence. R2/R3 and national point estimates need the specified dose distribution; no economic totals are approved. Scientific gate failure is not disguised by software test success. Source paths resolved through pathlib/config. Raw acquisitions are local only; no original ZIP or history rewritten. Five Notebooks call the same src functions and are actually executed.
''')
    textfile('DATA_DICTIONARY.md','''# Data dictionary
Results: year/calendar year; disease/IHD or IS ONLY; endpoint/GBD original measure mapped to Incidence,Deaths,YLD,YLL,DALY,Prevalence; population/persons; baseline_total/annual disease events or prevalent persons, YLD/YLL/DALY years; population_scope/China20+ or30–69. No totals across different endpoints.
benefit_point/empty when not identified; benefit_lower_bound and upper_bound/identification envelopes conditional on fixed central risk and mapping assumptions, not samplingUIs; category_proxy identifies a different pooled-category counterfactual. benefit_rate_*/per100000 corresponding scope; benefit_pct_*/percent of disease total in same scope. increment_vs_P15 is coupled difference, remaining_disease includes non-PA disease, remaining_R1_attributable is residual relative to that specific counterfactual. Zero bounds are genuine mathematical limits; missing data use empty CSV cells.
Exposure: p_inactive/proportion; p_P15/intervention marginal; alpha/fraction of original inactive movers; shared_parameter_id/coarse observed survey parameter shared by fine ages. No independent fine-age CIs.95+ merges WPP95–99and100+; never splits GBD95+.
GBD inputs: rates per100000, point/lower/upper from original detailed2023 raw export; lower/upper not aggregated as95%UI. Citation retained in input rawZIP and run provenance. New public-source manuscripts/XML stay local to avoid assuming redistribution rights. Published factual tabulations and original analysis code only are staged; no microdata.
Economic: original currency/scope preserved. original_price_year and legacy_assumed_price_year are distinct. Unit per selected survivor differs from all incident cases. Source-value verification does not imply national economic admission.
Registers: evidence_id/cost_id/rr_id/parameter_id unique. source_status, exposure_match, endpoint_match, allowed_uses, structural_assumptions and model_ready are distinct. Computational PASS does not release scientific gates.''')
    selected=[r for r in read(HERE/'results/scenario_health_benefits.csv') if r['year']=='2030' and r['analysis_mode']=='SUPPORT_FREE_CONTINUOUS']
    with (HERE/'reports/HANDOFF_ROUND7.md').open('a',encoding='utf-8',newline='\n') as f:
        f.write('\n## 2030 numerical illustration: conservative identification envelopes\n\nDisease | Endpoint | Scope | Scenario | Lower | Upper\n--- | --- | --- | --- | ---: | ---:\n')
        for r in selected:f.write(' | '.join([r['disease'],r['endpoint'],r['population_scope'],r['scenario'],f"{float(r['benefit_lower_bound']):,.1f}",f"{float(r['benefit_upper_bound']):,.1f}"])+'\n')
        f.write('\nThese are weak outer bounds conditional on a cause-event/mortality transport sensitivity, not an expected benefit or95%UI. They demonstrate the consequence of unidentified within-inactive and active dose distributions. Low-category proxy results are separate rows and must not be substituted for exact600.\n')

def build():
    setup();extract_evidence();matrix();economies();requests();summary=calculate();reports(summary);checks();figures();notebooks()
    # Additional conclusions are sourced by exact public abstract location, not substituted risk measures.
    for report in ['RR_AND_CRA_ADMISSION_REVIEW.md','HANDOFF_ROUND7.md']:
        p=HERE/'reports'/report
        with p.open('a',encoding='utf-8',newline='\n') as f:f.write('\nAdditional resolved risk facts: Schuch2018 adult high-vs-low adjustedOR0.78(0.70–0.87), notRR; older subgroup is separate. Liu2017 leisure PA per10MET-h/week RR0.94(0.92–0.96); inactive-vs-recommended contrast has upperCI0.97, a distinct contrast. Exposure domains and high/low categories still do not match totalgross600. No OR-to-RR substitution. Original abstracts PMID29690792/28348016 are recorded separately from fulltext. ChinaT2D incident-complication cost source DOI10.1007/s13300-020-00967-y was additionally reviewed: MI onset-quarter cost19633CNY is NOT T2D-own firstyear cost and must not duplicate IHD costs.\n')
    jwrite(HERE/'logs/run_summary.json',dict(**summary,baseline_commit=BASE,branch=BRANCH,executed_at=datetime.now(timezone.utc).isoformat(),modules='Round7 CRA only',point_estimates_released=False))
    jwrite(HERE/'logs/dependency_versions.json',dict(python=sys.version,**{name:__import__(name).__version__ for name in ['numpy','pandas','scipy','matplotlib','pypdf','nbformat','nbclient']}))
    print(json.dumps(summary,ensure_ascii=False),flush=True)
def finalize():
    checks()
    source_provenance=[]
    for log in ['evidence_acquisition.json','additional_evidence_acquisition.json']:
        for r in json.loads((HERE/'logs'/log).read_text('utf-8')):
            p=HERE/'raw'/r['file'];source_provenance.append(dict(file='raw/'+r['file'],url=r['url'],acquisition_status=r['status'],local_bytes_archived=p.exists(),file_obtained_utc=datetime.fromtimestamp(p.stat().st_mtime,timezone.utc).isoformat() if p.exists() else '',sha256=sha(p) if p.exists() else '',content_status='CHALLENGE_NOT_ARTICLE' if r['file']=='China_ACS_first_year_abstract.html' else 'SEE_CONTENT_CHECKS_AND_EVIDENCE_REGISTER',distribution_permission='NOT_ASSUMED; local archive only'))
    jwrite(HERE/'logs/source_provenance.json',source_provenance)
    paths=[]
    for p in sorted(HERE.rglob('*')):
        if not p.is_file() or p.name=='sha256_manifest.csv' or any(s in ['__pycache__','.runtime'] for s in p.parts):continue
        paths.append(dict(path=p.relative_to(HERE).as_posix(),sha256=sha(p),bytes=p.stat().st_size,publication='LOCAL_SOURCE_ONLY' if 'raw' in p.relative_to(HERE).parts else 'REVIEWABLE_PUBLIC_DERIVATIVE'))
    write(HERE/'sha256_manifest.csv',paths)
    print('FINALIZED',len(paths),'files; scientific evidence gates are distinct from execution checks',flush=True)
