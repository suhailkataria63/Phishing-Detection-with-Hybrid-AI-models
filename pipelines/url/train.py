#!/usr/bin/env python3
from __future__ import annotations
import argparse, runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEGACY = ROOT / 'pipelines' / 'url' / 'legacy'
TARGETS = {
    'v1': 'train_url_model_v1.py',
    'v2': 'train_url_model_v2_ngrams.py',
    'dataset': 'build_dataset_v1.py',
}

def main() -> None:
    p = argparse.ArgumentParser(description='URL training pipeline entrypoint')
    p.add_argument('task', choices=sorted(TARGETS.keys()))
    args, _ = p.parse_known_args()
    runpy.run_path(str(LEGACY / TARGETS[args.task]), run_name='__main__')

if __name__ == '__main__':
    main()
