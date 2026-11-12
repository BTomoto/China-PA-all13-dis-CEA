"""Standard Jupyter kernel execution with nbclient; outputs saved separately."""
import json
import os
import sys
from pathlib import Path
import nbformat
from nbclient import NotebookClient
from ipykernel.kernelspec import get_kernel_dict
from src.common import R5,write_json

runtime=R5/'.runtime';kernel_dir=runtime/'kernels/round5';kernel_dir.mkdir(parents=True,exist_ok=True)
kernel=get_kernel_dict();kernel['argv'][0]=sys.executable
write_json(kernel_dir/'kernel.json',kernel)
os.environ['JUPYTER_PATH']=str(runtime)
os.environ['JUPYTER_RUNTIME_DIR']=str(runtime/'runtime')
os.environ['IPYTHONDIR']=str(runtime/'ipython')
results=[]
for path in sorted((R5/'notebooks').glob('*.ipynb')):
    notebook=nbformat.read(path,as_version=4)
    client=NotebookClient(notebook,timeout=300,kernel_name='round5',resources={'metadata':{'path':str(R5)}})
    try:
        client.execute();status='PASS'
    except Exception as error:
        status='FAIL';failure=repr(error)
    (R5/'notebooks/executed'/path.name).write_text(nbformat.writes(notebook)+'\n',encoding='utf-8',newline='\n')
    results.append(dict(notebook=path.name,status=status,engine='nbclient 0.10.2; real ipykernel',executed_code_cells=sum(c.cell_type=='code' and c.execution_count is not None for c in notebook.cells),error='' if status=='PASS' else failure))
    print(path.name,status,flush=True)
write_json(R5/'logs/notebook_execution.json',results)
if len(results)!=5 or any(r['status']!='PASS' for r in results):raise SystemExit(1)
