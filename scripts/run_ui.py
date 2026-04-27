"""Wrapper that ensures we run from the project root.

Used by .claude/launch.json (preview_start) which doesn't honor a working dir.
For everyday use, prefer:
    python -m ui --port 8000
"""
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT))

from ui.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
