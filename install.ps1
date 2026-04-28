# Cascade — one-line installer for Windows.
# Usage:  powershell -ExecutionPolicy Bypass -File install.ps1

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
  # Last-resort: common install location
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

# 4. Bootstrap .env
if (-not (Test-Path '.env')) {
  Copy-Item '.env.example' '.env'
  Write-Host "✓ Создан .env. Открой его и впиши OPENROUTER_API_KEY." -ForegroundColor Yellow
  Write-Host "   Получить ключ: https://openrouter.ai/keys"
} else {
  Write-Host "✓ .env уже существует"
}

Write-Host ""
Write-Host "═══════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host " Установка завершена." -ForegroundColor Green
Write-Host ""
Write-Host " Запуск веб-интерфейса:"
Write-Host "   .venv\Scripts\python.exe -m ui"
Write-Host ""
Write-Host " Или CLI:"
Write-Host "   .venv\Scripts\python.exe -m generator --task task_a"
Write-Host ""
Write-Host " Открой в браузере: http://127.0.0.1:8000"
Write-Host "═══════════════════════════════════════════════" -ForegroundColor Cyan
