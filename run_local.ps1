$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $MyInvocation.MyCommand.Path
$study = Join-Path $repo 'new_study\round5_dynamic_calibration_20261112'
$python = Join-Path $repo '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'BLOCKED_INPUT: create .venv and install requirements.txt' }
$oldBytecode = $env:PYTHONDONTWRITEBYTECODE
Push-Location $study
try {
  $env:PYTHONDONTWRITEBYTECODE = '1'
  foreach ($script in @('build_round5.py','run_tests.py','execute_notebooks.py','finalize_run.py')) {
    & $python $script
    if ($LASTEXITCODE -ne 0) { throw "Round-five execution failed: $script" }
  }
} finally {
  $env:PYTHONDONTWRITEBYTECODE = $oldBytecode
  Pop-Location
}
