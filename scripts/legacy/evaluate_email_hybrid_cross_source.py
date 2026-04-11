#!/usr/bin/env python3
from __future__ import annotations
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
runpy.run_path(str(ROOT / 'pipelines/email/legacy/evaluate_email_hybrid_cross_source.py'), run_name='__main__')
