from round8 import *
def prepare():
 names=['population','pa_binary_exposure','pa_published_validation','gbd_burden','gbd_cases','rr_admitted','rr_evidence_all','disease_mapping','medical_cost_candidates','productivity_candidates','source_manifest','old_to_new_crosswalk','transformation_log','formal_input_admission','conditional_inputs','excluded_legacy_inputs','genuine_remaining_gaps']
 meta=[]
 for name in names:
  d=read(HERE/'database'/f'{name}.csv').fillna('');rows=d.astype(object).where(pd.notna(d),None).values.tolist()
  # Pandas inferred numeric columns remain numeric; literal TRUE/FALSE metadata is preserved.
  js('runtime/'+name+'.json',dict(columns=list(d.columns),rows=rows));meta.append(dict(sheet=name[:31],csv='database/'+name+'.csv',payload=name+'.json'))
 js('runtime/workbook_payload.json',meta)
if __name__=='__main__':prepare()
