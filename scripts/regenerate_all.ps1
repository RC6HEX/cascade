# Regenerate all 3 demos and copy them into deploy/
# Usage: powershell -ExecutionPolicy Bypass -File scripts\regenerate_all.ps1

$ErrorActionPreference = 'Stop'
Set-Location -Path (Join-Path $PSScriptRoot '..')

$Python = Join-Path (Get-Location) '.venv\Scripts\python.exe'

Write-Host "-> Generating task_a (calculator)..."
& $Python -m generator --task task_a

Write-Host "-> Generating task_b (taskboard)..."
& $Python -m generator --task task_b

Write-Host "-> Generating task_c (currency)..."
& $Python -m generator --task task_c

Write-Host "-> Copying outputs to deploy/..."
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue 'deploy\task_a','deploy\task_b','deploy\task_c'
Copy-Item -Recurse 'output\task_a' 'deploy\'
Copy-Item -Recurse 'output\task_b' 'deploy\'
Copy-Item -Recurse 'output\task_c' 'deploy\'

Write-Host ""
Write-Host "Done. Run a local server:"
Write-Host "  python -m http.server 8765 --directory deploy"
