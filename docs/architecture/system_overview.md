# System Overview

## Runtime Architecture
- `app/frontend/`: Next.js UI for URL, Email, and Joint detection modes.
- `app/backend/`: FastAPI backend serving URL model, email model, and joint rule-assisted scoring.

## ML Layers
- URL channel: hybrid URL model (`url_model.py` + `url_model_v2.py` + `hybrid_url.py`).
- Email channel: DistilBERT text-only inference (`email_model.py`).
- Joint channel: explainable rule-assisted strategy (`joint_scoring.py` + `joint_optimization.py`).

## Pipelines
- `pipelines/email/`: train/evaluate/ablation/portability entrypoints.
- `pipelines/url/`: train/evaluate/calibrate entrypoints.
- `pipelines/joint/`: optimize/evaluate/calibrate entrypoints.

## Storage Layout
- `data/processed/`: modeling-ready datasets.
- `data/eval/`: synthetic benchmark suites.
- `data/samples/`: compact sample/calibration inputs.
- `models/email|url|joint/`: organized model artifacts.

## Reporting Layout
- `reports/final/`: high-value stable reports.
- `reports/experiments/`: interim evaluation outputs.
- `reports/archive/`: superseded/legacy reports.

## Compatibility Notes
- Root `backend` and `frontend` are symlinks to `app/backend` and `app/frontend` for command compatibility.
- Root `scripts/*.py` are compatibility wrappers pointing to consolidated `pipelines/**/legacy/` scripts.
