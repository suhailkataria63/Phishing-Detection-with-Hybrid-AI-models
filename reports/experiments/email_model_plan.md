# Email Model Plan (TG-5.7)

## Scope
- Purpose: prepare architecture scaffolding for an advanced email model path.
- This step is planning-only.
- No transformer model download is performed.
- No transformer training is executed.

## Expected Input Schema
Primary record schema (training + future inference contract):
- `subject` (string)
- `body` (string)
- `sender` (string, optional at inference)
- `sender_domain` (string, optional at inference)
- `urls` (list-like or serialized list)
- `text` (string): canonical text = `subject + [SEP] + body`
- `label` (int): `0=legitimate`, `1=suspicious/phishing-like`
- `source` (string)

Numeric signal columns planned for fusion:
- `url_count`
- `has_ip_url`
- `avg_url_length`
- `suspicious_tld_count`
- `shortener_count`
- `exclamation_count`
- `digit_ratio`
- `capital_ratio`
- `body_length`

## Planned Training Dataset Path
- `data/processed/email_dataset_v2_features.csv`

## Text Combination Strategy
- Build one canonical text field as: `subject + [SEP] + body`.
- `subject` captures short lure intent; `body` captures detailed context.
- Future tokenizer settings are expected to include deterministic truncation and max length.

## Planned Fusion Strategy (Later Step)
- Channel 1: transformer text probability from `subject + [SEP] + body`.
- Channel 2: numeric URL/email signals listed above.
- Candidate fusion methods:
- late weighted averaging after calibration
- logistic stacking over channel probabilities
- rule-gated overrides for explicit high-risk signals

## Planned Artifact Output Locations
- `models/email_transformer_model.pt`
- `models/email_transformer_scaler.joblib`
- `models/email_transformer_metadata.json`
- `reports/email_transformer_results.md`
- Optional threshold artifact (future): `reports/email_transformer_threshold_metrics.csv`

## Evaluation Plan Against Existing Baselines
Text-only baseline references:
- `reports/email_baseline_report.md`
- `reports/email_cross_source_eval.md`

Hybrid baseline references:
- `scripts/train_email_hybrid_baseline.py`
- `reports/email_hybrid_cross_source_eval.md`
- `reports/email_hybrid_threshold_report.md`

Required evaluation metrics:
- accuracy
- precision
- recall
- F1
- ROC-AUC (when valid)
- confusion matrix

Required evaluation slices:
- deterministic random split
- source-held-out A/B/C cross-source evaluation
- threshold sweep for security tuning

## Next Concrete Implementation Step (After TG-5.7)
1. Implement real training logic in `scripts/train_email_transformer.py` (currently dry-run only).
2. Load `email_dataset_v2_features.csv`, build transformer text channel, and add numeric-fusion head.
3. Train and save artifacts under the planned `models/` paths.
4. Generate `reports/email_transformer_results.md` with direct comparison vs:
- text-only baseline metrics
- hybrid baseline metrics
- cross-source and threshold behavior
