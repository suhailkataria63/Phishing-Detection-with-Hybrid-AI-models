#!/usr/bin/env python3
from __future__ import annotations
import argparse, runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEGACY = ROOT / 'pipelines' / 'email' / 'legacy'
TARGETS = {
    'cross-source': 'evaluate_email_cross_source.py',
    'hybrid-cross-source': 'evaluate_email_hybrid_cross_source.py',
    'thresholds': 'analyze_email_hybrid_thresholds.py',
}

def main() -> None:
    p = argparse.ArgumentParser(description='Email evaluation pipeline entrypoint')
    p.add_argument('task', choices=sorted(TARGETS.keys()))
    args, _ = p.parse_known_args()
    runpy.run_path(str(LEGACY / TARGETS[args.task]), run_name='__main__')

if __name__ == '__main__':
    main()
