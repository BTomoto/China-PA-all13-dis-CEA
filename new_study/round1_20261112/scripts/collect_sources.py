"""Archive lawful public sources; never executes research models."""
import csv, hashlib, json, re, shutil, time, urllib.request, urllib.parse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT.parents[2]
RAW = ROOT / 'raw'
DATE = '2026-11-12'

def save_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows: return
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        w=csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

def fetch(item):
    id,url,group=item
    p=RAW/group/(id + ('.txt' if 'raw.githubusercontent' in url else '.jpg' if url.endswith('.jpg') else '.html'))
    p.parent.mkdir(parents=True,exist_ok=True)
    rec=dict(source_id=id,url=url,obtained_date=DATE,path='',bytes='',sha256='',http_status='',status='缺失',notes='')
    try:
        req=urllib.request.Request(url,headers={'User-Agent':'China-PA-source-audit/1.0'})
        with urllib.request.urlopen(req,timeout=40) as r: b=r.read(); rec['http_status']=r.status; rec['final_url']=r.url
        if b'captcha' in b[:10000].lower() or b'Checking your browser' in b:
            rec['notes']='Security challenge; not archived as full text';return rec
        p.write_bytes(b);rec.update(path=str(p.relative_to(ROOT)).replace('\\','/'),bytes=len(b),sha256=hashlib.sha256(b).hexdigest(),status='部分核验',notes='HTTP bytes archived; content verification recorded separately')
    except Exception as e:rec['notes']=str(e)
    return rec

def main():
    sources=[('Gao2018','https://html.rhhz.net/zhlxbx/20230803.htm','pa'),('Gao2018_Table2','https://html.rhhz.net/zhlxbx/PIC/zhlxbxzz-44-8-1190-T2.jpg','pa'),('Zhang2023','https://pmc.ncbi.nlm.nih.gov/articles/PMC10351178/','pa'),('Katzmarzyk2021','https://pmc.ncbi.nlm.nih.gov/articles/PMC8478970/','rr'),('Kyu2016','https://pmc.ncbi.nlm.nih.gov/articles/PMC4979358/','rr'),('Pearce2022','https://pmc.ncbi.nlm.nih.gov/articles/PMC9008579/','rr'),('Kivimaki2019','https://www.bmj.com/content/365/bmj.l1495','rr'),('Liu2017','https://pubmed.ncbi.nlm.nih.gov/28348016/','rr'),('Schuch2018','https://pubmed.ncbi.nlm.nih.gov/29690792/','rr'),('Matthews2020','https://ascopubs.org/doi/full/10.1200/JCO.19.02407','rr'),('IHD_cost','https://pmc.ncbi.nlm.nih.gov/articles/PMC10203198/','cost'),('Stroke_cost','https://pmc.ncbi.nlm.nih.gov/articles/PMC9278468/','cost'),('CRC_cost','https://pmc.ncbi.nlm.nih.gov/articles/PMC5410077/','cost'),('Depression_cost','https://pubmed.ncbi.nlm.nih.gov/36171041/','cost'),('T2D_cost_old','https://pubmed.ncbi.nlm.nih.gov/19824187/','cost'),('AD_cost','https://pubmed.ncbi.nlm.nih.gov/29433981/','cost'),('T2D_cost_2019','https://www.frontiersin.org/journals/public-health/articles/10.3389/fpubh.2023.1062903/full','cost'),('WPP_package','https://raw.githubusercontent.com/PPgp/wpp2024/2da7768ae64fc74105d3f9e98f9a74d37b62f99a/man/wpp2024-package.Rd','population'),('WPP_home','https://population.un.org/wpp/','population'),('GBD_results','https://vizhub.healthdata.org/gbd-results/','gbd')]
    base='https://raw.githubusercontent.com/PPgp/wpp2024/2da7768ae64fc74105d3f9e98f9a74d37b62f99a/data-raw/'
    sources += [(f'pop{s}proj{v}',base+f'pop{s}proj{v}.txt','population') for s in ['M','F'] for v in ['Med','Low','High']]
    with ThreadPoolExecutor(max_workers=3) as ex: records=list(ex.map(fetch,sources))
    # Fixed schema even for failed requests.
    for r in records:r.setdefault('final_url','')
    save_csv(ROOT/'registers/download_attempts.csv',records)
    print(json.dumps([{'id':r['source_id'],'bytes':r['bytes'],'status':r['status'],'error':r['notes'] if not r['path'] else ''} for r in records],ensure_ascii=False))

if __name__=='__main__':main()
