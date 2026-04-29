# Cascade — one-liner installer for Windows.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File install.ps1
#   powershell -ExecutionPolicy Bypass -File install.ps1 -Run
#   $env:OPENROUTER_API_KEY="sk-or-v1-..."; powershell -ExecutionPolicy Bypass -File install.ps1 -Run
#
# What it does:
#   1. Finds Python 3.11+
#   2. Creates .venv, installs deps
#   3. If .env doesn't exist — prompts for OPENROUTER_API_KEY (or reads $env:OPENROUTER_API_KEY)
#   4. With -Run: launches `python -m ui` on http://127.0.0.1:8000

param(
  [switch]$Run
)

$ErrorActionPreference = 'Stop'
Set-Location -Path $PSScriptRoot

Write-Host "→ Cascade installer" -ForegroundColor Cyan
Write-Host ""

# 1. Find Python
$pythonBin = $null
foreach ($cand in @('python', 'python3', 'py')) {
  try {
    $ver = & $cand -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>$null
    if ($ver -and $LASTEXITCODE -eq 0) {
      $parts = $ver.Trim().Split('.')
      if ([int]$parts[0] -ge 3 -and [int]$parts[1] -ge 11) {
        $pythonBin = $cand
        Write-Host "✓ Python: $cand ($($ver.Trim()))" -ForegroundColor Green
        break
      }
    }
  } catch { }
}

if (-not $pythonBin) {
  $userPython = "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe"
  if (Test-Path $userPython) {
    $pythonBin = $userPython
    Write-Host "✓ Python: $userPython" -ForegroundColor Green
  } else {
    Write-Host "✗ Не нашёл Python 3.11+. Установи: https://www.python.org/downloads/" -ForegroundColor Red
    exit 1
  }
}

# 2. Create venv
if (-not (Test-Path '.venv')) {
  Write-Host "→ Создаю виртуальное окружение в .venv ..."
  & $pythonBin -m venv .venv
} else {
  Write-Host "✓ .venv уже существует"
}

$venvPy = Join-Path (Get-Location) '.venv\Scripts\python.exe'
if (-not (Test-Path $venvPy)) {
  Write-Host "✗ Не нашёл python в .venv" -ForegroundColor Red
  exit 1
}

# 3. Install deps
Write-Host "→ Устанавливаю зависимости..."
& $venvPy -m pip install --upgrade pip --quiet
& $venvPy -m pip install -r requirements.txt --quiet
Write-Host "✓ Зависимости установлены" -ForegroundColor Green

# 4. Bootstrap .env
if (-not (Test-Path '.env')) {
  Copy-Item '.env.example' '.env'

  $key = $env:OPENROUTER_API_KEY
  if (-not $key -and [Environment]::UserInteractive) {
    Write-Host ""
    Write-Host "Нужен OpenRouter API ключ (получить: https://openrouter.ai/keys)"
    $key = Read-Host "Вставь ключ (или Enter — потом сам впиши в .env)"
  }

  if ($key) {
    (Get-Content .env) -replace '^OPENROUTER_API_KEY=.*', "OPENROUTER_API_KEY=$key" |
      Set-Content -Encoding UTF8 .env
    Write-Host "✓ Ключ записан в .env" -ForegroundColor Green
  } else {
    Write-Host "⚠ .env создан, но ключ не вписан. Открой и добавь:" -ForegroundColor Yellow
    Write-Host "    OPENROUTER_API_KEY=sk-or-v1-..."
  }
} else {
  Write-Host "✓ .env уже существует"
}

Write-Host ""
Write-Host "═══════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host " Установка завершена." -ForegroundColor Green

if ($Run) {
  Write-Host " Запускаю веб-интерфейс..."
  Write-Host "═══════════════════════════════════════════════" -ForegroundColor Cyan
  Write-Host ""
  & $venvPy -m ui
  exit $LASTEXITCODE
}

Write-Host ""
Write-Host " Запуск веб-интерфейса:"
Write-Host "   .venv\Scripts\python.exe -m ui"
Write-Host ""
Write-Host " Или CLI на конкретное задание:"
Write-Host "   .venv\Scripts\python.exe -m generator --task task_a"
Write-Host ""
Write-Host " UI будет на: http://127.0.0.1:8000"
Write-Host "═══════════════════════════════════════════════" -ForegroundColor Cyan
