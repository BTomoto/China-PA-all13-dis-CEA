from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import urllib.request,hashlib,json
R=Path(__file__).resolve().parent
items={
'China_CHNS_CVD_projection.html':'https://pmc.ncbi.nlm.nih.gov/articles/PMC5850940/',
'China_CHNS_supplement.pdf':'https://pmc-oa-opendata.s3.amazonaws.com/PMC5850940.1/NIHMS800634-supplement-supplement_1.pdf',
'Brazil_CRA_Kyu_mortality.html':'https://oup.silverchair-cdn.com/article-minimal/5139677',
'Morocco_CRA_Kyu.html':'https://www.cdc.gov/pcd/issues/2026/25_0352.htm',
'NBS_2025_wages.html':'https://www.stats.gov.cn/sj/zxfb/202605/t20260515_1963707.html',
'China_ACS_first_year_abstract.html':'https://pubmed.ncbi.nlm.nih.gov/30770126/',
'RAND_productivity_primary.xml':'https://www.ebi.ac.uk/europepmc/webservices/rest/PMC7719903/fullTextXML',
'China_T2D_incident_complications.html':'https://link.springer.com/article/10.1007/s13300-020-00967-y',
'CHNS_supplement_direct.pdf':'https://pmc.ncbi.nlm.nih.gov/articles/instance/5850940/bin/NIHMS800634-supplement-supplement_1.pdf',
'Schuch2018_abstract.json':'https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=EXT_ID:29690792%20AND%20SRC:MED&format=json&resultType=core',
'Liu2017_abstract.json':'https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=EXT_ID:28348016%20AND%20SRC:MED&format=json&resultType=core',
'Carlsson2007_abstract.json':'https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=EXT_ID:17096113%20AND%20SRC:MED&format=json&resultType=core',
'ACS2019_abstract.json':'https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=EXT_ID:30770126%20AND%20SRC:MED&format=json&resultType=core',
}
def fetch(item):
 name,url=item;p=R/'raw'/name
 if p.exists():return dict(file=name,url=url,status='PRESENT_NOT_OVERWRITTEN',sha256=hashlib.sha256(p.read_bytes()).hexdigest())
 try:
  with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=45) as f:data=f.read(12000000)
  if name.endswith('.pdf') and not data.startswith(b'%PDF'):raise ValueError('NOT_PDF')
  if name.endswith('.xml') and b'<article' not in data[:10000]:raise ValueError('NOT_ARTICLE_XML')
  if b'recaptcha' in data[:12000].lower() or len(data)<(100 if name.endswith('.json') else 5000):raise ValueError('ACCESS_CHALLENGE_OR_SHORT_RESPONSE')
  if name.endswith('.json') and not json.loads(data).get('resultList',{}).get('result'):raise ValueError('NO_BIBLIOGRAPHIC_RESULT')
  p.write_bytes(data)
  return dict(file=name,url=url,status='DOWNLOADED',sha256=hashlib.sha256(data).hexdigest(),bytes=len(data))
 except Exception as e:return dict(file=name,url=url,status='DOWNLOAD_FAILED',error=str(e))
with ThreadPoolExecutor(max_workers=7) as ex:rows=list(ex.map(fetch,items.items()))
(R/'logs/additional_evidence_acquisition.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
checks=[]
for file,tokens in {'China_CHNS_CVD_projection.html':['CHNS','3999'],'Brazil_CRA_Kyu_mortality.html':['Kyu','Relative risk estimates'],'NBS_2025_wages.html':['129441','71590'],'China_ACS_first_year_abstract.html':['20771','22877'],'China_T2D_incident_complications.html':['114,847','complication']}.items():
 p=R/'raw'/file
 valid=p.exists() and all(s in p.read_text('utf-8',errors='replace') for s in tokens)
 checks.append(dict(file=file,status='CONTENT_VERIFIED' if valid else 'NOT_VERIFIED_OR_CHALLENGE',required_content_tokens=tokens))
(R/'logs/download_content_checks.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(rows,ensure_ascii=False))
