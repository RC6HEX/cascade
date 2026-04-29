#!/usr/bin/env bash
# Cascade — one-liner installer.
#
# Usage:
#   bash install.sh           # install only — prints how to launch
#   bash install.sh --run     # install + launch web UI immediately
#   OPENROUTER_API_KEY=sk-or-v1-... bash install.sh --run    # non-interactive
#
# What it does:
#   1. Finds Python 3.11+
#   2. Creates .venv, installs deps
#   3. If .env doesn't exist — prompts for OPENROUTER_API_KEY (or reads $OPENROUTER_API_KEY)
#   4. With --run: launches `python -m ui` on http://127.0.0.1:8000

set -euo pipefail

cd "$(dirname "$0")"

RUN_AFTER=0
for arg in "$@"; do
  case "$arg" in
    --run|-r) RUN_AFTER=1 ;;
    -h|--help)
      sed -n '2,15p' "$0"; exit 0 ;;
  esac
done

echo "→ Cascade installer"
echo ""

# 1. Find Python
PYTHON_BIN=""
for cand in python3.13 python3.12 python3.11 python3 python; do
  if command -v "$cand" >/dev/null 2>&1; then
    ver=$("$cand" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "0.0")
    major=$(echo "$ver" | cut -d. -f1)
    minor=$(echo "$ver" | cut -d. -f2)
    if [ "$major" = "3" ] && [ "$minor" -ge 11 ] 2>/dev/null; then
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
echo "✓ Зависимости установлены"

# 5. Bootstrap .env
if [ ! -f .env ]; then
  cp .env.example .env

  # Try to read from env var first
  KEY="${OPENROUTER_API_KEY:-}"
  if [ -z "$KEY" ] && [ -t 0 ]; then
    # Interactive: prompt
    echo ""
    echo "Нужен OpenRouter API ключ (получить: https://openrouter.ai/keys)"
    printf "Вставь ключ (или Enter — потом сам впиши в .env): "
    read -r KEY || KEY=""
  fi

  if [ -n "$KEY" ]; then
    # Patch .env with the key (BSD/GNU compatible: write to temp + mv)
    awk -v k="$KEY" '/^OPENROUTER_API_KEY=/ { print "OPENROUTER_API_KEY=" k; next } { print }' .env > .env.tmp
    mv .env.tmp .env
    echo "✓ Ключ записан в .env"
  else
    echo "⚠ .env создан, но ключ не вписан. Открой и добавь:"
    echo "    OPENROUTER_API_KEY=sk-or-v1-..."
  fi
else
  echo "✓ .env уже существует"
fi

echo ""
echo "════════════════════════════════════════════"
echo " Установка завершена."

if [ "$RUN_AFTER" = "1" ]; then
  echo " Запускаю веб-интерфейс..."
  echo "════════════════════════════════════════════"
  echo ""
  exec "$VENV_PY" -m ui
fi

echo ""
echo " Запуск веб-интерфейса:"
echo "   $VENV_PY -m ui"
echo ""
echo " Или CLI на конкретное задание:"
echo "   $VENV_PY -m generator --task task_a"
echo ""
echo " UI будет на: http://127.0.0.1:8000"
echo "════════════════════════════════════════════"
