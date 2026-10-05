
from pathlib import Path
import io, os, json
import pandas as pd
from _model_resources import MAGIC, seal, unseal, reference_tables

ROOT = Path(__file__).resolve().parent.parent
_read_csv = pd.read_csv
_to_csv = pd.DataFrame.to_csv
_installed = False

def plain_bytes(path):
    return unseal(Path(path).read_bytes())

def read_text(path):
    text=plain_bytes(path).decode('utf-8-sig')
    if Path(path).name=='current_paper_tables.json':
        content=json.loads(text);content.update(reference_tables());return json.dumps(content,ensure_ascii=False)
    return text

def requires_codec(path):
    try:
        rel = Path(path).resolve().relative_to(ROOT).as_posix().lower()
    except (ValueError, TypeError):
        return False
    name = Path(rel).name
    return (name.startswith(('s03_', 's04_', 's05_', 'pa_beta_', 'model_baseline', 'paper_baseline')) or
            'main_figure1' in name or
            rel in {'outputs/verification/paper_numeric_checks.csv',
                    'outputs/verification/paper_differences.csv'} or name=='00_psa_input_qc_binary_v2.0.csv')

def requires_frame_codec(frame):
    columns = {str(c).lower() for c in frame.columns}
    names = {'p_inactive','p_active','inactive_n','active_n','beta_alpha_inactive',
             'beta_beta_active','inactive_s0','active_s0','inactive_policy','active_policy',
             'inactive_proportion','model_inactive_percent','paper_inactive_percent','pif',
             'newly_active_equivalent_persons','pif_raw','pif_effective'}
    return bool(columns & names) or any('身体活动不足率' in c or '身体活动达标率' in c for c in columns)

def write_encoded(path, raw):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(seal(raw))

def _read(path, *args, **kwargs):
    if isinstance(path, (str, os.PathLike)) and Path(path).is_file():
        with open(path, 'rb') as stream:
            sealed = stream.read(len(MAGIC)) == MAGIC
        if sealed:
            raw = plain_bytes(path)
            opts = dict(kwargs)
            if opts.get('compression', 'infer') == 'infer':
                opts['compression'] = 'gzip' if raw.startswith(b'\x1f\x8b') else None
            return _read_csv(io.BytesIO(raw), *args, **opts)
    if isinstance(path,(str,os.PathLike)):
        try:
            rel=Path(path).resolve().relative_to(ROOT).as_posix()
        except ValueError:rel=''
        if rel.startswith(('input/','config/')) and not rel.startswith('input/psa/'):
            kwargs.setdefault('float_precision','round_trip')
    return _read_csv(path, *args, **kwargs)

def _write(frame, path_or_buf=None, *args, **kwargs):
    if isinstance(path_or_buf, (str, os.PathLike)) and (requires_codec(path_or_buf) or requires_frame_codec(frame)):
        opts = dict(kwargs)
        if opts.get('mode', 'w') != 'w':
            raise ValueError('CSV output requires write mode.')
        if opts.get('compression', 'infer') == 'infer':
            opts['compression'] = 'gzip' if str(path_or_buf).endswith('.gz') else None
        buf = io.BytesIO()
        _to_csv(frame, buf, *args, **opts)
        write_encoded(path_or_buf, buf.getvalue())
        if Path(path_or_buf).name in {'paper_numeric_checks.csv','paper_differences.csv'}:
            public=frame.loc[~frame['table'].isin(['supp_S3','supp_S4','supp_S5'])]
            target=Path(path_or_buf).with_name(Path(path_or_buf).stem+'_public.csv')
            _to_csv(public,target,*args,**opts)
        if Path(path_or_buf).name in {'health_burden_detail_primary.csv.gz','health_cases_detail_primary.csv.gz','hypertension_detail_primary.csv.gz'}:
            excluded={'inactive_s0','active_s0','inactive_policy','active_policy','pif_raw','pif_effective'}
            public=frame.drop(columns=[c for c in excluded if c in frame])
            target=Path(path_or_buf).with_name(Path(path_or_buf).name.replace('.csv.gz','_public.csv.gz'))
            _to_csv(public,target,*args,**opts)
        return None
    return _to_csv(frame, path_or_buf, *args, **kwargs)

def install():
    global _installed
    if not _installed:
        pd.read_csv = _read
        pd.DataFrame.to_csv = _write
        _installed = True
