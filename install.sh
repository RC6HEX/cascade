#!/usr/bin/env bash
# Cascade — one-line installer.
# Usage: bash install.sh
#
# Creates .venv, installs deps, copies .env.example → .env if missing.
# After install, edit .env to add OPENROUTER_API_KEY then run:
#   .venv/bin/python -m ui    (Linux/macOS)
#   .venv\Scripts\python -m ui    (Windows)

set -euo pipefail

cd "$(dirname "$0")"

echo "→ Cascade installer"
echo ""

# 1. Find Python
PYTHON_BIN=""
for cand in python3.13 python3.12 python3.11 python3 python; do
  if command -v "$cand" >/dev/null 2>&1; then
    ver=$("$cand" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    major=$(echo "$ver" | cut -d. -f1)
    minor=$(echo "$ver" | cut -d. -f2)
    if [ "$major" -ge 3 ] && [ "$minor" -ge 11 ]; then
      PYTHON_BIN="$cand"
      echo "✓ Python: $cand ($ver)"
      break
    fi
  fi
done

if [ -z "$PYTHON_BIN" ]; then
  echo "✗ Не нашёл Python 3.11+. Установи: https://www.python.org/downloads/"
  exit 1
fi

# 2. Create venv
if [ ! -d .venv ]; then
  echo "→ Создаю виртуальное окружение в .venv ..."
  "$PYTHON_BIN" -m venv .venv
else
  echo "✓ .venv уже существует"
fi

# 3. Resolve venv python
if [ -x ".venv/bin/python" ]; then
  VENV_PY=".venv/bin/python"
elif [ -x ".venv/Scripts/python.exe" ]; then
  VENV_PY=".venv/Scripts/python.exe"
else
  echo "✗ Не нашёл python внутри .venv"
  exit 1
fi

# 4. Install deps
echo "→ Устанавливаю зависимости..."
"$VENV_PY" -m pip install --upgrade pip --quiet
"$VENV_PY" -m pip install -r requirements.txt --quiet

# 5. Bootstrap .env
if [ ! -f .env ]; then
  cp .env.example .env
  echo "✓ Создан .env. Открой его и впиши OPENROUTER_API_KEY."
  echo "   Получить ключ: https://openrouter.ai/keys"
else
  echo "✓ .env уже существует"
fi

echo ""
echo "════════════════════════════════════════════"
echo " Установка завершена."
echo ""
echo " Запуск веб-интерфейса:"
echo "   $VENV_PY -m ui"
echo ""
echo " Или напрямую через CLI:"
echo "   $VENV_PY -m generator --task task_a"
echo ""
echo " Открой в браузере: http://127.0.0.1:8000"
echo "════════════════════════════════════════════"
