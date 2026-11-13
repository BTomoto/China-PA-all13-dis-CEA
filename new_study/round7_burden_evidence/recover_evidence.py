"""Read metadata and aggregate source documents only; never read individual records."""
import argparse,csv,hashlib,io,json,urllib.request,zipfile,time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def csvout(p,rows):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
def run(root):
    out=root/'new_study/round7_burden_evidence';out.mkdir(parents=True,exist_ok=True)
    rows=[];seen=set();zips=[]
    for directory in [root,root.parent/'Data',Path('C:/Users/Windows11/Documents/ChatGPT/身体活动不足分析/research_repo'),Path('C:/Users/Windows11/Downloads')]:
        if not directory.exists():continue
        for p in directory.rglob('*'):
            if not p.is_file() or any(s in {'.git','.venv','node_modules','.runtime','round7_burden_evidence'} for s in p.parts):continue
            ext=p.suffix.lower();name=p.name.lower()
            candidate=ext in {'.xlsx','.dta','.sav','.rds','.rdata','.parquet'} or (ext=='.csv' and any(t in name for t in ['activity','身体活动','pa_binary','exposure','physical','gpaq','ipaq'])) or (ext=='.zip' and any(t in name for t in ['continuation','补充','复核','ihme']))
            if not candidate or str(p) in seen:continue
            seen.add(str(p));h=digest(p);meta='';domain='UNKNOWN';scope='NOT_CONFIRMED';auth='METADATA_ONLY_NO_RECORD_ACCESS'
            if ext=='.xlsx':
                with zipfile.ZipFile(p) as z:
                    meta=z.read('xl/workbook.xml').decode()[:20000]
                scope='AGGREGATE_WORKBOOK_CANDIDATE';auth='PREEXISTING_PROJECT_AGGREGATE_USE; no individual rows inspected'
            elif ext=='.csv':
                with p.open(encoding='utf-8-sig') as f:meta=f.readline().strip()
                auth='HEADER_ONLY_NO_RECORD_ACCESS'
            elif ext=='.zip':
                with zipfile.ZipFile(p) as z:
                    names=z.namelist();meta=json.dumps(names,ensure_ascii=False)
                    if 'ihme' in name:
                        zips.append(p)
                        for n in names:
                            if n.lower().endswith('.csv'):
                                with z.open(n) as f:header=f.readline().decode('utf-8-sig')
                                meta+='\nCSV_HEADER:'+header
                    auth='ZIP_MEMBER_NAMES_AND_GBD_AGGREGATE_HEADERS_ONLY'
            rows.append(dict(candidate_id=f'EX-{len(rows)+1:04}',path=str(p),sha256=h,size_bytes=p.stat().st_size,source='existing project/registered handoff/downloads',year='UNRESOLVED',sample='AGGREGATE_OR_UNRESOLVED',population='UNRESOLVED',national_representativeness=scope,variables_or_members=meta,weights='NOT_ESTABLISHED',activity_domain=domain,authorization=auth,record_access='NO_INDIVIDUAL_RECORDS_READ'))
    csvout(out/'registers/exposure_candidate_inventory.csv',rows)
    # GBD records are public aggregate exports, not individual observations.
    g=[]
    for p in zips:
        with zipfile.ZipFile(p) as z:
            for n in z.namelist():
                if not n.lower().endswith('.csv'):continue
                table=csv.DictReader(io.TextIOWrapper(z.open(n),encoding='utf-8-sig'));fields=table.fieldnames;dims={k:set() for k in fields if k.endswith('_name') or k in ['rei_id','cause_id','year']};nr=0
                for r in table:
                    nr+=1
                    for k in dims:dims[k].add(r[k])
                g.append(dict(path=str(p),sha256=digest(p),member=n,rows=nr,contains_risk_dimension=any(k in fields for k in ['rei_id','rei_name','risk_name']),dimensions={k:sorted(v) for k,v in dims.items()}))
    (out/'logs').mkdir(exist_ok=True)
    (out/'logs/gbd_zip_inventory.json').write_text(json.dumps(g,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    urls={
      'GBD2021_low_PA_methods.pdf':'https://www.healthdata.org/sites/default/files/methods_appendices/2021/lojustin_activity_writeup_gbd2020_AC_updated0131.pdf',
      'China_first_year_IS_CNSR3.xml':'https://www.ebi.ac.uk/europepmc/webservices/rest/PMC11420908/fullTextXML',
      'China_CHNS_CVD_projection.xml':'https://www.ebi.ac.uk/europepmc/webservices/rest/PMC5850940/fullTextXML',
      'China_CKB_PA_phenome.xml':'https://www.ebi.ac.uk/europepmc/webservices/rest/PMC12277735/fullTextXML',
      'GBD2019_lowPA_external_reference.xml':'https://www.ebi.ac.uk/europepmc/webservices/rest/PMC10286621/fullTextXML',
    }
    raw=out/'raw';raw.mkdir(exist_ok=True)
    def fetch(item):
        name,url=item;p=raw/name;start=time.time()
        if p.exists():return dict(file=name,url=url,status='PRESENT_NOT_OVERWRITTEN',sha256=digest(p),bytes=p.stat().st_size)
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 (public academic evidence verification)'})
            with urllib.request.urlopen(req,timeout=55) as f:data=f.read(15000000)
            if not (data.startswith(b'%PDF') if name.endswith('.pdf') else b'<article' in data[:10000]):raise ValueError('not expected source format')
            p.write_bytes(data)
            return dict(file=name,url=url,status='DOWNLOADED',sha256=digest(p),bytes=len(data),seconds=round(time.time()-start,2))
        except Exception as e:return dict(file=name,url=url,status='DOWNLOAD_FAILED',error=str(e),seconds=round(time.time()-start,2))
    with ThreadPoolExecutor(max_workers=5) as ex:downloads=list(ex.map(fetch,urls.items()))
    (out/'logs/evidence_acquisition.json').write_text(json.dumps(downloads,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(inventory_candidates=len(rows),gbd_exports=len(g),risk_exports=sum(x['contains_risk_dimension'] for x in g),downloads=downloads),ensure_ascii=False))
if __name__=='__main__':run(Path(argparse.ArgumentParser().parse_known_args()[1][0]).resolve())
