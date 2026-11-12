"""Read-only source comparisons and input-format audit. No health/economic model.
Run from any directory with Python 3.11+ (stdlib only).
"""
import csv, gzip, hashlib, io, json, math, re, zipfile
from collections import Counter, defaultdict
from pathlib import Path
from html.parser import HTMLParser

ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parents[1]
DATE='2026-11-12'
def read(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def write(p,rows):
    if not rows:return
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
checks=[]
def check(name,ok,detail):checks.append(dict(check=name,passed=bool(ok),detail=detail))
def close(a,b):return math.isclose(float(a),float(b),rel_tol=1e-10,abs_tol=1e-8)
def plain(p):return re.sub(r'\s+',' ',re.sub('<[^>]+>',' ',p.read_text(encoding='utf-8',errors='replace')))

def main():
    # Preserve every previously tracked byte; README additions are explicitly allowed.
    preserved=[]
    for r in read(ROOT/'registers/base_tracked_sha256.csv'):
        p=REPO/r['path']; ok=p.exists() and digest(p)==r['sha256']
        preserved.append(dict(path=r['path'],original_sha256=r['sha256'],current_sha256=digest(p) if p.exists() else '',unchanged=ok,allowed_documentation_edit=r['path'] in ['README.md','new_study/README.md']))
    check('old_files_preserved',all(r['unchanged'] or r['allowed_documentation_edit'] for r in preserved),f'{len(preserved)} base files; only README additions allowed')
    write(ROOT/'checks/preservation.csv',preserved)
    h=ROOT/'handoff/continuation'
    # The two supplied workbooks must agree byte for byte, not merely visually.
    check('handoff_workbook_duplicate',digest(h/'data/New_study_inputs.xlsx')==digest(ROOT/'handoff/supplement/New_study_inputs.xlsx'),'Both supplied XLSX versions compared by SHA256')
    duplicates=defaultdict(list)
    for p in ROOT.rglob('*'):
        if p.is_file() and not any(x in p.parts for x in ['checks','extracted_text','__pycache__']):duplicates[digest(p)].append(p.relative_to(ROOT).as_posix())
    write(ROOT/'registers/duplicate_files.csv',[dict(sha256=s,paths=' | '.join(ps),selection='handoff/continuation for original registers; handoff/supplement for additional RR provenance JSON; candidate_inputs only flat interface, never a second independent source') for s,ps in duplicates.items() if len(ps)>1])
    # Validate and independently parse actual GBD export CSVs in the four ZIPs.
    raw={};index={};raw_manifest=[]
    keycols=['population_group_id','location_id','sex_id','age_id','cause_id','measure_id','metric_id','year']
    def key(r):return tuple(str(r[k]) for k in keycols)
    for p in (h/'source_data/gbd').glob('*.zip'):
        with zipfile.ZipFile(p) as z:
            check('zip_crc_'+p.name,z.testzip() is None,'ZIP CRC checked')
            n=next(n for n in z.namelist() if n.endswith('.csv'))
            a=list(csv.DictReader(io.TextIOWrapper(z.open(n),encoding='utf-8-sig')))
        raw[p.name]=a;index[p.name]={key(r):r for r in a}
        check('raw_unique_'+p.name,len(index[p.name])==len(a),f'{len(a)} rows')
        raw_manifest.append(dict(file=p.relative_to(ROOT).as_posix(),sha256=digest(p),rows=len(a),years='|'.join(sorted({r['year'] for r in a},key=int)),measures='|'.join(sorted({r['measure_name'] for r in a})),causes='|'.join(sorted({r['cause_name'] for r in a})),obtained_date=DATE,original_download_date='',status='部分核验',notes='原导出格式与值已检查；原查询操作日志/下载日期未提供'))
    write(ROOT/'registers/gbd_raw_audit.csv',raw_manifest)
    comparisons=[];candidates=[]
    for file in ['gbd_burden_legacy.csv','gbd_cases_legacy.csv']:
        a=read(ROOT/'candidate_inputs'/file);candidates.extend(a)
        check('unique_'+file,len({key(r) for r in a})==len(a),f'{len(a)} candidate rows')
        check('format_'+file,all(r['val'] and all(math.isfinite(float(r[x])) for x in ['val','lower','upper']) and float(r['lower'])<=float(r['val'])<=float(r['upper']) for r in a),'Finite values and ordered limits; scientific applicability separate')
        for r in a:
            source=r['source_file'];s=index.get(source,{}).get(key(r));verified_source=source if s else '';status='缺失';method='source export absent';sv=sl=su=''
            if s is None:
                for filename,ix in index.items():
                    alternate=ix.get(key(r))
                    if alternate and all(close(r[x],alternate[x]) for x in ['val','lower','upper']):
                        s=alternate;verified_source=filename;break
            if s:
                sv,sl,su=s['val'],s['lower'],s['upper'];status='已核验' if all(close(r[x],s[x]) for x in ['val','lower','upper']) else '部分核验';method='direct_same_export'
            elif source in raw and r['age_name']=='70+ years':
                age_ids={'19','20','30','31','32','235'}
                parts=[s for s in raw[source] if all(s[k]==r[k] for k in keycols if k!='age_id') and s['age_id'] in age_ids]
                if len(parts)==6:
                    sv=sum(float(s['val']) for s in parts);status='部分核验';method='70+ point sum only; interval not reconstructed'
            comparisons.append(dict(outcome_id=r['lancet_outcome_id'],cause_id=r['cause_id'],cause_name=r['cause_name'],measure_id=r['measure_id'],measure_name=r['measure_name'],year=r['year'],sex=r['sex_name'],age_id=r['age_id'],age_group=r['age_name'],candidate_val=r['val'],source_val=sv,candidate_lower=r['lower'],candidate_upper=r['upper'],source_lower=sl,source_upper=su,status=status,method=method,source_file=source,verified_source_file=verified_source,point_match='' if sv=='' else close(r['val'],sv)))
    write(ROOT/'registers/gbd_row_comparison.csv',comparisons)
    verified_keys={(r['source_file'],r['cause_id'],r['measure_id'],r['year'],r['sex'],r['age_id']):r for r in comparisons if r['status']=='已核验'}
    reusable=[]
    for r in candidates:
        proof=verified_keys.get((r['source_file'],r['cause_id'],r['measure_id'],r['year'],r['sex_name'],r['age_id']))
        if proof:reusable.append({**r,'verified_source_file':proof['verified_source_file'],'source_value_verification':'val/lower/upper matched raw export','new_study_admission':'pending study-definition and endpoint review in Work'})
    write(ROOT/'candidate_inputs/gbd_source_verified_subset.csv',reusable)
    check('reusable_gbd_subset',len(reusable)==12296,'Existing data retained as source-verified candidates, not automatic model admission')
    # Reconstruct exact replacement query requests from existing rows, never fabricate old UI history.
    queries=[]
    for source in sorted({r['source_file'] for r in candidates}):
        a=[r for r in candidates if r['source_file']==source]
        queries.append(dict(expected_file=source,version='GBD 2023',location='6:China',population='1:All Population',metric='1:Number',years='|'.join(sorted({r['year'] for r in a},key=int)),measure_ids='|'.join(sorted({r['measure_id']+':'+r['measure_name'] for r in a})),cause_ids='|'.join(sorted({r['cause_id']+':'+r['cause_name'] for r in a})),sex_ids='|'.join(sorted({r['sex_id']+':'+r['sex_name'] for r in a})),age_ids='|'.join(sorted({r['age_id']+':'+r['age_name'] for r in a})),query_role='derived replacement specification, NOT recovered original query log',status='部分核验' if source in raw else '缺失',attempts='all remote branch histories and both handoff ZIPs searched; public GBD app returns shell; no authenticated export',needed='original ZIP + citation + saved query/screenshot; or new GBD2023 same-definition export with timestamp and query',source_url='https://vizhub.healthdata.org/gbd-results/'))
    write(ROOT/'registers/gbd_query_requests.csv',queries)
    # 13 outcomes x 4 measures, with stroke components still visible in detailed audit.
    outcomes=sorted({r['outcome_id'] for r in read(h/'registers/rr_admission_register.csv')})
    mapping={r['outcome_id']:r for r in read(ROOT/'candidate_inputs/disease_mapping_legacy.csv') if r['record_type']=='outcome'}
    matrix=[]
    for outcome in outcomes:
        for measure,cn in [('Incidence','发病'),('Deaths','死亡'),('DALYs (Disability-Adjusted Life Years)','DALY'),('Prevalence','患病')]:
            a=[r for r in comparisons if r['outcome_id']==outcome and r['measure_name']==measure];recent=[r for r in a if 2018<=int(r['year'])<=2023]
            counts=Counter(r['status'] for r in recent)
            m=mapping.get(outcome,{})
            issues=m.get('key_issue','')
            if outcome=='stroke':issues+='; 卒中分IS/ICH/SAH三亚型；RR登记仅保留证据，不判断跨亚型/跨结局适用性'
            if outcome=='hypertension':issues+='; 无GBD本病四结局导出；22条旧高血压患病率候选为独立派生模块'
            if counts['部分核验']:issues+='; 70+均值与区间检查分开，缺draw'
            if not recent:issues+='; 2018—2023候选行不存在；原因未定，不能作零'
            matrix.append(dict(outcome_id=outcome,endpoint=cn,measure_name=measure,candidate_exists='是' if a else '否',candidate_rows=len(a),recent_2018_2023_rows=len(recent),recent_source_verified=counts['已核验'],recent_source_partial=counts['部分核验'],recent_source_missing=counts['缺失'],source_status='已核验' if recent and counts['已核验']==len(recent) else '部分核验' if recent and counts['已核验']+counts['部分核验'] else '缺失',definition_consistency='待核验',cause_names='|'.join(sorted({r['cause_name'] for r in a})),years='|'.join(sorted({r['year'] for r in a},key=int)),sex='|'.join(sorted({r['sex'] for r in a})),age='|'.join(sorted({r['age_group'] for r in a})),unit={'Incidence':'incident cases','Deaths':'deaths','Prevalence':'prevalent cases','DALYs (Disability-Adjusted Life Years)':'DALY years'}[measure]+'; Number metric',rr_admission='未决定，交 Work',issues=issues))
    write(ROOT/'registers/disease_endpoint_availability.csv',matrix)
    check('matrix_52',len(matrix)==52 and len({(r['outcome_id'],r['endpoint']) for r in matrix})==52,'13 x 4, existence only; no endpoint-risk decision')
    # Verify 18 coarse age-sex observations against the visually inspected Gao Table 2.
    expected={'Male':[(.275,.249,.301),(.266,.242,.290),(.220,.204,.236),(.208,.193,.223),(.208,.195,.220),(.272,.257,.288)],'Female':[(.253,.228,.277),(.201,.181,.222),(.156,.137,.175),(.154,.139,.170),(.172,.158,.186),(.295,.275,.314)],'Both':[(.264,.244,.283),(.234,.215,.253),(.188,.173,.204),(.181,.167,.196),(.190,.178,.203),(.284,.269,.299)]}
    observed=read(h/'registers/pa_observed_evidence.csv');pa=[]
    for r in observed:
        if r['source_id']=='PA-GAO2023' and r['age_group'] in ['18-29','30-39','40-49','50-59','60-69','70+']:
            vals=expected[r['sex']][['18-29','30-39','40-49','50-59','60-69','70+'].index(r['age_group'])]
            ok=all(close(r[k],v) for k,v in zip(['p_inactive','lower_95','upper_95'],vals));check('gao_'+r['sex']+'_'+r['age_group'],ok,'Visually inspected saved Table 2 image, percent/100')
            pa.append({**r,'verification_status':'已核验' if ok else '部分核验','verified_against':'raw/pa/Gao2018_Table2.jpg','admission':'未决定，20岁边界与2025变换待 Work'})
    write(ROOT/'candidate_inputs/pa_2018_published_verified.csv',pa)
    # Population: redownload hashes, extraction identity and all 1716 old aggregations.
    src=read(h/'registers/population_source_manifest.csv');pop=defaultdict(float);popchecks=[]
    for s in src:
        p=ROOT/'raw/population'/(Path(s['file']).stem+'.txt.gz');b=gzip.decompress(p.read_bytes()) if p.exists() else b''
        ok=hashlib.sha256(b).hexdigest()==s['source_sha256'];check('population_source_'+s['file'],ok,'Fresh fixed-commit download vs handoff full-source SHA256')
        a=list(csv.DictReader(io.StringIO(b.decode('utf-8-sig')),delimiter='\t'));china=[x for x in a if x['country_code']=='156']
        sex='Female' if 'popF' in s['file'] else 'Male';variant='Medium' if 'Med' in s['file'] else 'High' if 'High' in s['file'] else 'Low'
        for y in range(2025,2051):
            for x in china:
                age=int(x['age'])
                if age<20:continue
                group='70+' if age>=70 else f'{age//5*5}-{age//5*5+4}'
                pop[(variant,str(y),sex,group)]+=(float(x[str(y-1)])+float(x[str(y)]))*500
        popchecks.append(dict(file=s['file'],redownload_hash_match=ok,china_rows=len(china),time_definition='package t = end t = UN 1 Jan t+1',midyear_formula='(package t-1 + package t)/2 * 1000; linear approximation, not official July extraction',source_url=s['url']))
    write(ROOT/'registers/population_redownload.csv',popchecks)
    future=read(ROOT/'candidate_inputs/population_future_legacy.csv');check('population_1716',len(future)==1716 and all(abs(float(r['population'])-pop[(r['variant'],r['year'],r['sex'],r['age_group'])])<1 for r in future),'All layers agree within 1 person; confirms algorithm only')
    old=read(ROOT/'candidate_inputs/population_baseline_legacy.csv');den=[]
    for r in old:
        v=pop[('Medium','2025',r['sex'],r['age_group'])];o=float(r['baseline_population_2025'])
        den.append(dict(sex=r['sex'],age_group=r['age_group'],old_baseline=o,wpp_midyear_approx=v,difference=v-o,old_source='data/Public_model_inputs.xlsx::基线人口; upstream source unresolved',new_source='six fixed-commit raw WPP package files',status='部分核验'))
    write(ROOT/'registers/population_denominator_difference.csv',den)
    check('denominator_difference',close(sum(x['difference'] for x in den),50064034),'1,113,252,959 - 1,063,188,925 = 50,064,034; upstream reason remains unresolved')
    official=ROOT/'raw/population/WPP_age5_official.csv.gz'
    if official.exists():
        with gzip.open(official,'rt',encoding='utf-8-sig',newline='') as f:
            china=[r for r in csv.DictReader(f) if r['LocID']=='156' and 2024<=int(r['Time'])<=2050 and int(r['AgeGrpStart'])>=20]
        write(ROOT/'candidate_inputs/population_UN_official_china_2024_2050.csv',china)
        compare=[];agg=defaultdict(float)
        for r in china:
            age=int(r['AgeGrpStart']);age='70+' if age>=70 else r['AgeGrp']
            for sex,col in [('Male','PopMale'),('Female','PopFemale')]:agg[(r['Time'],sex,age)]+=float(r[col])*1000
        for r in den:
            v=agg[('2025',r['sex'],r['age_group'])]
            compare.append(dict(sex=r['sex'],age_group=r['age_group'],UN_official_July2025=v,package_midyear_approx=r['wpp_midyear_approx'],difference_official_minus_approx=v-r['wpp_midyear_approx'],old_baseline=r['old_baseline'],difference_official_minus_old=v-r['old_baseline']))
        write(ROOT/'registers/population_official_comparison.csv',compare)
        check('UN_official_2025_strata',len(compare)==22 and all(x['UN_official_July2025']>0 for x in compare),'Official UN full download, China156 Medium; no choice of denominator made')
    # Recheck the supplied RR numeric provenance against the newly saved source Table 1.
    supplement=next((ROOT/'handoff/supplement').glob('RR*.json'))
    rrjson=json.loads(supplement.read_text(encoding='utf-8'))
    rrsource=plain(ROOT/'raw/rr/Katzmarzyk2021.html'); rrrows=[]
    for r in rrjson['rr_component_audit']:
        old=' '.join(str(r[k]) for k in ['legacy_rr','legacy_lower','legacy_upper'])
        rrrows.append(dict(outcome_id=r['outcome_id'],component_id=r['component_id'],legacy_value=old,old_value_source_verified=r['numeric_match_to_Katzmarzyk_2021_Table_1'],source='raw/rr/Katzmarzyk2021.html#T1',primary_source_status='full text or metadata only; see download_attempts',new_admission='HOLD',caveat=r['caveat']))
    write(ROOT/'registers/rr_numeric_provenance.csv',rrrows)
    check('RR_table1_anchors',all(x in rrsource for x in ['1.32 (1.06 to 1.64)','1.28 (1.01 to 1.62)','1.19 (1.13 to 1.26)','1.17 (1.11 to 1.23)']),'Saved Katzmarzyk Table1 anchors; dementia mismatch retained')
    cost=read(h/'registers/medical_cost_evidence_register.csv');costrows=[]
    for o in outcomes:
        a=[x for x in cost if x['outcome_id']==o]
        costrows.append(dict(outcome_id=o,evidence_rows=len(a),legacy_cost_rows=sum(x['outcome_id']==o for x in read(ROOT/'candidate_inputs/cost_legacy.csv')),source_urls=' | '.join(x['source_url'] for x in a),old_value_provenance='部分核验' if a else '缺失',new_admission='HOLD',issues=' | '.join(x['notes'] for x in a) if a else 'No direct medical source/value verified; do not substitute other cancer or total social costs'))
    write(ROOT/'registers/cost_disease_availability.csv',costrows)
    # CSV shape, missing-value handling, PA complement and population ranges.
    for p in (ROOT/'candidate_inputs').glob('*.csv'):
        with p.open(encoding='utf-8-sig',newline='') as f:
            a=list(csv.reader(f))
        check('csv_shape_'+p.name,bool(a) and all(len(x)==len(a[0]) for x in a),f'{len(a)-1} rows; header/row widths')
    paold=read(ROOT/'candidate_inputs/pa_2025_legacy.csv')
    check('pa_2025_format',len(paold)==22 and len({(x['sex'],x['age_group']) for x in paold})==22 and all(0<=float(x['p_inactive'])<=1 and close(float(x['p_inactive'])+float(x['p_active']),1) for x in paold),'Legacy derived values only; source chain unresolved')
    check('population_format',all(float(x['population'])>0 and x['sex'] in ['Male','Female'] and 2025<=int(x['year'])<=2050 for x in future),'1716 source-preserving candidates')
    # Public cloud catalogue ETag verification; no article-level scientific admission implied.
    import xml.etree.ElementTree as ET
    cloud=[]
    for listing in (ROOT/'raw/pmc_cloud').glob('*/listing.xml'):
        doc=ET.parse(listing);ns={'s':'http://s3.amazonaws.com/doc/2006-03-01/'}
        for item in doc.findall('s:Contents',ns):
            keyname=item.findtext('s:Key',namespaces=ns);p=listing.parent/keyname.split('/')[-1]
            if not p.exists():continue
            etag=item.findtext('s:ETag',namespaces=ns).strip('"');md5=hashlib.md5(p.read_bytes()).hexdigest()
            cloud.append(dict(file=p.relative_to(ROOT).as_posix(),catalogue_key=keyname,source_url='https://pmc-oa-opendata.s3.amazonaws.com/'+keyname,md5=md5,catalogue_etag=etag,etag_match=md5==etag,sha256=digest(p)))
    write(ROOT/'checks/pmc_catalogue_integrity.csv',cloud)
    check('pmc_cloud_catalogue',bool(cloud) and all(x['etag_match'] for x in cloud),f'{len(cloud)} actual files vs public catalogue ETag')
    # Every data file is indexed, including missing source names; source status never means model admission.
    attempts=read(ROOT/'registers/download_attempts.csv');by_path={r['path']:r for r in attempts if r['path']}
    registry=[]
    for p in sorted(ROOT.rglob('*')):
        if not p.is_file() or any(x in p.parts for x in ['__pycache__','checks','extracted_text']) or p.name in ['source_registry.csv','file_manifest.csv']:continue
        rel=p.relative_to(ROOT).as_posix();a=by_path.get(rel,{})
        if not a and rel.startswith('raw/pmc_cloud/'):
            a={'url':'https://pmc-oa-opendata.s3.amazonaws.com/'+p.parent.name+'.1/'+p.name,'notes':'Public PMC cloud dataset; version/citation/license in sibling JSON; byte check separate from scientific suitability'}
        group='population' if any(x in rel for x in ['wpp','population']) else 'pa' if any(x in rel for x in ['pa_','/pa/']) else 'gbd' if 'gbd' in rel.lower() else 'rr' if '/rr' in rel.lower() else 'cost' if 'cost' in rel else 'mixed'
        status=a.get('status','部分核验')
        if rel.startswith(('scripts/','reports/')):status='不适用'
        registry.append(dict(file=rel,source_url=a.get('url',''),original_file=a.get('url','') or ('handoff packages; see registers/handoff_packages.csv' if rel.startswith('handoff/') else 'data/Public_model_inputs.xlsx; read-only extraction' if rel.startswith('candidate_inputs/') and 'verified' not in rel else 'derived audit; see scripts/audit_round1.py and handoff registers'),obtained_date=DATE,original_download_date='',version='WPP2024 fixed commit 2da7768' if group=='population' else 'GBD2023 / handoff 20261111' if group=='gbd' else 'published article / handoff20261111 / round1 as applicable',population='China' if group in ['population','pa','gbd','cost'] else 'source-study populations; see evidence registers',age='20+ candidates; 18+ survey; source-age strata preserved' if group in ['population','pa','gbd'] else 'source-dependent; not assumed',sex='Male/Female/Both as source; female-specific cancer restrictions pending',years='2018 observed / 2025 derived' if group=='pa' else '2024-2050 extracted; full projection to2100' if group=='population' else '2010-2023 candidates; original exports may include1990+' if group=='gbd' else 'source-specific; evidence register',unit='proportion' if group=='pa' else 'persons (raw thousands)' if group=='population' else 'Number; cases/deaths/persons/DALY-years' if group=='gbd' else 'risk ratio/HR/OR or currency per source; see evidence registers',sha256=digest(p),status=status,model_admission='未决定',notes=a.get('notes','Metadata describes file scope; row-level definitions and unknowns remain explicit in supplied evidence registers')))
    for q in queries:
        if q['status']=='缺失':registry.append(dict.fromkeys(registry[0],''));registry[-1].update(file=q['expected_file'],source_url=q['source_url'],obtained_date='',version='GBD2023',population='China',age=q['age_ids'],sex=q['sex_ids'],years=q['years'],unit='Number',status='缺失',model_admission='未决定',notes=q['needed'])
    # Narrow file-level metadata where known; unknown source study fields remain explicit.
    for r in registry:
        f=r['file']
        if f.startswith('raw/population/pop'):
            r.update(population='All countries in fixed PPgp WPP2024 file; China code156 extracted separately',age='single ages0-99 and100+',sex='Female' if '/popF' in f else 'Male',years='2024-2100',unit='thousand persons',version='PPgp/wpp2024 fixed commit2da7768ae64fc74105d3f9e98f9a74d37b62f99a')
        if f.endswith('WPP_age5_official.csv.gz'):
            r.update(population='UN locations including China156',age='5-year ages0-4 through100+',sex='Male/Female/Total',years='1950-2100',unit='thousand persons',version='UN WPP2024 Medium; 2026-11-12 download')
        if f.endswith('pa_2018_published_verified.csv') or f in ['raw/pa/Gao2018.html','raw/pa/Gao2018_Table2.jpg']:
            r.update(population='China CCDRFS2018 residents18+; analysis n183769',age='18-29|30-39|40-49|50-59|60-69|70+',sex='Male/Female/Both',years='2018',unit='proportion (CSV); percent with95%CI (original Table2)',source_url='https://html.rhhz.net/zhlxbx/20230803.htm',version='Gao2023 published Table2')
        if f.startswith('candidate_inputs/') and 'legacy' in f:
            r['notes']+='; Old candidate only; source/upstream uncertainty not resolved by byte-preserving export'
    write(ROOT/'registers/source_registry.csv',registry)
    # Fresh manifest includes original source snapshots; excludes itself and changing check outputs.
    manifest=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=digest(p)) for p in sorted(ROOT.rglob('*')) if p.is_file() and not any(x in p.parts for x in ['checks','__pycache__','extracted_text']) and p.name!='file_manifest.csv']
    write(ROOT/'registers/file_manifest.csv',manifest)
    check('manifest_readback',all(digest(ROOT/r['path'])==r['sha256'] for r in manifest),f'{len(manifest)} files hashed')
    check('all_rr_hold',all(r['new_admission']=='HOLD' and r['approved_for_model']=='False' for r in read(h/'registers/rr_admission_register.csv')),'No risk endpoint admission changed')
    check('no_new_missing_as_zero',all(r['source_val']!='0' for r in comparisons if r['status']=='缺失'),'Missing source values remain blank')
    result=dict(date=DATE,passed=all(r['passed'] for r in checks),checks=checks,gbd_status_counts=dict(Counter(r['status'] for r in comparisons)),model_run=False,model_ready=False)
    (ROOT/'checks/validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='checks'},ensure_ascii=False));print('checks',len(checks),'failures',[r for r in checks if not r['passed']])
    if not result['passed']:raise SystemExit(1)

if __name__=='__main__':main()
