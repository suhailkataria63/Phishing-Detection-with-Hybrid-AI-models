# Joint Detector Optimization

## 1. Why TG-6.1 Plateaued Near ~82%
TG-6.1 improved single-holdout performance from baseline (~0.76) to rule-optimized (~0.82), but gains stalled because:
- The synthetic set was small (56 rows), so one split could be lucky or unstable.
- Hard negatives were underrepresented (legitimate security/password-reset style emails).
- Some clean-phish patterns and sender/brand mismatch conflicts were not fully encoded.
- A meta-classifier showed near-perfect scores, but likely overfit due small sample size.

## 2. What TG-6.2 Added

### 2.1 Dataset Expansion
Created:
- `data/eval/email_url_joint_test_dataset_v2.csv`
- `reports/experiments/email_url_joint_test_dataset_v2_summary.md`

Dataset v2 composition:
- Total: 200 cases
- Benign: 80
- Malicious: 80
- Edge/Hard: 40

All original rows were retained and new rows were appended.

### 2.2 New Hard-Negative and Clean-Phish Logic
Updated `backend/app/utils/joint_optimization.py` with:
- Trusted-domain and trusted-subdomain support (`accounts.google.com`, `meet.google.com`, `maps.google.com`, etc.).
- Sender-brand/domain consistency and mismatch penalties.
- Clean benign no-URL suppression.
- Legitimate security-alert suppression when trusted domain + sender consistency + low malicious intent.
- Clean-phish URL escalation (compound host + auth path/risk cues).
- Multi-URL conflict handling where malicious URL dominates benign URLs.
- High-intent malicious-text escalation even when URL looks official.

### 2.3 Metadata for Explainability
`/detect/joint` now returns additional optimization metadata flags:
- `trusted_domain_match`
- `brand_domain_mismatch`
- `no_url_benign_support`
- `suspicious_url_escalation`
- `strategy_version` (current: `optimized_v2`)

## 3. Robust Evaluation Method
Created:
- `scripts/evaluate_joint_detector_robustly.py`
- `reports/experiments/joint_detector_robust_metrics.csv`
- `reports/final/joint_detector_robust_eval_report.md`
- `reports/experiments/joint_detector_v2_error_analysis.csv`

Evaluation design:
- Repeated stratified train/dev/test splits (5 repeats).
- Compared:
  - `baseline`
  - `optimized` (production-safe rule-assisted)
  - `meta_experimental` (logistic meta-classifier)
- Thresholds evaluated each repeat:
  - `soc` (0.4)
  - `balanced` (0.5)
  - `high_confidence` (0.6)
  - `dev_optimized` (chosen on dev only)

## 4. Repeated-Split Results on Dataset v2
From `reports/final/joint_detector_robust_eval_report.md`:

- Baseline (`balanced`):
  - Accuracy: **0.770 ± 0.045**
  - F1: **0.796 ± 0.039**

- Optimized (`balanced`, production default):
  - Accuracy: **0.925 ± 0.031**
  - F1: **0.939 ± 0.025**

- Optimized (`high_confidence`):
  - Accuracy: **0.945 ± 0.041**
  - F1: **0.951 ± 0.037**

- Meta experimental:
  - Very high mean performance, but still treated as experimental due overfit risk on synthetic distributions.

## 5. Is 90%+ Stable?
For the production-safe optimized strategy:
- Yes, 90%+ is reached in repeated evaluation at `balanced`/`high_confidence` settings on dataset v2.
- This is a stronger claim than TG-6.1 because it is based on repeated splits, not a single holdout.

Still, this is synthetic data; external real-world validation remains required.

## 6. Production Decision
- Keep `joint_strategy=optimized` as default.
- Keep `joint_strategy=baseline|optimized` switch for rollback/testing.
- Keep `meta_experimental` out of production default path until broader validation.

## 7. Remaining Limitations
- Synthetic data can still encode authoring artifacts.
- Trusted-domain heuristics are curated and may miss unseen brands.
- Some scenarios (e.g., subtle doc-share variants) remain non-zero error sources.

## 8. Recommended Next Step
Evaluate TG-6.2 optimized rules on a larger, more realistic, source-diverse dataset with external domains and unseen writing styles before production hardening claims.
