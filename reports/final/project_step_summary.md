# Project Step Summary (Append-Only)

This log is maintained as an append-friendly project history.  
Scope covered here: TG-1.0 through TG-6.0.

## TG-1.0 — URL Parsing Consolidation
### What was done
- Centralized URL normalization, parsing, hostname extraction, and domain extraction into shared utilities.
- Refactored duplicated URL parsing paths in backend URL inference stack to reuse shared helpers.

### Why it was done
- Reduce parsing inconsistencies and make URL handling testable and maintainable.

### Key result
- Unified backend URL parsing behavior with defensive error handling and shared utility functions.

### Insight
- Centralization improved reliability and reduced hidden divergence across URL model components.

## TG-1.1 — URL/Domain Utility Tests
### What was done
- Added focused tests for normalization, hostname extraction, registrable domain extraction, subdomain extraction, IP host detection, and malformed input handling.

### Why it was done
- Lock expected parsing behavior before adding higher-risk hardening logic.

### Key result
- Utility behavior became regression-protected for common legitimate/suspicious URL cases.

### Insight
- Solid parsing tests were foundational for later trusted-domain and confusable logic.

## TG-2.0 — Trusted-Domain and Fake-Brand Hardening
### What was done
- Moved trusted-domain logic toward shared helpers and refactored hybrid URL checks to use them.
- Added protections so exact trusted registrable domains are not falsely flagged as fake-brand.

### Why it was done
- Reduce false positives on legitimate brands while preserving lookalike detection.

### Key result
- Clearer distinction between exact trusted domains, trusted ecosystem domains, and suspicious lookalikes.

### Insight
- Trust logic must explicitly model domain hierarchy; string similarity alone is insufficient.

## TG-2.1 — Typosquat Regression Guard
### What was done
- Added regression coverage for an obvious typosquat (`paypa1.com`) to ensure untrusted classification and fake-brand reasoning.

### Why it was done
- Validate that trusted-domain protections do not suppress real impersonation catches.

### Key result
- Typosquat catch remained intact while trusted URLs stayed protected.

### Insight
- Every false-positive reduction step needs paired regression tests for true positives.

## TG-3.0 — Homoglyph/Confusable Hardening
### What was done
- Added lightweight unicode/IDN-aware confusable handling for domain lookalike checks.
- Integrated confusable cues into hybrid URL reasoning with trusted-domain exemptions.

### Why it was done
- Extend beyond ASCII edit-distance detection into visual impersonation cases.

### Key result
- Confusable lookalike detection improved while preserving trusted exact-domain exemptions.

### Insight
- Confusable logic is high value when narrowly scoped and exempting exact trusted domains.

## TG-4.0 — URL Hardening Evaluation
### What was done
- Built curated URL evaluation cases and a lightweight evaluation workflow/report.
- Assessed trusted, suspicious, typosquat, and confusable classes with reason quality checks.

### Why it was done
- Validate hardening impact before shifting focus to email detection.

### Key result
- Strong trusted/typosquat/confusable behavior; weaker detection remained for some phishing-style URLs.

### Insight
- Lexical redirect/IP-path patterns required stronger signals despite trust hardening gains.

## TG-4.5 — Suspicious URL Patch
### What was done
- Added targeted backend logic for weak cases:
- IP-host URLs with sensitive paths.
- Embedded redirect targets in query parameters.
- Untrusted-domain lure-style lexical patterns.

### Why it was done
- Improve suspicious phishing-style recall without retraining or API shape changes.

### Key result
- Previously weak cases improved while trusted protections were retained.

### Insight
- Small rule-based augmentations can recover clear misses before model retraining.

## TG-5.1 — Email Dataset Ingestion Planning
### What was done
- Inspected Enron, Nazario, and SpamAssassin raw sources and documented parsing requirements.
- Defined unified processed schema: subject, body, sender, sender_domain, urls, label, source.

### Why it was done
- Avoid blind ingestion; align source-specific parsing/label assumptions before building dataset.

### Key result
- Clear ingestion plan and label mapping strategy established.

### Insight
- Source heterogeneity required explicit parser contracts and sanity checks per dataset.

## TG-5.2 — Unified Email Dataset Builder
### What was done
- Implemented `scripts/build_email_dataset.py` for Enron/Nazario/SpamAssassin ingestion, URL extraction, sender-domain extraction, deduplication, and stats export.
- Generated `data/processed/email_dataset_v1.csv` and `reports/email_dataset_v1_stats.md`.

### Why it was done
- Create the first reproducible labeled dataset for baseline email modeling.

### Key result
- Practical v1 dataset built and documented with source/label counts.

### Insight
- Parser robustness and normalization choices materially affect downstream model quality.

## TG-5.2b — Dataset Validation and Balance Controls
### What was done
- Validated sample quality across source/label pairs.
- Added optional balancing/sampling controls for deterministic dataset construction.

### Why it was done
- Confirm label sanity (especially Nazario polarity) and ensure controllable training distribution.

### Key result
- Dataset quality deemed usable for baseline modeling with reproducible sampling controls.

### Insight
- Early sample-level QA prevented silent label or parsing errors from propagating.

## TG-5.3 — Text-Only Baseline Model
### What was done
- Implemented TF-IDF + Logistic Regression baseline training pipeline.

### Why it was done
- Establish a strong classical baseline before advanced architectures.

### Key result
- Random split metrics: Accuracy 0.9685, Precision 0.9603, Recall 0.9667, F1 0.9635, ROC-AUC 0.9950.

### Insight
- In-domain random split looked very strong but likely included source-style shortcuts.

## TG-5.4 — Cross-Source Baseline Evaluation
### What was done
- Ran source-held-out experiments A/B/C for text-only baseline.

### Why it was done
- Measure generalization beyond mixed random splits.

### Key result
- A F1 0.1273 (very low recall), B F1 0.8044, C invalid for phishing generalization (single-class test).

### Insight
- Cross-source shift was severe; random split performance overstated robustness.

## TG-5.5 — Hybrid Baseline (Text + Engineered Features)
### What was done
- Trained TF-IDF + numeric-feature hybrid logistic baseline on v2 features.

### Why it was done
- Test whether structured URL/email cues improve robustness.

### Key result
- Mixed cross-source effect: A improved vs text-only, B regressed; no consistent generalization gain.

### Insight
- Engineered features helped selectively but also encoded source-specific artifacts.

## TG-5.6 — Hybrid Threshold Analysis
### What was done
- Added threshold sweeps and probability diagnostics for hybrid model.

### Why it was done
- Separate ranking quality from decision-threshold behavior for security operations.

### Key result
- Lower thresholds improved recall; higher thresholds improved precision.

### Insight
- Threshold policy materially changed operational utility even when model ranking was stable.

## TG-5.7 — Transformer Pipeline Planning
### What was done
- Added transformer training scaffold (dry-run), architecture plan, and backend inference prep scaffold.

### Why it was done
- Define implementation contract before costly training.

### Key result
- Clear design for subject+body transformer input, artifacts, and evaluation path.

### Insight
- Early architecture docs reduced integration risk for TG-5.8 onward.

## TG-5.8 — Transformer + Numeric Fusion Training
### What was done
- Implemented full DistilBERT hybrid training/evaluation with random + cross-source + threshold reporting.

### Why it was done
- Evaluate contextual encoding + engineered feature fusion.

### Key result
- Random split F1 0.8895, ROC-AUC 0.9672.
- Cross-source: A F1 0.5332, B F1 0.9110, C invalid for phishing-class comparison.

### Insight
- Transformer improved difficult cross-source regimes, but threshold sensitivity remained high.

## TG-5.9 — Ablation and Evaluation Repair
### What was done
- Compared four variants: fusion/text-only × frozen/unfrozen.
- Added explicit invalid-split handling for single-class test sets.

### Why it was done
- Isolate contribution of fusion, unfreezing, and thresholds.

### Key result
- Best random: textonly_unfrozen (F1 0.9178).
- Best A: textonly_frozen (F1 0.7787).
- Best B: fusion_unfrozen (F1 0.9329).
- C explicitly marked invalid.

### Insight
- Unfreezing and fusion were not uniformly beneficial; robustness gains were split-dependent.

## TG-5.10 — Feature Portability Audit
### What was done
- Implemented distribution drift, source leakage, feature-label association, and lightweight single-feature ablation audit.
- Generated `reports/email_feature_portability_report.md`.

### Why it was done
- Explain why engineered features did not generalize consistently.

### Key result
- Portability verdict: **NOT portable**.
- Top problematic features: `avg_url_length`, `url_count`, `exclamation_count`.

### Insight
- Numeric features showed source-specific patterns and weak incremental value on top of strong text signals.

## TG-6.0 — Final Model Selection and Packaging
### What was done
- Selected final model: DistilBERT text-only, frozen encoder.
- Implemented `scripts/train_email_final_model.py` and produced deployment artifacts:
- `models/email_final_model.pt`
- `models/email_final_tokenizer/`
- `models/email_final_metadata.json`
- Produced `reports/email_final_model_report.md` and `reports/email_final_thresholds.md`.

### Why it was done
- Finalize a deployment-ready model with robust cost/performance characteristics.

### Key result
- Random split: F1 0.8924, ROC-AUC 0.9634.
- Cross-source A/B (selected model): F1 0.5336 / 0.9125.
- Threshold guidance formalized: low 0.2-0.3 for recall, high 0.7-0.8 for precision.

### Insight
- Frozen text-only DistilBERT provided the best practical robustness-cost packaging point.


## TG-6.1 — Joint Rule-Assisted Optimization (Initial)
### What was done
- Added first-pass rule-assisted joint optimization and heuristic feature extraction for sender/domain consistency, URL suspicion cues, and benign-text dampening.
- Built optimization evaluation pipeline with dev/holdout split and threshold sweeps.
- Integrated `joint_strategy=baseline|optimized` switch into joint API flow.

### Why it was done
- Baseline joint scoring was better than individual channels but still left meaningful false positives/false negatives.

### Key result
- Single-holdout improvement from baseline accuracy ~0.7647 to rule-optimized ~0.8235.

### Insight
- Explainable rules helped materially, but one holdout split and a small synthetic set were not enough for stability claims.

## TG-6.2 — Dataset v2 Expansion + Robust Repeated Evaluation
### What was done
- Expanded synthetic evaluation set to `data/eval/email_url_joint_test_dataset_v2.csv` (200 rows: 80 benign / 80 malicious / 40 edge).
- Added hard-negative benign coverage, clean-phish malicious coverage, and mixed/conflict scenarios.
- Strengthened production-safe rule-assisted logic:
- trusted-domain/subdomain support
- sender-brand/domain mismatch penalties
- clean benign no-URL suppression
- legitimate security-alert suppression
- clean-phish URL escalation
- multi-URL conflict dominance
- Added robust repeated-split evaluator (`scripts/evaluate_joint_detector_robustly.py`) and generated stable mean/std reports.

### Why it was done
- Reduce overfitting risk from small single-holdout testing and verify whether optimization gains are stable.

### Key result
- Repeated-split (5 repeats) mean metrics on dataset v2:
- baseline balanced accuracy: 0.770 ± 0.045
- optimized balanced accuracy: 0.925 ± 0.031
- optimized high-confidence accuracy: 0.945 ± 0.041
- Optimized outperformed baseline in 5/5 repeats at balanced threshold.

### Insight
- Rule-assisted optimization can reach stable 90%+ performance on synthetic benchmark v2 when evaluation is done with repeated splits and hard-negative coverage.

## Repo Cleanup / Compaction Refactor
### What was done
- Reorganized runtime app into `app/backend` and `app/frontend` with compatibility symlinks at root (`backend`, `frontend`).
- Consolidated scripts under `pipelines/email`, `pipelines/url`, and `pipelines/joint`, with legacy implementations under `pipelines/*/legacy`.
- Kept compatibility wrappers in `scripts/` so prior commands continue to work.
- Reorganized reports into `reports/final`, `reports/experiments`, and `reports/archive`.
- Reorganized model artifacts into `models/email`, `models/url`, `models/joint` with legacy symlink compatibility.
- Added `data/samples` and moved calibration sample assets there.
- Archived deprecated artifacts to `archive/deprecated_artifacts` and documented moves in `archive/ARCHIVE_NOTES.md`.

### Why it was done
- Reduce repository clutter, separate active entrypoints from historical artifacts, and make long-term maintenance easier.

### Key result
- Cleaner, domain-based structure with stable backward compatibility for existing run commands and backend startup.

### Insight
- Safe compaction works best with compatibility layers (symlinks/wrappers) so team workflows stay uninterrupted while structure improves.

## Wrapper Minimization Cleanup
### What was done
- Moved thin compatibility wrappers out of top-level `scripts/` into `scripts/legacy/`.
- Kept `scripts/` intentionally minimal with three compact launchers:
- `run_email_pipeline.py`
- `run_url_pipeline.py`
- `run_joint_pipeline.py`
- Added `scripts/README.md` to document active usage and legacy wrapper location.
- Removed stale `scripts/__pycache__/` clutter.

### Why it was done
- The previous wrapper-heavy layout still looked crowded in IDE explorer even after pipeline consolidation.

### Key result
- Top-level `scripts/` is now reduced to a small, readable launcher surface while legacy wrappers remain preserved under `scripts/legacy/`.

### Insight
- A compact launcher layer plus a dedicated `legacy/` folder keeps usability high without visual clutter.
