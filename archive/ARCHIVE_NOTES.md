# Archive Notes

## What Was Moved

### Deprecated artifacts
Moved to `archive/deprecated_artifacts/`:
- `report/` -> `archive/deprecated_artifacts/report_legacy/`
- `RP/` -> `archive/deprecated_artifacts/RP_legacy/`
- `hybrid_url.py` (top-level legacy copy) -> `archive/deprecated_artifacts/hybrid_url_legacy.py`
- `Advanced Phishing Detection using hybrid.md` -> `archive/deprecated_artifacts/advanced_hybrid_notes.md`

### Reports
- Legacy URL model text reports moved to `reports/archive/`.
- Intermediate experiment outputs moved to `reports/experiments/`.
- Final/high-value reports moved to `reports/final/`.

### Wrapper minimization
- 19 thin compatibility wrappers were moved from `scripts/*.py` to `scripts/legacy/`.
- `scripts/` now keeps only compact launchers and a local README.

## Why It Was Moved
- Reduce top-level clutter and keep active runtime/pipeline files easy to find.
- Preserve historical context without polluting active working directories.
- Separate active entrypoints from compatibility/legacy command shims.

## What Remains Active
- Runtime app code: `app/backend`, `app/frontend`
- Active pipeline entrypoints: `pipelines/email/*.py`, `pipelines/url/*.py`, `pipelines/joint/*.py`
- Compact optional launchers: `scripts/run_*_pipeline.py`
- Final reports: `reports/final/*`

## Compatibility
- Existing commands using `backend/` and `frontend/` continue to work via symlinks.
- Old script wrappers are preserved under `scripts/legacy/` for manual fallback.
