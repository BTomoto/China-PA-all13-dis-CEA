$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $MyInvocation.MyCommand.Path
$study = Join-Path $repo 'new_study\round4_dynamic_health_model_20261112'
$python = Join-Path $repo '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'BLOCKED_INPUT: create .venv with py -m venv .venv' }
Push-Location $study
try {
  & $python build_round4.py
  if ($LASTEXITCODE -ne 0) { throw 'BLOCKED_INPUT: build/validation failed' }
  $env:PYTHONPATH = $study
  & $python -m unittest discover -s tests -p 'test_*.py' -v
  if ($LASTEXITCODE -ne 0) { throw 'BLOCKED_INPUT: tests failed' }
  & $python execute_notebooks.py
  if ($LASTEXITCODE -ne 0) { throw 'BLOCKED_INPUT: notebook execution failed' }
  & $python finalize_run.py
  if ($LASTEXITCODE -ne 0) { throw 'BLOCKED_INPUT: finalization failed' }
  Write-Output 'BLOCKED_DYNAMIC_PARAMETERS: empirical transitions are missing; synthetic software fixture passed.'
} finally { Pop-Location }
