"""Use the documented, anonymous PMC cloud dataset; never handles browser credentials."""
import csv,hashlib,json,urllib.request,urllib.parse,xml.etree.ElementTree as E,logging
from pathlib import Path
from pypdf import PdfReader
from collect_sources import ROOT,save_csv

BASE='https://pmc-oa-opendata.s3.amazonaws.com/'
logging.getLogger('pypdf').setLevel(logging.ERROR)
IDS=['PMC4979358','PMC8478970','PMC7048166','PMC10203198','PMC9278468','PMC9528634','PMC5410077','PMC6468884']
def get(url):
    with urllib.request.urlopen(url,timeout=30) as r:return r.read()
def main():
    out=[]
    for id in IDS:
        folder=ROOT/'raw/pmc_cloud'/id;folder.mkdir(parents=True,exist_ok=True)
        url=BASE+'?list-type=2&prefix='+id+'.&max-keys=100'
        try:
            b=get(url);(folder/'listing.xml').write_bytes(b)
            listing=E.fromstring(b);ns={'s':'http://s3.amazonaws.com/doc/2006-03-01/'}
            keys=[x.findtext('s:Key',namespaces=ns) for x in listing.findall('s:Contents',ns)]
            for key in keys:
                if not key.lower().endswith(('.json','.xml','.txt','.pdf','.docx','.xlsx','.csv')):continue
                u=BASE+urllib.parse.quote(key);p=folder/key.split('/')[-1]
                try:
                    data=get(u);p.write_bytes(data);note='Public PMC cloud dataset; fixed version key; original bytes'
                    if p.suffix.lower()=='.pdf':
                        if not data.startswith(b'%PDF'):raise ValueError('Not PDF')
                        doc=PdfReader(p);text='\n'.join(x.extract_text() or '' for x in doc.pages)
                        textp=ROOT/'reports/extracted_text'/(id+'_'+p.stem+'.txt');textp.parent.mkdir(exist_ok=True);textp.write_text(text,encoding='utf-8')
                        note+=f'; PDF signature/pages/text checked: {len(doc.pages)} pages, {len(text)} characters'
                    out.append(dict(source_id=id+'_'+p.name,url=u,obtained_date='2026-11-12',path=p.relative_to(ROOT).as_posix(),bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),http_status=200,status='部分核验',notes=note,final_url=u))
                except Exception as e:out.append(dict(source_id=id+'_'+key,url=u,obtained_date='2026-11-12',path='',bytes='',sha256='',http_status='',status='缺失',notes=str(e),final_url=''))
            print(id,len(keys),'listed',flush=True)
        except Exception as e:
            out.append(dict(source_id=id,url=url,obtained_date='2026-11-12',path='',bytes='',sha256='',http_status='',status='缺失',notes=str(e),final_url=''));print(id,str(e),flush=True)
    prior=list(csv.DictReader((ROOT/'registers/download_attempts.csv').open(encoding='utf-8-sig')))
    prior=[r for r in prior if not r['source_id'].startswith(tuple(IDS))]
    save_csv(ROOT/'registers/download_attempts.csv',prior+out)
    save_csv(ROOT/'registers/pmc_cloud_files.csv',out)

if __name__=='__main__':main()
