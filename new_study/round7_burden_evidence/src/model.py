import csv,hashlib,io,json,math,zipfile
from pathlib import Path
import numpy as np

HERE=Path(__file__).resolve().parents[1]
ROOT=HERE.parents[1]
AGES=[f'{a}-{a+4}' for a in range(20,95,5)]+['95+']
CAUSES={'Ischemic heart disease':'IHD','Ischemic stroke':'IS'}
MEASURES={'Incidence':'Incidence','Deaths':'Deaths','Prevalence':'Prevalence','YLDs (Years Lived with Disability)':'YLD','YLLs (Years of Life Lost)':'YLL','DALYs (Disability-Adjusted Life Years)':'DALY'}
class Blocked(ValueError):pass
def read(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def write(path,rows,fields=None):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields or list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
def jwrite(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8',newline='\n')
def config():return json.loads((HERE/'config.json').read_text('utf-8'))
def population():
    from collections import defaultdict
    c=config();pa={(r['sex'],r['age_group']):r for r in read(ROOT/c['exposure'])};groups=defaultdict(list)
    if len(pa)!=34:raise Blocked('exposure dimensions')
    for r in read(ROOT/c['population']):
        age='95+' if r['age_group'] in ['95-99','100+'] else r['age_group'];s=pa[(r['sex'],r['age_group'])]
        groups[(int(r['year']),r['sex'],age)].append((int(r['population_persons']),s))
    result=[]
    for (year,sex,age),parts in sorted(groups.items()):
        n=sum(x[0] for x in parts);p=sum(x[0]*float(x[1]['p_inactive']) for x in parts)/n
        if len({x[1]['shared_parameter_id'] for x in parts})!=1:raise Blocked('shared source parameter')
        result.append(dict(year=year,sex=sex,age=age,population=n,p_inactive=p,shared_parameter_id=parts[0][1]['shared_parameter_id'],lower_95=float(parts[0][1]['lower_95']),upper_95=float(parts[0][1]['upper_95'])))
    if len(result)!=832:raise Blocked('population grid')
    return result
def gbd():
    rates={};records=[]
    for relative in config()['gbd']:
        path=ROOT/relative
        with zipfile.ZipFile(path) as z:
            for member in z.namelist():
                if not member.endswith('.csv'):continue
                for r in csv.DictReader(io.TextIOWrapper(z.open(member),encoding='utf-8-sig')):
                    age=r['age_name'].removesuffix(' years');measure=MEASURES.get(r['measure_name']);d=CAUSES.get(r['cause_name'])
                    if r['year']!='2023' or r['metric_name']!='Rate' or age not in AGES or not d or not measure:continue
                    if r['sex_name'] not in ['Male','Female'] or r['location_name']!='China' or r.get('population_group_name','All Population')!='All Population':raise Blocked('GBD scope')
                    key=(d,measure,r['sex_name'],age)
                    if key in rates:raise Blocked('duplicate GBD key')
                    v,lo,hi=[float(r[k]) for k in ['val','lower','upper']]
                    if not 0<=lo<=v<=hi:raise Blocked('GBD interval')
                    rates[key]=(v,lo,hi)
                    records.append(dict(disease=d,endpoint=measure,sex=r['sex_name'],age=age,rate_per_100000=v,lower=lo,upper=hi,year=2023,source=relative,source_member=member,source_sha256=sha(path)))
    if len(rates)!=384:raise Blocked('GBD disease x endpoint x sex x age grid incomplete')
    return rates,records
def rr(disease,x,method='log_linear'):
    r=sorted((v for v in read(HERE/'inputs/kyu_published_grid.csv') if v['disease']==disease),key=lambda v:int(v['dose']))
    if not r:raise Blocked('RR disease not registered')
    dose=np.asarray([float(v['dose']) for v in r]);values=np.asarray([float(v['estimate']) for v in r]);x=np.asarray(x,dtype=float)
    if np.any(~np.isfinite(x)) or np.any(x<0) or np.any(x>dose[-1]):raise Blocked('dose outside published support; tail rule not admitted')
    if method=='log_linear':return np.exp(np.interp(x,dose,np.log(values)))
    if method=='linear':return np.interp(x,dose,values)
    raise Blocked('interpolation method')
def transformed(x,scenario):
    x=np.asarray(x,dtype=float)
    if scenario=='B0':return x
    if scenario=='R1':return np.maximum(x,600)
    if scenario=='R2':return 1.2*x
    if scenario=='R3':return np.where(x<600,600,1.2*x)
    raise Blocked('P15 requires weight splitting, not deterministic transformation')
def alpha(year):return min(.15,max(0.,.03*(year-2025)))
def pif_atoms(disease,doses,weights,scenario,year=2030):
    doses=np.asarray(doses,dtype=float);weights=np.asarray(weights,dtype=float)
    if np.any(weights<0) or not math.isclose(float(weights.sum()),1.,abs_tol=1e-10):raise Blocked('weights must sum to one')
    baseline=rr(disease,doses);after=rr(disease,transformed(doses,'R1' if scenario=='P15' else scenario))
    if scenario=='P15':after=baseline+alpha(year)*(after-baseline)
    return float(np.dot(weights,baseline-after)/np.dot(weights,baseline))
def admission(disease,endpoint,mode):
    rows=read(HERE/'registers/disease_endpoint_evidence_matrix.csv')
    row=next((r for r in rows if r['outcome_id']==disease and r['endpoint']==endpoint),None)
    if not row:raise Blocked('unregistered disease/endpoint')
    if row['source_status']!='VERIFIED_2023' or row['exposure_match']!='BINARY_MARGIN_ONLY':raise Blocked('source/exposure mismatch')
    if mode not in row['allowed_uses'].split('|'):raise Blocked('endpoint or purpose not admitted')
    return row
def bounds(disease,p,mode='SUPPORT_FREE_CONTINUOUS'):
    """Identification envelopes, NOT estimates, confidence intervals or posterior UIs.

    Continuous: A=E[r|inactive] in [r(600),1], B=E[r|active]>0.
    F=p*(A-r600)/(p*A+(1-p)*B) in [0,1-r600]. No tail value is evaluated.
    Categorical: changes to LOW CATEGORY (not exactly 600); unknown active category weights.
    """
    if not 0<=p<=1:raise Blocked('probability')
    if p==0:return 0.,0.
    if mode=='SUPPORT_FREE_CONTINUOUS':return 0.,1.-float(rr(disease,[600])[0])
    if mode=='CATEGORY_TARGET_SENSITIVITY':
        rows=read(HERE/'inputs/kyu_category_rr.csv');v=[float(r['rr_vs_inactive']) for r in rows if r['disease']==disease]
        if len(v)!=4:raise Blocked('categorical RR')
        return p*(1-v[1])/(p+(1-p)*max(v[1:])),p*(1-v[1])/(p+(1-p)*min(v[1:]))
    raise Blocked('unknown bound mode')
