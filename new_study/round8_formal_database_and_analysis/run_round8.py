"""One command rebuild of CSV database, deterministic analysis, figures and notebooks."""
import argparse
from round8 import *
from deliver import plots,reports,notebooks,finalize
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--finalize-only',action='store_true');parser.add_argument('--skip-migration',action='store_true');args=parser.parse_args()
 if not args.finalize_only:
  if not args.skip_migration:print('Migrated GBD records:',migrate(),flush=True)
  d,_,_=calculate();print('Annual detailed scenario rows:',len(d),flush=True)
  from postprocess import run as add_reporting_metrics
  add_reporting_metrics();reports();plots();notebooks();print('5 notebooks executed',flush=True)
  from prepare_workbook import prepare
  prepare()
  import os
  node=os.environ.get('ARTIFACT_NODE_EXECUTABLE',str(Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe'))
  subprocess.run([node,'--max-old-space-size=12288',str(HERE/'build_workbook.mjs'),str(HERE)],check=True)
 checks=finalize();print(json.dumps({'software_failures':[t['id'] for t in checks if t['gate']=='software' and t['status']=='FAIL']},ensure_ascii=False),flush=True)
 if any(t['gate']=='software' and t['status']=='FAIL' for t in checks):raise SystemExit(1)
