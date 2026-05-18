#!/usr/bin/env python3
from __future__ import annotations
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
runpy.run_path(str(ROOT / 'pipelines/url/legacy/train_url_model_v2_ngrams.py'), run_name='__main__')
