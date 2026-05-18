# Project Tree

## Cleaned Repository Structure

```text
phish-detector/
├── app/
│   ├── backend/                # FastAPI backend (runtime APIs + ML serving)
│   └── frontend/               # Next.js frontend
├── backend -> app/backend      # compatibility symlink
├── frontend -> app/frontend    # compatibility symlink
├── data/
│   ├── raw/                    # raw source datasets
│   ├── interim/                # intermediate data
│   ├── processed/              # processed training datasets
│   ├── eval/                   # synthetic evaluation suites (v2)
│   └── samples/                # calibration/sample inputs
├── models/
│   ├── email/                  # email model artifacts
│   ├── url/                    # URL model artifacts
│   ├── joint/                  # joint artifacts (reserved)
│   └── (legacy symlinks for compatibility)
├── pipelines/
│   ├── email/
│   │   ├── train.py
│   │   ├── evaluate.py
│   │   ├── ablation.py
│   │   ├── portability.py
│   │   └── legacy/
│   ├── url/
│   │   ├── train.py
│   │   ├── evaluate.py
│   │   ├── calibrate.py
│   │   └── legacy/
│   └── joint/
│       ├── optimize.py
│       ├── evaluate.py
│       ├── calibrate.py
│       └── legacy/
├── scripts/
│   ├── run_email_pipeline.py   # compact launcher
│   ├── run_url_pipeline.py     # compact launcher
│   ├── run_joint_pipeline.py   # compact launcher
│   ├── smoke_load_models.py    # deployment/runtime smoke check
│   ├── README.md
│   └── (no legacy wrappers)    # legacy wrappers moved to archive/
├── docs/
│   ├── architecture/
│   ├── experiments/
│   └── integration/
├── reports/
│   ├── final/                  # stable/high-value reports
│   ├── experiments/            # intermediate experiments + CSV outputs
│   ├── archive/                # superseded legacy reports
│   └── project_step_summary.md -> final/project_step_summary.md
├── archive/
│   ├── old_scripts/
│   ├── old_reports/
│   ├── deprecated_artifacts/
│   └── ARCHIVE_NOTES.md
├── tests/
├── README.md
├── requirements.txt
└── project_tree.md
```

## Top-Level Folder Purpose
- `app/`: active runtime product app code (backend + frontend).
- `data/`: datasets by lifecycle stage (raw/processed/eval/samples).
- `models/`: persisted model artifacts grouped by detector type.
- `pipelines/`: active workflow entrypoints by domain.
- `scripts/`: minimal launchers plus relocated legacy wrappers.
- `docs/`: architecture, integration notes, and experiment design docs.
- `reports/`: organized outputs (final vs experiments vs archived).
- `archive/`: preserved deprecated material and migration notes.

## Active Entrypoints

### Primary (recommended)
- `python pipelines/email/train.py <baseline|hybrid|transformer|final|build-dataset|build-features>`
- `python pipelines/email/evaluate.py <cross-source|hybrid-cross-source|thresholds>`
- `python pipelines/email/ablation.py`
- `python pipelines/email/portability.py`
- `python pipelines/url/train.py <v1|v2|dataset>`
- `python pipelines/url/evaluate.py`
- `python pipelines/url/calibrate.py`
- `python pipelines/joint/optimize.py`
- `python pipelines/joint/evaluate.py`
- `python pipelines/joint/calibrate.py`

### Compact launchers
- `python scripts/run_email_pipeline.py <task>`
- `python scripts/run_url_pipeline.py <train|evaluate|calibrate> [v1|v2|dataset]`
- `python scripts/run_joint_pipeline.py <optimize|evaluate|calibrate>`

## Reports Classification
- Final reports: `reports/final/*`
- Experimental/intermediate outputs: `reports/experiments/*`
- Archived/superseded reports: `reports/archive/*`

## Compatibility Notes
- Old wrapper commands were relocated from `scripts/*.py` to `archive/old_scripts/scripts_legacy/` to reduce explorer clutter.
- Existing backend/frontend commands still work via root symlinks.
