# Windows PowerShell: installs desktop only. No AF3 weights, Docker, or databases.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$py = if (Get-Command py -ErrorAction SilentlyContinue) { 'py' } else { 'python' }
if ($py -eq 'py') {
  & py -3.11 -c "import sys; assert sys.version_info >= (3, 11)"
  if ($LASTEXITCODE -eq 0) { $pyFlags = @('-3.11') }
  else { $pyFlags = @('-3') }
  & py @pyFlags -c "import sys; assert sys.version_info >= (3, 11), 'Python 3.11+ required'"
  if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.11+ and the py launcher first' }
  & py @pyFlags -m venv .venv
} else {
  & python -c "import sys; assert sys.version_info >= (3, 11), 'Python 3.11+ required'"
  if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.11+ first' }
  & python -m venv .venv
}
if ($LASTEXITCODE -ne 0) { throw 'Could not create virtual environment' }
$venvPython = Join-Path $root '.venv\Scripts\python.exe'
& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'pip upgrade failed' }
& $venvPython -m pip install -e '.[gui,recommended]'
if ($LASTEXITCODE -ne 0) { throw 'pip install failed' }
& $venvPython -m pip check
if ($LASTEXITCODE -ne 0) { throw 'pip check failed' }
& $venvPython -m ppigfinder.integrations.af3.cli doctor --mode wrapper
Write-Host 'PPIGFINDER_INSTALL=PASS'
Write-Host 'Launch: .\.venv\Scripts\python.exe main.py'
