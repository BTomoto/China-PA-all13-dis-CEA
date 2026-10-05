
from pathlib import Path
import hashlib, json
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent.parent

def schema():
    return json.loads((ROOT/'data/input_schema.json').read_text(encoding='utf-8'))

def _restore(frame, spec):
    if list(frame.columns)!=spec['columns']:
        raise ValueError('Excel列名不匹配：'+spec['sheet'])
    frame=frame.copy()
    for col,dtype in spec['dtypes'].items():
        if dtype!='object':
            s=frame[col].where(frame[col].ne(''),np.nan)
            if dtype=='bool':
                s=s.map(lambda v: v if isinstance(v,bool) else {'True':True,'False':False,'1':True,'0':False}[str(v)])
            else:s=pd.to_numeric(s,errors='raise')
            frame[col]=s.astype(dtype)
        else:
            frame[col]=frame[col].astype(object)
            kinds=spec.get('object_types',{}).get(col)
            if kinds and len(frame)==len(kinds):
                for i,kind in enumerate(kinds):
                    value=frame.at[i,col]
                    if kind=='NoneType' and value=='':frame.at[i,col]=None
                    elif kind in {'float','float64'}:frame.at[i,col]=float(value) if value!='' else np.nan
                    elif kind in {'int','int64'}:frame.at[i,col]=int(value)
                    elif kind=='str':frame.at[i,col]=str(value)
            else:
                frame.loc[frame[col].eq(''),col]=np.nan
    return frame

def prepare_public_inputs(excel_tables, workbook):
    parent={};summary=[]
    for spec in schema():
        frame=_restore(excel_tables[spec['sheet']],spec)
        key=spec['key']
        if key.startswith('parent/'):
            records=frame.astype(object).where(pd.notna(frame),None).values.tolist()
            parent[key.split('/',1)[1]]={'columns':list(frame.columns),'data':records}
        else:
            path=ROOT/key;path.parent.mkdir(parents=True,exist_ok=True)
            frame.to_csv(path,index=False,encoding='utf-8-sig',float_format=lambda x:format(x,'.17g'))
        summary.append({'工作表':spec['sheet'],'记录数':len(frame)})
    (ROOT/'input/public_parent_tables.json').write_text(json.dumps(parent,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    digest=hashlib.sha256(Path(workbook).read_bytes()).hexdigest()
    (ROOT/'input/excel_read_state.json').write_text(json.dumps({'workbook_sha256':digest}),encoding='utf-8')
    return pd.DataFrame(summary)

def ensure_inputs():
    status=ROOT/'input/excel_read_state.json'
    if not status.exists():raise RuntimeError('请先运行本Notebook的数据读取单元。')
    digest=hashlib.sha256((ROOT/'data/Public_model_inputs.xlsx').read_bytes()).hexdigest()
    if json.loads(status.read_text())['workbook_sha256']!=digest:
        raise RuntimeError('Excel已变化，请从本Notebook的数据读取单元重新运行。')

def read_public_parent(name):
    data=json.loads((ROOT/'input/public_parent_tables.json').read_text(encoding='utf-8'))[name]
    return pd.DataFrame(data['data'],columns=data['columns'])
