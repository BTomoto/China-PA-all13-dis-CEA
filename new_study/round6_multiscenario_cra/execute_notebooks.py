import os,sys
import nbformat
from nbclient import NotebookClient
from ipykernel.kernelspec import get_kernel_dict
from src.common import R6,write_json

runtime=R6/'.runtime';kernel_dir=runtime/'kernels/round6';kernel_dir.mkdir(parents=True,exist_ok=True)
kernel=get_kernel_dict();kernel['argv'][0]=sys.executable;write_json(kernel_dir/'kernel.json',kernel)
os.environ['JUPYTER_PATH']=str(runtime);os.environ['JUPYTER_RUNTIME_DIR']=str(runtime/'runtime');os.environ['IPYTHONDIR']=str(runtime/'ipython')
results=[]
for path in sorted((R6/'notebooks').glob('*.ipynb')):
    nb=nbformat.read(path,as_version=4)
    try:
        NotebookClient(nb,timeout=300,kernel_name='round6',resources={'metadata':{'path':str(R6)}}).execute();status='PASS';error=''
    except Exception as exc:status='FAIL';error=repr(exc)
    (R6/'notebooks/executed'/path.name).write_text(nbformat.writes(nb)+'\n',encoding='utf-8',newline='\n')
    results.append(dict(notebook=path.name,status=status,engine='nbclient0.10.2 + real ipykernel',executed_cells=sum(c.cell_type=='code' and c.execution_count is not None for c in nb.cells),error=error));print(path.name,status,flush=True)
write_json(R6/'logs/notebook_execution.json',results)
if len(results)!=5 or any(r['status']!='PASS' for r in results):raise SystemExit(1)
