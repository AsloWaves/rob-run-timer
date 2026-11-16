# Builds dist\RobRunTimer.exe (single file, no Python needed on the target PC).
# Usage:  powershell -ExecutionPolicy Bypass -File build.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not (Test-Path .venv-build)) { python -m venv .venv-build }
.\.venv-build\Scripts\python -m pip install --quiet --upgrade pyinstaller
.\.venv-build\Scripts\pyinstaller --noconfirm --clean --onefile --windowed `
    --name RobRunTimer --icon assets\icon.ico --add-data "assets\icon.ico;assets" rob_run_timer.py
$exe = "dist\RobRunTimer.exe"
"{0}  {1:N1} MB" -f $exe, ((Get-Item $exe).Length / 1MB)
"SHA256: " + (Get-FileHash $exe -Algorithm SHA256).Hash
