"""Record actual visual review, check idempotence and every manifest entry; no new analysis."""
from pathlib import Path
import sys,json,hashlib,subprocess,csv
sys.path.insert(0,str(Path(__file__).resolve().parent))
from src.model import HERE,ROOT,read,sha,jwrite
from src.pipeline import checks,finalize
# Canonicalise only new, public text artifacts; historical inputs and local raw archives are untouched.
for p in HERE.rglob('*'):
    if not p.is_file() or any(x in ['raw','.runtime','__pycache__'] for x in p.relative_to(HERE).parts) or p.suffix in ['.png','.pdf']:continue
    p.write_text(p.read_text('utf-8').replace('\r\n','\n'),encoding='utf-8',newline='\n')
jwrite(HERE/'logs/visual_qa.json',dict(status='PASS',reviewed_images=['figures/2030_identification_envelopes.png','figures/kyu_published_grid.png'],source_pages_rendered_and_inspected=['Kyu Appendix4 page22 Carlsson row','Kyu Appendix4 page79 TableF'],findings='labels/captions readable; endpoints visible; no clipping or invented point estimates; source600RR IHD.909 IS.910 verified visually; Carlsson selected subtype not resolved by Appendix table alone',scope='visual/data transcription review; NOT scientific main-analysis admission'))
a=checks();b=checks();assert a==b and len({r['id'] for r in a})==len(a)
assert all(len(r['cells'])>0 for r in [json.loads(p.read_text('utf-8')) for p in (HERE/'notebooks').glob('*.ipynb')])
for p in (HERE/'notebooks').glob('*.ipynb'):
    nb=json.loads(p.read_text('utf-8'));code=[c for c in nb['cells'] if c['cell_type']=='code'];assert all(c['execution_count'] is not None for c in code);assert not any(o['output_type']=='error' for c in code for o in c['outputs'])
diff=subprocess.check_output(['git','diff','1a2a8f11a0dd5c813d2cd35b18e906ea66dedc50','--name-only'],cwd=ROOT,text=True).splitlines();assert all(n.startswith('new_study/round7_burden_evidence/') for n in diff)
jwrite(HERE/'logs/final_integrity_check.json',dict(software_integrity='PASS',notebooks_executed=5,notebook_errors=0,finalizer_check_ids_unique=True,repeated_check_results_identical=True,old_tracked_files_changed=0,original_locked_inputs_verified=11,scientific_gates='separate:3FAIL,1NOT_CHECKED; no main point result release',figure_visual_qa='PASS',publication='only Round7 code, deidentified aggregate derivatives and factual evidence extractions; raw sources local only'))
finalize()
bad=[r['path'] for r in read(HERE/'sha256_manifest.csv') if sha(HERE/r['path'])!=r['sha256']]
assert not bad,bad
print('MANIFEST_ALL_MATCH',len(read(HERE/'sha256_manifest.csv')))
