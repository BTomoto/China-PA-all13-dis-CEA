import csv,sys,gzip,hashlib,json,urllib.request,urllib.parse
from pathlib import Path
from collect_sources import ROOT,fetch,save_csv

rows=list(csv.DictReader((ROOT/'registers/download_attempts.csv').open(encoding='utf-8-sig')))
extras=[('Pubmed_records','https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id=28348016,29690792,36171041,19824187,29433981,31877085&retmode=xml','metadata'),('Crossref_Matthews','https://api.crossref.org/works/10.1200/JCO.19.02407','metadata'),('WPP_age5_official','https://population.un.org/wpp/assets/Excel%20Files/1_Indicator%20(Standard)/CSV_FILES/WPP2024_PopulationByAge5GroupSex_Medium.csv.gz','population')]
for item in extras:
 r=fetch(item)
 if r['path']:
  p=ROOT/r['path'];b=p.read_bytes()
  if b[:2]==b'\x1f\x8b':
   q=p.with_suffix('.csv.gz');p.rename(q);r['path']=q.relative_to(ROOT).as_posix()
  elif b.lstrip().startswith(b'<?xml'):
   q=p.with_suffix('.xml');p.rename(q);r['path']=q.relative_to(ROOT).as_posix()
  elif b.lstrip().startswith(b'{'):
   q=p.with_suffix('.json');p.rename(q);r['path']=q.relative_to(ROOT).as_posix()
 rows.append(r);print(item[0],r['bytes'],r['notes'],flush=True)
# Preserve exactly the downloaded bytes in deterministic gzip, record both hashes.
for r in rows:
 if r['source_id'].startswith('pop') and r['path'].endswith('.txt'):
    p=ROOT/r['path'];q=p.with_suffix('.txt.gz')
    b=p.read_bytes() if p.exists() else gzip.decompress(q.read_bytes())
    q.write_bytes(gzip.compress(b,mtime=0))
    if p.exists():p.unlink()
  r['path']=q.relative_to(ROOT).as_posix();r['notes']='Lossless gzip; sha256/bytes refer to original uncompressed download; archive hash in file_manifest.csv'
 # HTTP 200 is not proof of useful source content.
 if r['path']:
  p=ROOT/r['path']
  if p.suffix=='.html':
   b=p.read_bytes()
   if len(b)<10000 and r['source_id'] not in ['GBD_results','WPP_home']:
    r['status']='缺失';r['notes']='HTTP 200 returned interstitial, not article/PDF; kept as diagnostic only'
   if r['source_id']=='GBD_results':r['notes']='Application HTML shell only; no GBD data export or query state recovered'
 for key in ['final_url']:r.setdefault(key,'')
save_csv(ROOT/'registers/download_attempts.csv',rows)
