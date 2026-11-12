$ErrorActionPreference = 'Stop'
$study = Split-Path -Parent $MyInvocation.MyCommand.Path
$repo = Split-Path -Parent (Split-Path -Parent $study)
$python = Join-Path $repo '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Create project .venv and install round6 requirements.txt' }
$oldBytecode = $env:PYTHONDONTWRITEBYTECODE
Push-Location $study
try {
  $env:PYTHONDONTWRITEBYTECODE = '1'
  foreach ($script in @('build_round6.py','run_tests.py','execute_notebooks.py','finalize_run.py')) {
    & $python -X utf8 $script
    if ($LASTEXITCODE -ne 0) { throw "Round-six execution failed: $script" }
  }
} finally {
  $env:PYTHONDONTWRITEBYTECODE = $oldBytecode
  Pop-Location
}
