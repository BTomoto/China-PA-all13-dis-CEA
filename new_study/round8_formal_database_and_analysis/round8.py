"""Round 8 migration and deterministic static CRA. Never executes legacy models."""
from pathlib import Path
import sys, json, hashlib, zipfile, io, subprocess, shutil, math, re
import numpy as np
import pandas as pd
from inspect_sources import workbook
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
R1=ROOT/'new_study/round1_20261112'
R7=ROOT/'new_study/round7_burden_evidence'
BASE='0aaa68fd8cf7bfd2230d02c28abcdb90e5fa6a37'
BRANCH='codex/formal-database-and-analysis-round8'
SHORT={'Deaths':'Deaths','Incidence':'Incidence','Prevalence':'Prevalence','YLLs (Years of Life Lost)':'YLL','YLDs (Years Lived with Disability)':'YLD','DALYs (Disability-Adjusted Life Years)':'DALY'}
CAUSE={493:'IHD',495:'IS',496:'ICH',497:'SAH',976:'T2D',429:'breast_cancer',441:'colorectal_cancer',435:'uterine_cancer',411:'oesophageal_cancer',414:'stomach_cancer',471:'kidney_cancer',474:'bladder_cancer',543:'AD_and_other_dementias',567:'depression'}
AGE=[f'{a}-{a+4}' for a in range(20,70,5)]+['70+']
SCI_LIMIT='Binary working model assigns the low-active category RR to the combined active category; this is an explicit approximation, not a measured RR for all >=600. Legacy 2025 exposure conversion is unresolved. Constant 2023 rates; instantaneous response; no cohort interpretation.'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return pd.read_csv(p,keep_default_na=False)
def save(df,p):
 p=HERE/p;p.parent.mkdir(parents=True,exist_ok=True);df.to_csv(p,index=False,lineterminator='\n',float_format='%.15g')
def js(p,o):
 p=HERE/p;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(o,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
def txt(p,s):
 p=HERE/p;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(s,encoding='utf-8',newline='\n')
def rel(p):return Path(p).relative_to(ROOT).as_posix()
def mark(df,domain,path,sheet='',status='A_FORMAL_REUSE'):
 df=df.copy();df['domain']=domain;df['origin_path']=rel(path);df['origin_sheet_or_table']=sheet;df['source_file_sha256']=sha(path);df['source_id']=sha(path)[:16];df['geography']='China';df['admission_status']=status
 for c in ['year','sex','age_group','disease','cause_id','measure','metric','unit','val','lower','upper','transformation','limitation']:
  if c not in df:df[c]=''
 df['variable_id']=[domain+'_'+hashlib.sha256((rel(path)+'|'+sheet+'|'+str(i)).encode()).hexdigest()[:20] for i in range(len(df))]
 return df
def inventory():
 paths=[ROOT/'data/Public_model_inputs.xlsx',R1/'handoff/continuation/data/New_study_inputs.xlsx']
 records=[];tables={}
 schema=json.loads((ROOT/'data/input_schema.json').read_text('utf-8'))
 specs={x['sheet']:x['key'] for x in schema}
 for p in paths:
  for name,d in workbook(p).items():
   key=specs.get(name,name);tables[(rel(p),name)]=d
   if any(w in key.lower() for w in ['policy','programme','implementation','lag','gdp','macro','payer']):cls='D_ARCHIVE_ONLY'
   elif any(w in key.lower() for w in ['cost','hypertension','rr']):cls='C_CONDITIONAL_REUSE'
   else:cls='B_REUSE_AFTER_TRANSFORMATION'
   dest='database/legacy_tables/'+hashlib.sha256((rel(p)+'|'+name).encode()).hexdigest()[:12]+'.csv'
   save(d,dest)
   records.append(dict(origin_path=rel(p),origin_sheet_or_table=name,legacy_key=key,rows=len(d),sha256=sha(p),reuse_class=cls,new_path=dest,decision='Preserved table; row-level admission is separate',model_read_path='src/public_inputs.py -> src/aggregate_inputs.py -> src/run_d1_d10_stage.py:load_inputs'))
 for entry in ['input/gbd_standardized','input/population','input/hypertension','input/disease_costs','input/prepublication_extensions','config','reference/parameter_tables','new_study/round1_20261112/candidate_inputs','new_study/round1_20261112/handoff/continuation/registers']:
  p=ROOT/entry;files=sorted(x for x in p.rglob('*') if x.is_file()) if p.exists() else []
  records.append(dict(origin_path=entry,origin_sheet_or_table='',legacy_key='',rows=len(files),sha256='',reuse_class='B_REUSE_AFTER_TRANSFORMATION' if files else 'D_ARCHIVE_ONLY',new_path='database/legacy_tables or canonical domain table',decision='Actual directory inspected; workbook schema supplies virtual input paths' if files else 'Directory absent/empty; equivalent workbook sheets inspected',model_read_path='src/public_inputs.py writes schema-key paths; NOT executed'))
 for p in sorted((ROOT/'new_study').glob('round*/**/*.csv')):
  if HERE in p.parents or any(x in p.parts for x in ['raw','source_data']):continue
  if any(x in p.parts for x in ['registers','candidate_inputs','inputs','results']):
   records.append(dict(origin_path=rel(p),origin_sheet_or_table='CSV',legacy_key='',rows=sum(1 for _ in p.open(encoding='utf-8-sig'))-1,sha256=sha(p),reuse_class='C_CONDITIONAL_REUSE',new_path='database domain table or evidence archive',decision='Content inventoried; no inherited APPROVED status',model_read_path='Historical result is not a reverse-derived parameter'))
 # Commit history inventory: bounded path inventory, no checkout or legacy execution.
 history=subprocess.check_output(['git','log','--all','--format=%H','--name-only','--','input','config','data','reference','src'],cwd=ROOT,text=True,encoding='utf-8')
 txt('logs/history_paths.txt',history)
 for p in sorted((ROOT.parent/'Data').glob('*')) if (ROOT.parent/'Data').exists() else []:
  records.append(dict(origin_path=str(p),origin_sheet_or_table='handoff package',legacy_key='',rows='',sha256=sha(p),reuse_class='D_ARCHIVE_ONLY',new_path='',decision='Already extracted handoff duplicate; raw preserved',model_read_path='Local archive inventory'))
 cross=pd.DataFrame(records);save(cross,'database/old_to_new_crosswalk.csv')
 return tables,cross
def migrate():
 tables,cross=inventory();b=R1/'candidate_inputs'
 # Exact official Medium; optional High/Low are already archived WPP-derived midyear series.
 p=read(ROOT/'new_study/round2_20261112/registers/population_input_whitelist_v1.csv');p=p.rename(columns={'population_persons':'val'});p['variant']='Medium';p['unit']='persons';p['source_column']=p['sex'].map({'Male':'PopMale','Female':'PopFemale'})
 p=mark(p,'population',ROOT/'new_study/round2_20261112/registers/population_input_whitelist_v1.csv');p['transformation']='Official WPP2024 PopMale/PopFemale in thousands converted to persons; 1 July'
 f=read(b/'population_future_legacy.csv');f=f[f.variant.isin(['Low','High'])].copy();f=f.rename(columns={'population':'val'});f=mark(f,'population_variant',b/'population_future_legacy.csv',status='C_CONDITIONAL_REUSE');f['source_column']=f.sex.map({'Male':'popMproj variant','Female':'popFproj variant'});f['limitation']='Archived PPgp endyear interpolation; 22 cells; not official single-file July1 series';f['transformation']='mean endyear(t-1,t) as archived'
 p=pd.concat([p,f],ignore_index=True);save(p,'database/population.csv')
 hp=mark(read(b/'population_history_legacy.csv'),'population_history',b/'population_history_legacy.csv');save(hp,'database/population_history.csv')
 pa=read(b/'pa_2025_legacy.csv');pa['val']=pa.p_inactive;pa['unit']='proportion';pa['lower']='';pa['upper']='';pa=mark(pa,'pa_binary',b/'pa_2025_legacy.csv');pa['limitation']='Researcher-selected legacy model baseline; NOT observed 2025 surveillance; 2018->2025 chain unresolved; psa_precision_n is assumption only';pa['transformation']='Original 22 probabilities unchanged; WPP weights replace rounded workbook population';save(pa,'database/pa_binary_exposure.csv')
 obs=mark(read(b/'pa_2018_published_verified.csv'),'pa_observed',b/'pa_2018_published_verified.csv');obs['val']=obs.p_inactive;obs['unit']='proportion';obs['lower']=obs.lower_95;obs['upper']=obs.upper_95
 overall=[]
 for sex,v,lo,hi in [('Both',.223,.209,.237),('Male',.244,.230,.258),('Female',.202,.186,.218)]:overall.append(dict(year=2018,sex=sex,age_group='18+',p_inactive=v,val=v,lower=lo,upper=hi,lower_95=lo,upper_95=hi,unit='proportion',source_location='Gao2023 Abstract Results; archived HTML lines47/70',source_url='https://html.rhhz.net/zhlxbx/20230803.htm',limitation='Complex-survey weighted18+; not comparable20+ model crude rate without age alignment'))
 overall=mark(pd.DataFrame(overall),'pa_observed_overall',R1/'raw/pa/Gao2018.html');obs=pd.concat([obs,overall],ignore_index=True);save(obs,'database/pa_published_validation.csv')
 # Keep original Number records and source reconciliation, then add detailed verified Rate/Number exports.
 comp=read(R1/'registers/gbd_row_comparison.csv');keys=['cause_id','measure_id','year','sex_name','age_id']
 co=comp.rename(columns={'sex':'sex_name'})[keys+['status','method','point_match']];assert not co.duplicated(keys).any()
 frames=[]
 for name in ['gbd_burden_legacy.csv','gbd_cases_legacy.csv']:
  d=read(b/name).merge(co,on=keys,how='left',validate='one_to_one');d['source_status']=d.status.map({'已核验':'SOURCE_VERIFIED','部分核验':'POINT_VERIFIED_UI_CONDITIONAL','缺原件':'LEGACY_STANDARDIZED_TRACEABLE'}).fillna('LEGACY_STANDARDIZED_TRACEABLE');d=mark(d,'gbd',b/name,status='B_REUSE_AFTER_TRANSFORMATION');d['source_record_id']=name+':'+d.index.astype(str);frames.append(d)
 cfg=json.loads((R7/'config.json').read_text('utf-8'))
 for path in cfg['gbd']:
  zpath=ROOT/path
  with zipfile.ZipFile(zpath) as z:
   for member in z.namelist():
    if not member.endswith('.csv'):continue
    d=pd.read_csv(z.open(member));d=d[d.year.between(2010,2023)&d.sex_name.isin(['Male','Female'])];d=mark(d,'gbd_raw',zpath,member);d['source_status']='SOURCE_VERIFIED';d['source_record_id']=Path(path).name+':'+d.index.astype(str);d['source_file']=Path(path).name;frames.append(d)
 g=pd.concat(frames,ignore_index=True);g['sex']=g.sex_name;g['age_group']=g.age_name.str.replace(' years','',regex=False);g['disease']=g.cause_id.map(CAUSE);g['measure']=g.measure_name.map(SHORT);g['metric']=g.metric_name;g['unit']=g['measure'].map({'Deaths':'deaths','Incidence':'incident events','Prevalence':'prevalent persons','YLL':'years lost','YLD':'years lived with disability','DALY':'disability-adjusted life years'});g.loc[g.metric.eq('Rate'),'unit']=g.loc[g.metric.eq('Rate'),'unit']+' per100000';g['limitation']='No aggregate UI without draws; standardized high-age bounds retained only as historical fields';g['transformation']=np.where(g.domain.eq('gbd_raw'),'Direct raw export','Legacy Number table; exact status from round1 row reconciliation')
 # Direct raw takes priority for same exact key; retain displaced originals in legacy sheets.
 g['_priority']=g.domain.eq('gbd_raw').astype(int);g=g.sort_values('_priority').drop_duplicates(['cause_id','measure_id','metric_id','year','sex','age_group'],keep='last').drop(columns='_priority');g=g[g.disease.notna()&g.measure.notna()].copy()
 save(g[g.measure.isin(['Deaths','YLL','YLD','DALY'])],'database/gbd_burden.csv');save(g[g.measure.isin(['Incidence','Prevalence'])],'database/gbd_cases.csv')
 save(mark(read(b/'hypertension_legacy.csv'),'hypertension',b/'hypertension_legacy.csv',status='C_CONDITIONAL_REUSE'),'database/hypertension_candidates.csv')
 save(mark(read(b/'disease_mapping_legacy.csv'),'disease_mapping',b/'disease_mapping_legacy.csv',status='C_CONDITIONAL_REUSE'),'database/disease_mapping.csv')
 rr=mark(read(b/'rr_legacy.csv'),'rr_legacy',b/'rr_legacy.csv',status='D_ARCHIVE_ONLY');save(rr,'database/rr_evidence_all.csv')
 for source,name in [('medical_cost_evidence_register.csv','medical_cost_candidates.csv'),('productivity_evidence_register.csv','productivity_candidates.csv'),('rr_function_register.csv','rr_round7_review.csv')]:
  save(mark(read(R7/'registers'/source),name.removesuffix('.csv'),R7/'registers'/source,status='C_CONDITIONAL_REUSE'),'database/'+name)
 # Preserve all independent cost sources and explicit evidence links; never join costs on outcome_id.
 for path in [b/'cost_legacy.csv',ROOT/'new_study/round2_audit_fix_20261112/registers/cost_admission_audit_v3.csv',ROOT/'new_study/round2_audit_fix_20261112/registers/cost_evidence_links_v3.csv']:
  d=read(path)
  if 'link_type' in d:d.loc[(d.link_type=='EXACT_LINK')&(d.assignment_allowed!='TRUE'),'link_type']='CANDIDATE_LINK'
  save(mark(d,'cost_archive',path,status='C_CONDITIONAL_REUSE'),'database/'+path.name)
 r=[]
 for cid,v,lo,hi,ad in [(493,.837,.791,.886,'FORMAL'),(495,.843,.779,.918,'FORMAL'),(429,.967,.937,.998,'FORMAL'),(976,.857,.816,.902,'CONDITIONAL_CRA_MAPPING')]:
  r.append(dict(rr_id='KYU_BINARY_'+str(cid),cause_id=cid,disease=CAUSE[cid],c_active_vs_inactive=v,c_lower=lo,c_upper=hi,rr_inactive_vs_active=1/v,rr_lower=1/hi,rr_upper=1/lo,effect_measure='pooled RR',exposure='<600 total gross MET-min/week',reference='600-3999 total gross MET-min/week',model_active_group='>=600 approximated by low-active RR',sex='Female' if cid==429 else 'Male|Female',age='20+ adult transport',outcome_admission=ad,source='https://doi.org/10.1136/bmj.i3857',source_location='Table 1',source_file_sha256=sha(R1/'raw/pmc_cloud/PMC4979358/PMC4979358.1.xml'),limitation=SCI_LIMIT+(' T2D: exact Carlsson selected subtype remains unresolved.' if cid==976 else '')))
 rr=pd.DataFrame(r);save(rr,'database/rr_admitted.csv')
 adm=[]
 for cid,disease in CAUSE.items():
  for ep in SHORT.values():
   status='BLOCKED_OUTCOME_MISMATCH';reason='No verified matching risk-exposure-disease pair';method='';sex='Female' if cid in [429,435] else 'Male|Female'
   if cid in [493,495,429,976] and ep=='Incidence':status=rr.loc[rr.cause_id.eq(cid),'outcome_admission'].iloc[0];reason='Prospective disease-event evidence; adult binary working model';method='Direct disease-event CRA'
   elif cid in [493,495,429,976] and ep in ['Deaths','YLL','YLD','DALY']:
    status='CONDITIONAL_CRA_MAPPING';method={'Deaths':'Assume disease incidence RR transports to fatal disease burden; not direct mortality RR','YLL':'Within age-sex cell assume attributed fatal events have same mean life-years lost','YLD':'Assume fraction of disease incidence is transferable to steady-state disability burden; same duration/severity; no cohort dynamics','DALY':'Sum separately attributed YLL and YLD; both conditional'}[ep];reason='Generic CRA method supports conditional proportional mapping, not empirical endpoint equivalence'
   if cid==976:reason+='; diabetes subtype selection incompletely resolved'
   if cid in [441,435,411,414]:reason='Risk subtype does not match aggregate GBD cause; no silent colon->CRC/endometrium->uterus/adeno->all/cardia->all mapping'
   if cid in [496,497]:reason='IS RR not applicable to hemorrhagic subtypes'
   if cid==543:reason='Legacy RR 1.40 source mismatch; AD not equal all dementias'
   if cid==567:reason='Adult high-vs-low OR is not total activity binary RR'
   if cid==567 and ep in ['Deaths','YLL']:status='NOT_APPLICABLE';reason='Nonfatal GBD depressive disorder endpoint'
   adm.append(dict(cause_id=cid,disease=disease,measure=ep,outcome_admission=status,sex_restriction=sex,method=method,reason=reason,source='https://www.ncbi.nlm.nih.gov/books/NBK11813/' if method else '',assumptions=SCI_LIMIT))
 for ep in SHORT.values():adm.append(dict(cause_id=-1,disease='hypertension',measure=ep,outcome_admission='NOT_APPLICABLE' if ep in ['Deaths','YLL','YLD','DALY'] else 'BLOCKED_OUTCOME_MISMATCH',sex_restriction='Male|Female',method='',reason='No qualifying incidence interface; legacy modelled prevalence retained; leisure-PA RR mismatch',source='',assumptions='No HTN burden added to IHD/stroke'))
 save(pd.DataFrame(adm),'registers/outcome_admission.csv')
 for name in ['formal_input_admission','conditional_inputs','excluded_legacy_inputs']:
  cls={'formal_input_admission':['A_FORMAL_REUSE','B_REUSE_AFTER_TRANSFORMATION'],'conditional_inputs':['C_CONDITIONAL_REUSE'],'excluded_legacy_inputs':['D_ARCHIVE_ONLY']}[name];s=cross[cross.reuse_class.isin(cls)];save(s,'database/'+name+'.csv');save(s,'registers/'+name+'.csv')
 gaps=pd.DataFrame([dict(domain='exposure',gap='Legacy 2018->2025 transformation not recovered',action='Model choice disclosed; does not block current binary analysis'),dict(domain='T2D',gap='Exact Carlsson selected PA row subtype',action='Conditional result only; review original study when available'),dict(domain='medical',gap='National treated incident coverage and uniform original price year',action='No national cost multiplication'),dict(domain='productivity',gap='Age-sex employment/wage plus China causal PA productivity evidence',action='No GDP point estimate'),dict(domain='disease_mapping',gap='Colon-only/endometrial/cardial/adenocarcinoma matched burden and subtype RR',action='Keep aggregate disease totals; corresponding attributed outputs blank')]);save(gaps,'database/genuine_remaining_gaps.csv');save(gaps,'registers/genuine_remaining_gaps.csv')
 # Source hashes include every file actually loaded plus old source inventories.
 source_paths=set(cross.loc[cross.sha256.ne(''),'origin_path'])
 for pth in list((R1/'candidate_inputs').glob('*.csv'))+[ROOT/x for x in cfg['gbd']]+[ROOT/'new_study/round2_20261112/registers/population_input_whitelist_v1.csv',R1/'raw/pa/Gao2018.html',R1/'raw/pmc_cloud/PMC4979358/PMC4979358.1.xml',ROOT/'src/run_d1_d10_stage.py',ROOT/'src/public_inputs.py',ROOT/'data/input_schema.json']:
  source_paths.add(rel(pth))
 manifest=[]
 for path in sorted(source_paths):
  pth=ROOT/path
  if pth.is_file():manifest.append(dict(origin_path=path,sha256=sha(pth),bytes=pth.stat().st_size,acquired='existing archive; original dates retained in source registers',version='GBD2023/WPP2024/legacy as recorded',public_role='Aggregate or source metadata; no individual records'))
 save(pd.DataFrame(manifest),'database/source_manifest.csv')
 transforms=[('PA','Preserve 22 values; replace population weights; no interpolation of observed 2018 rates'),('WPP','Medium official five-year PopMale/PopFemale; Low/High archive interpolation; aggregate only for matching old GBD70+'),('GBD','Prefer direct detailed Rate for IHD/IS; other Number / historical WPP2023 forms explicitly rebased rates, not original IHME rates'),('RR','c<1 active/inactive; inverse CI endpoints reversed'),('PAF','common baseline denominator for PAF_scenario; PIF = PAF_B0 - remaining_attributable_fraction'),('DALY','YLL+YLD point sum; never sum uncertainty interval limits'),('cost','Keep cost_id/evidence_id links; no disease-only source inheritance')]
 save(pd.DataFrame(transforms,columns=['domain','transformation']),'database/transformation_log.csv')
 js('config.json',dict(base_commit=BASE,branch=BRANCH,main_exposure='legacy_22_model_rates_with_official_WPP_weights',active_category_assumption='>=600 represented by Kyu low-active risk',main_population='Medium',main_rate='constant_2023',scenario={'B0':0,'P15_GRADUAL':'min(.15,.03*(year-2025))','P15_IMMEDIATE':.15,'R1':1},no_psa=True))
 return len(g)
def collapsed_population():
 p=read(HERE/'database/population.csv');p['age_group']=p.age_group.map(lambda a:'70+' if int(a.split('-')[0].replace('+',''))>=70 else a)
 return p.groupby(['variant','year','sex','age_group'],as_index=False).val.sum().rename(columns={'val':'population'})
def exposure_summary():
 pa=read(HERE/'database/pa_binary_exposure.csv');p=collapsed_population();p=p[p.variant.eq('Medium')&p.year.eq(2025)].merge(pa[['sex','age_group','p_inactive','population_million']],on=['sex','age_group'],validate='one_to_one');p['inactive_persons']=p.population*p.p_inactive;p['p_active']=1-p.p_inactive;p['result_status']='MODEL_BASELINE';p['evidence_tier']='LEGACY_MODEL_EXPOSURE';p['outcome_admission']='FORMAL';p['formal_point_estimate']=True;p['conditional_result']=False;p['structural_range']=False;p['limitation']='Legacy model values; not observed 2025; transformation chain unresolved';save(p,'results/baseline_exposure_2025.csv')
 out=[]
 for sex in ['Both','Male','Female']:
  s=p if sex=='Both' else p[p.sex.eq(sex)];out.append(dict(source='ROUND8_MAIN_WPP_WEIGHTED',sex=sex,age='20+',val=s.inactive_persons.sum()/s.population.sum(),population=s.population.sum()))
  out.append(dict(source='LEGACY_ROUNDED_POP_WEIGHTS',sex=sex,age='20+',val=(s.population_million*s.p_inactive).sum()/s.population_million.sum(),population=s.population_million.sum()*1e6))
 out.append(dict(source='ROUND7_2018_STRUCTURE_MODEL',sex='Both',age='20+',val=.2196605152043413,population=1113252964))
 save(pd.DataFrame(out),'results/exposure_source_comparison.csv')
 obs=read(HERE/'database/pa_published_validation.csv');obs=obs[['sex','age_group','val','lower','upper','source_location']].copy();rows=[]
 for r in obs.to_dict('records'):
  age=r['age_group'];lo=int(age.split('-')[0].replace('+','')) if str(age)[0].isdigit() else 20
  if age in ['18+','18-29','30-39','40-49','50-59','60-69','70+']:
   ages=AGE if age=='18+' else AGE[10:] if age=='70+' else [a for a in AGE if lo<=int(a.split('-')[0].replace('+',''))<=int(age.split('-')[1]) if a!='70+']
   s=p[p.age_group.isin(ages)];s=s if r['sex']=='Both' else s[s.sex.eq(r['sex'])]
   if len(s):rows.append(dict(**r,model_2025=(s.population*s.p_inactive).sum()/s.population.sum(),difference_pp=100*((s.population*s.p_inactive).sum()/s.population.sum()-r['val']),interpretation='Year+population weights+legacy transformation; 18-29 comparator vs20-29 is age mismatch; cannot isolate causes'))
 save(pd.DataFrame(rows),'results/exposure_2018_comparison.csv')
 return p
def rates():
 g=pd.concat([read(HERE/'database/gbd_burden.csv'),read(HERE/'database/gbd_cases.csv')],ignore_index=True)
 hp=read(HERE/'database/population_history.csv');hp=hp[['year','sex','age_group','population']]
 legacy=g[g.domain.eq('gbd')&g.metric.eq('Number')&g.age_group.isin(AGE)].copy();legacy=legacy.merge(hp,on=['year','sex','age_group'],validate='many_to_one');legacy['rate']=legacy.val/legacy.population*1e5
 slopes={}
 for k,s in legacy.groupby(['cause_id','measure','sex','age_group']):
  s=s[(s.rate>0)&s.year.between(2010,2023)]
  if len(s)>=2:slopes[k]=float(np.clip(np.polyfit(s.year,np.log(s.rate),1)[0],-.1,.1))
 anchor=legacy[legacy.year.eq(2023)].copy();anchor['rate_method']='2023 Number / WPP2023; rebased working rate';anchor['input_tier']=anchor.source_status
 # Raw rates retain 70-74 ...95+; population will match this grid, exposure remains70+.
 direct=g[g.domain.eq('gbd_raw')&g.year.eq(2023)&g.metric.eq('Rate')&g.age_group.str.match(r'^(20|25|30|35|40|45|50|55|60|65|70|75|80|85|90)-|^95\+$')].copy();direct['rate']=direct.val;direct['rate_method']='Direct GBD2023 Rate per100000';direct['input_tier']='SOURCE_VERIFIED'
 anchor=anchor[~anchor.cause_id.isin([493,495])];a=pd.concat([anchor,direct],ignore_index=True)
 a=a[~(a.cause_id.isin([429,435])&a.sex.eq('Male'))];a=a[~(a.cause_id.eq(567)&a.measure.isin(['Deaths','YLL']))]
 a['slope']=[slopes.get((int(r.cause_id),r.measure,r.sex,'70+' if int(r.age_group.split('-')[0].replace('+',''))>=70 else r.age_group),np.nan) for r in a.itertuples()]
 save(a,'database/model_rates_2023.csv');return a
def fraction(p0,p1,c):
 p0=np.asarray(p0);p1=np.asarray(p1)
 if np.any((p0<0)|(p0>1)|(p1<0)|(p1>1)) or c<=0:raise ValueError('invalid exposure or risk')
 den=p0+(1-p0)*c
 return (p0-p1)*(1-c)/den
def annual(pop_variant='Medium',rr_bound='point',trend=False):
 if pop_variant!='Medium':return annual_variant_from_main(pop_variant,rr_bound,trend)
 rates_=read(HERE/'database/model_rates_2023.csv');pa=read(HERE/'database/pa_binary_exposure.csv');pop=read(HERE/'database/population.csv');pop=pop[pop.variant.eq(pop_variant)].copy();rr=read(HERE/'database/rr_admitted.csv').set_index('cause_id');adm=read(HERE/'registers/outcome_admission.csv').set_index(['cause_id','measure'])
 rows=[]
 for r in rates_.itertuples():
  age=r.age_group;coarse='70+' if int(age.split('-')[0].replace('+',''))>=70 else age
  p0=float(pa[(pa.sex==r.sex)&(pa.age_group==coarse)].p_inactive.iloc[0]);cid=int(r.cause_id);gate=adm.loc[(cid,r.measure)].outcome_admission
  if pop_variant!='Medium' and cid in [493,495] and coarse=='70+':continue
  # For Low/High aggregate direct raw rates using WPP historical/detailed2023 proxy is not available;
  # instead use traceable old70+ Number/WPP2023 rate below, marked conditional.
  s=pop[pop.sex.eq(r.sex)]
  if age=='70+':s=s[s.age_group.map(lambda a:int(a.split('-')[0].replace('+',''))>=70)]
  elif age=='95+':s=s[s.age_group.isin(['95-99','100+','95+'])]
  else:s=s[s.age_group.eq(age)]
  for year,v in s.groupby('year').val.sum().items():
   if trend and (pd.isna(r.slope) or r.slope==''):continue
   factor=1.
   if trend:
    exposure=1+sum(1 if y<=2034 else max(0,(2040-y)/6) for y in range(2025,int(year)+1));factor=math.exp(float(r.slope)*exposure)
   total=float(v)*float(r.rate)/1e5*factor
   for scenario in ['B0','P15_GRADUAL','P15_IMMEDIATE','R1']:
    a={'B0':0,'P15_GRADUAL':min(.15,max(0,.03*(int(year)-2025))),'P15_IMMEDIATE':.15,'R1':1}[scenario]
    p1=p0*(1-a);paf=pif=attr=benefit=remaining=np.nan
    if gate in ['FORMAL','CONDITIONAL_CRA_MAPPING']:
     c=float(rr.loc[cid,{'point':'c_active_vs_inactive','lower':'c_lower','upper':'c_upper'}[rr_bound]])
     paf=float(fraction(p0,0,c));pif=float(fraction(p0,p1,c));attr=total*paf;benefit=total*pif;remaining=attr-benefit
    tier=r.input_tier;lim='M1_BINARY;M2_LEGACY_PA;M3_FIXED_RATE;'+('M4_WPP_REBASED;' if 'rebased' in r.rate_method else '')+'see METHODS_STATIC_CRA'
    rows.append(dict(year=int(year),scenario=scenario,disease=r.disease,cause_id=cid,measure=r.measure,sex=r.sex,age_group=age,population=float(v),baseline_total=total,p_inactive_B0=p0,p_inactive_scenario=p1,PAF_B0=paf,remaining_attributable_fraction_B0_denominator=paf-pif,PIF=pif,attributable_B0=attr,benefit=benefit,remaining_burden=remaining,rate_method=r.rate_method,input_source_status=tier,result_status='POINT_ESTIMATE' if gate=='FORMAL' else 'CONDITIONAL_POINT_ESTIMATE' if gate=='CONDITIONAL_CRA_MAPPING' else gate,evidence_tier=tier,outcome_admission=gate,formal_point_estimate=gate=='FORMAL',conditional_result=gate=='CONDITIONAL_CRA_MAPPING',structural_range=False,limitation=lim,variant=pop_variant,rr_bound=rr_bound,rate_scenario='LEGACY_DAMPED_TREND' if trend else 'FIXED_2023'))
 d=pd.DataFrame(rows)
 if pop_variant!='Medium':
  # Fully matched22-cell old rates are used for all age groups in variant sensitivity, not partial high-age omission.
  d=annual_variant_from_main(pop_variant,rr_bound,trend)
 return d
def annual_variant_from_main(variant,rr_bound,trend):
 # Hold each disease's fine-age composition within70+ at Medium, apply archived variant70+ ratio.
 # This unavoidable low/high age-resolution approximation is explicit and independently conditional.
 d=annual('Medium',rr_bound,trend);cp=collapsed_population();med=cp[cp.variant.eq('Medium')].set_index(['year','sex','age_group']).population;other=cp[cp.variant.eq(variant)].set_index(['year','sex','age_group']).population
 d['coarse']=d.age_group.map(lambda a:'70+' if int(a.split('-')[0].replace('+',''))>=70 else a)
 weights=np.array([other.loc[(r.year,r.sex,r.coarse)]/med.loc[(r.year,r.sex,r.coarse)] for r in d.itertuples()])
 for col in ['population','baseline_total','attributable_B0','benefit','remaining_burden']:d[col]=d[col]*weights
 d['variant']=variant;d['limitation']+=' Low/High70+ allocated using Medium fine-age composition; archived interpolated WPP variant.';d['conditional_result']=True;d['formal_point_estimate']=False;d.loc[d.outcome_admission.isin(['FORMAL','CONDITIONAL_CRA_MAPPING']),'outcome_admission']='CONDITIONAL_CRA_MAPPING';return d.drop(columns='coarse')
META=['result_status','evidence_tier','outcome_admission','formal_point_estimate','conditional_result','structural_range','limitation']
def aggregate(d,groups):
 # Missing remains missing; never sum an entirely blocked group to zero.
 nums=['baseline_total','attributable_B0','benefit','remaining_burden']
 out=d.groupby(groups+['outcome_admission'],dropna=False)[nums].sum(min_count=1).reset_index()
 out['result_status']=out.outcome_admission.map({'FORMAL':'POINT_ESTIMATE','CONDITIONAL_CRA_MAPPING':'CONDITIONAL_POINT_ESTIMATE'}).fillna(out.outcome_admission);out['evidence_tier']='See source-status detail; no aggregate UI';out['formal_point_estimate']=out.outcome_admission.eq('FORMAL');out['conditional_result']=out.outcome_admission.eq('CONDITIONAL_CRA_MAPPING');out['structural_range']=False;out['limitation']=SCI_LIMIT
 return out
def calculate():
 exposure_summary();rates();d=annual();save(d[d.outcome_admission.isin(['FORMAL','CONDITIONAL_CRA_MAPPING'])],'results/disease_age_sex_decomposition.csv');save(d[d.scenario.eq('B0')][['year','disease','cause_id','measure','sex','age_group','population','baseline_total','rate_method','input_source_status']],'results/baseline_total_age_sex.csv')
 main=aggregate(d,['year','scenario','disease','measure']);save(main,'results/scenario_health_benefits.csv')
 base=main[(main.year==2025)&(main.scenario=='B0')].copy();base['total_burden_status']='CALCULATED_GBD_CAUSE_TOTAL';base.loc[base.disease.eq('AD_and_other_dementias')&base.measure.isin(['Deaths','YLL']),'total_burden_status']='PARTIAL_AGE_COVERAGE_40PLUS';save(base,'results/attributable_burden_2025.csv')
 h=read(HERE/'database/hypertension_candidates.csv');pp=collapsed_population();pp=pp[pp.year.eq(2025)&pp.variant.eq('Medium')];h=h.merge(pp,on=['sex','age_group'],validate='one_to_one');htotal=(h.hypertension_prevalence_2025*h.population).sum()
 extras=[]
 for ep in SHORT.values():extras.append(dict(year=2025,scenario='B0',disease='hypertension',measure=ep,baseline_total=htotal if ep=='Prevalence' else np.nan,attributable_B0=np.nan,benefit=np.nan,remaining_burden=np.nan,result_status='CONDITIONAL_MODELLED_PREVALENCE' if ep=='Prevalence' else 'NOT_APPLICABLE' if ep in ['Deaths','YLL','YLD','DALY'] else 'MISSING_INCIDENCE_INTERFACE',evidence_tier='LEGACY_MODELLED_SURVEY_CALIBRATION',outcome_admission='BLOCKED_OUTCOME_MISMATCH',formal_point_estimate=False,conditional_result=ep=='Prevalence',structural_range=False,limitation='Legacy calibrated prevalence, not GBD cause; no attributed HTN deaths/DALYs',total_burden_status='CONDITIONAL_MODELLED_PREVALENCE' if ep=='Prevalence' else 'NOT_ESTIMATED'))
 for ep in ['Deaths','YLL']:extras.append(dict(year=2025,scenario='B0',disease='depression',measure=ep,baseline_total=np.nan,attributable_B0=np.nan,benefit=np.nan,remaining_burden=np.nan,result_status='NOT_APPLICABLE',evidence_tier='GBD_NONFATAL',outcome_admission='NOT_APPLICABLE',formal_point_estimate=False,conditional_result=False,structural_range=False,limitation='Not applicable, not zero',total_burden_status='NOT_APPLICABLE'))
 save(pd.concat([base,pd.DataFrame(extras)],ignore_index=True),'results/baseline_disease_burden_2025.csv')
 totals=[]
 for end in [2030,2034,2050]:
  x=aggregate(d[d.year.le(end)],['scenario','disease','measure']);x['start_year']=2025;x['end_year']=end;x['years_inclusive']=end-2024;totals.append(x)
 cum=pd.concat(totals,ignore_index=True);save(cum,'results/scenario_comparison.csv');save(cum[cum.scenario.eq('P15_GRADUAL')],'results/P15_cumulative.csv');save(cum[cum.scenario.eq('R1')],'results/R1_cumulative.csv');save(cum[cum.scenario.isin(['P15_GRADUAL','P15_IMMEDIATE'])],'results/time_path_sensitivity.csv')
 for name,cols in [('age_contribution',['age_group']),('sex_contribution',['sex']),('disease_age',['disease','age_group']),('disease_sex',['disease','sex']),('age_sex',['age_group','sex'])]:save(aggregate(d,['scenario','measure']+cols),'results/'+name+'.csv')
 rank=cum[cum.scenario.eq('P15_GRADUAL')&cum.end_year.eq(2050)&cum.measure.eq('Incidence')].sort_values('benefit',ascending=False);save(rank,'results/disease_contribution_ranking.csv')
 rrout=[];popout=[]
 for bound in ['lower','upper']:
  x=aggregate(annual(rr_bound=bound),['scenario','disease','measure']);x['risk_input_bound']=bound;x['uncertainty_interpretation']='One-at-a-time deterministic literature endpoint; NOT joint95%UI';rrout.append(x)
 save(pd.concat(rrout),'results/rr_deterministic_sensitivity.csv')
 for variant in ['Medium','Low','High']:
  x=aggregate(d if variant=='Medium' else annual(variant),['scenario','disease','measure']);x['variant']=variant
  if variant!='Medium':x['limitation']+=' Archived endyear-derived variant;70+ shares fixed to Medium.'
  popout.append(x)
 save(pd.concat(popout),'results/population_sensitivity.csv')
 tr=aggregate(annual(trend=True),['scenario','disease','measure']);tr['sensitivity']='Legacy 2010-2023 log-rate fit capped+-0.1; damping after2034; not a forecast';tr['conditional_result']=True;tr['formal_point_estimate']=False;save(tr,'results/disease_rate_trend_sensitivity.csv')
 save(pd.DataFrame([dict(scenario='STABLE',status='CALCULATED',parameter=0,reason='Main model'),dict(scenario='IMPROVING',status='NOT_ESTIMATED',parameter=None,reason='No validated China trend parameter in inspected old source chain'),dict(scenario='WORSENING',status='NOT_ESTIMATED',parameter=.0084,reason='Legacy0.84% source/definition not validated; do not upgrade assumption')]),'results/exposure_trend_sensitivity.csv')
 economic=[]
 for disease in list(CAUSE.values())+['hypertension']:
  economic.append(dict(disease=disease,module='direct_medical',value=None,result_status='NOT_ESTIMATED',evidence_tier='SOURCE_OR_SCOPE_NOT_ADMITTED',outcome_admission='BLOCKED_COST_INTERFACE',formal_point_estimate=False,conditional_result=False,structural_range=False,limitation='No jointly qualified source price-year, treated incident coverage and non-overlapping first-year cost; see cost_id-specific archive'))
 economic.append(dict(disease='All',module='productivity',value=None,result_status='NOT_ESTIMATED',evidence_tier='NO_CHINA_CAUSAL_PARAMETER',outcome_admission='BLOCKED_ECONOMIC_INTERFACE',formal_point_estimate=False,conditional_result=False,structural_range=False,limitation='No age-sex employment/wage and applicable PA productivity response; no GDP proxy'))
 save(pd.DataFrame(economic),'results/partial_medical_savings.csv');save(pd.DataFrame(economic),'registers/economic_admission.csv')
 return d,main,cum
