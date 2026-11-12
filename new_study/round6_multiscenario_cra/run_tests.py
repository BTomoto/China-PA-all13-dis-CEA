"""Run only CRA tests; prior natural-history test records stay historical."""
import io,json,unittest
from src.common import R6,ROOT,sha,write_json

suite=unittest.defaultTestLoader.discover(str(R6/'tests'),pattern='test_cra.py')
stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
text=stream.getvalue();(R6/'logs/cra_tests.log').write_text(text,encoding='utf-8',newline='\n')
cases=[]
for line in text.splitlines():
    if line.startswith('test_') and ' ... ' in line:
        name,status=line.rsplit(' ... ',1);cases.append(dict(check_id=name.split(' ')[0],status='PASS' if status=='ok' else 'FAIL',detail=line))
if len({r['check_id'] for r in cases})!=len(cases):raise SystemExit('duplicate test IDs')
write_json(R6/'logs/test_results.json',dict(tests_run=result.testsRun,failed=len(result.failures),errors=len(result.errors),status='PASS' if result.wasSuccessful() else 'FAIL',cases=cases))
previous=ROOT/'new_study/round5_dynamic_calibration_20261112/logs/test_results.json'
write_json(R6/'logs/prior_test_reference.json',dict(source=str(previous.relative_to(ROOT)),sha256=sha(previous),historical_test_count=85,status='HISTORICAL_NOT_EXECUTED_THIS_ROUND',reason='Prior tests execute natural-history functions; current scope prohibits that execution'))
print(f'Current CRA tests={result.testsRun} failures={len(result.failures)} errors={len(result.errors)}',flush=True)
if not result.wasSuccessful():print(text);raise SystemExit(1)
