#!/usr/bin/env python3
from __future__ import annotations
import argparse, runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEGACY = ROOT / 'pipelines' / 'email' / 'legacy'
TARGETS = {
    'baseline': 'train_email_baseline.py',
    'hybrid': 'train_email_hybrid_baseline.py',
    'transformer': 'train_email_transformer.py',
    'final': 'train_email_final_model.py',
    'build-dataset': 'build_email_dataset.py',
    'build-features': 'build_email_features.py',
}

def main() -> None:
    p = argparse.ArgumentParser(description='Email training/data pipeline entrypoint')
    p.add_argument('task', choices=sorted(TARGETS.keys()))
    args, _ = p.parse_known_args()
    runpy.run_path(str(LEGACY / TARGETS[args.task]), run_name='__main__')

if __name__ == '__main__':
    main()
