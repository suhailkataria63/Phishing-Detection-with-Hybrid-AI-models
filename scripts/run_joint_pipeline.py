#!/usr/bin/env python3
from __future__ import annotations
import argparse
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINTS = {
    "optimize": ROOT / "pipelines" / "joint" / "optimize.py",
    "evaluate": ROOT / "pipelines" / "joint" / "evaluate.py",
    "calibrate": ROOT / "pipelines" / "joint" / "calibrate.py",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run joint pipeline tasks")
    parser.add_argument("mode", choices=sorted(ENTRYPOINTS.keys()))
    args, _ = parser.parse_known_args()

    entry = ENTRYPOINTS[args.mode]
    import sys
    sys.argv = [str(entry)]
    runpy.run_path(str(entry), run_name="__main__")


if __name__ == "__main__":
    main()
