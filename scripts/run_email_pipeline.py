#!/usr/bin/env python3
from __future__ import annotations
import argparse
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "pipelines" / "email" / "train.py"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run email pipeline tasks")
    parser.add_argument(
        "task",
        choices=["baseline", "hybrid", "transformer", "final", "build-dataset", "build-features"],
        help="Email pipeline task",
    )
    args, _ = parser.parse_known_args()

    import sys
    sys.argv = [str(ENTRY), args.task]
    runpy.run_path(str(ENTRY), run_name="__main__")


if __name__ == "__main__":
    main()
