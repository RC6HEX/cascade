"""CLI launcher: python -m ui --port 8000"""
from __future__ import annotations

import argparse
import logging

import uvicorn


def main() -> int:
    parser = argparse.ArgumentParser(prog="ui", description="Autonomous Generator Web UI")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true", help="auto-reload on code changes")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%H:%M:%S",
    )

    uvicorn.run(
        "ui.server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="debug" if args.verbose else "info",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
