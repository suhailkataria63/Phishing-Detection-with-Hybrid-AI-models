#!/usr/bin/env python3
from __future__ import annotations
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
runpy.run_path(str(ROOT / 'pipelines/url/legacy/calibrate_url_model_v1.py'), run_name='__main__')
