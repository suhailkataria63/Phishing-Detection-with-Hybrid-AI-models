#!/usr/bin/env python3
from __future__ import annotations
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
runpy.run_path(str(ROOT / 'pipelines' / 'joint' / 'legacy' / 'evaluate_joint_detector_robustly.py'), run_name='__main__')
