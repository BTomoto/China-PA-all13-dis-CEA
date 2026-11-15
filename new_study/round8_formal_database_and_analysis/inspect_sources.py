from pathlib import Path
import zipfile,xml.etree.ElementTree as E,json
import pandas as pd
N={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
def workbook(path):
 with zipfile.ZipFile(path) as z:
  ss=[]
  if 'xl/sharedStrings.xml' in z.namelist():
   ss=[''.join(x.itertext()) for x in E.fromstring(z.read('xl/sharedStrings.xml'))]
  rel={r.attrib['Id']:r.attrib['Target'] for r in E.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
  out={}
  for s in E.fromstring(z.read('xl/workbook.xml')).find('m:sheets',N):
   target=rel[s.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']]
   member=target.lstrip('/') if target.startswith('/') else 'xl/'+target
   rows=[]
   for row in E.fromstring(z.read(member)).findall('.//m:sheetData/m:row',N):
    cells={}
    for c in row:
     col=0
     for ch in c.attrib['r']:
      if ch.isalpha():col=col*26+ord(ch.upper())-64
     v=c.find('m:v',N); val=v.text if v is not None else ''
     if c.attrib.get('t')=='s':val=ss[int(val)]
     elif c.attrib.get('t')=='inlineStr':val=''.join(c.find('m:is',N).itertext())
     elif val and c.attrib.get('t') not in ['str','e','b']:
      try:val=float(val)
      except ValueError:pass
     cells[col-1]=val
    if cells:rows.append([cells.get(i,'') for i in range(max(cells)+1)])
   width=max(map(len,rows)); rows=[r+['']*(width-len(r)) for r in rows]
   out[s.attrib['name']]=pd.DataFrame(rows[1:],columns=rows[0])
 return out
if __name__=='__main__':
 for p in [Path('data/Public_model_inputs.xlsx'),Path('new_study/round1_20261112/handoff/continuation/data/New_study_inputs.xlsx')]:
  t=workbook(p); print(str(p)); print([(k,v.shape) for k,v in t.items()])
 b=Path('new_study/round1_20261112/candidate_inputs')
 d=pd.read_csv(b/'gbd_cases_legacy.csv');print('2023',d[d.year.eq(2023)].groupby(['cause_id','cause_name','measure_name']).size().to_string())
 f=pd.read_csv(b/'population_future_legacy.csv');print('pop variants',f.groupby('variant').agg({'year':['min','max'],'age_group':'nunique'}).to_string())
