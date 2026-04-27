#!/usr/bin/env bash
# Regenerate all 3 demos and copy them into deploy/
# Usage: bash scripts/regenerate_all.sh

set -euo pipefail

cd "$(dirname "$0")/.."

PYTHON="${PYTHON:-./.venv/Scripts/python.exe}"
if [ ! -x "$PYTHON" ]; then
  PYTHON="./.venv/bin/python"
fi

echo "→ Generating task_a (calculator)..."
"$PYTHON" -m generator --task task_a

echo "→ Generating task_b (taskboard)..."
"$PYTHON" -m generator --task task_b

echo "→ Generating task_c (currency)..."
"$PYTHON" -m generator --task task_c

echo "→ Copying outputs to deploy/..."
rm -rf deploy/task_a deploy/task_b deploy/task_c
cp -r output/task_a deploy/
cp -r output/task_b deploy/
cp -r output/task_c deploy/

echo
echo "✓ Done. Open deploy/index.html or run:"
echo "  $PYTHON -m http.server 8765 --directory deploy"
