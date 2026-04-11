#!/usr/bin/env python3
from __future__ import annotations
import argparse
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINTS = {
    "train": ROOT / "pipelines" / "url" / "train.py",
    "evaluate": ROOT / "pipelines" / "url" / "evaluate.py",
    "calibrate": ROOT / "pipelines" / "url" / "calibrate.py",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run URL pipeline tasks")
    parser.add_argument("mode", choices=sorted(ENTRYPOINTS.keys()))
    parser.add_argument("task", nargs="?", help="Optional train task: v1|v2|dataset")
    args, _ = parser.parse_known_args()

    entry = ENTRYPOINTS[args.mode]
    import sys
    sys.argv = [str(entry)] + ([args.task] if args.task else [])
    runpy.run_path(str(entry), run_name="__main__")


if __name__ == "__main__":
    main()
