# Email Feature Portability Report (TG-5.10)

Generated: 2026-04-09T18:45:31.955933+00:00

## 1. Scope
- Goal: audit engineered numeric feature portability across Enron, Nazario, and SpamAssassin.
- Dataset: `data/processed/email_dataset_v2_features.csv`.
- Rows: 6,992
- Label counts: {0: 3992, 1: 3000}
- Source counts: {'enron': 994, 'nazario': 2998, 'spamassassin': 3000}
- Audited numeric features (9): ['url_count', 'has_ip_url', 'avg_url_length', 'suspicious_tld_count', 'shortener_count', 'exclamation_count', 'digit_ratio', 'capital_ratio', 'body_length']

## 2. Feature Distribution Drift Summary
Mean/std by source (excerpt):

| Feature | Source | Mean | Std |
|---|---|---:|---:|
| avg_url_length | enron | 7.4123 | 20.9139 |
| avg_url_length | nazario | 17.0462 | 42.5722 |
| avg_url_length | spamassassin | 30.0571 | 22.2727 |
| body_length | enron | 1911.3732 | 6726.3249 |
| body_length | nazario | 3534.8512 | 85380.0799 |
| body_length | spamassassin | 2176.9730 | 6375.1355 |
| capital_ratio | enron | 0.0851 | 0.0646 |
| capital_ratio | nazario | 0.0675 | 0.0522 |
| capital_ratio | spamassassin | 0.0705 | 0.0671 |
| digit_ratio | enron | 0.0354 | 0.0384 |
| digit_ratio | nazario | 0.0295 | 0.0418 |
| digit_ratio | spamassassin | 0.0297 | 0.0421 |
| exclamation_count | enron | 0.5885 | 2.0142 |
| exclamation_count | nazario | 0.8412 | 5.5581 |
| exclamation_count | spamassassin | 3.5073 | 10.2069 |
| has_ip_url | enron | 0.0050 | 0.0707 |
| has_ip_url | nazario | 0.0013 | 0.0365 |
| has_ip_url | spamassassin | 0.0343 | 0.1821 |
| shortener_count | enron | 0.0282 | 0.3159 |
| shortener_count | nazario | 0.0580 | 0.4562 |
| shortener_count | spamassassin | 0.1987 | 0.6970 |
| suspicious_tld_count | enron | 0.0000 | 0.0000 |
| suspicious_tld_count | nazario | 0.0000 | 0.0000 |
| suspicious_tld_count | spamassassin | 0.0000 | 0.0000 |
| url_count | enron | 0.6620 | 5.5406 |
| url_count | nazario | 1.2238 | 9.8402 |
| url_count | spamassassin | 2.1000 | 6.5937 |

Pairwise drift/association summary:

| Feature | abs(label corr) | source eta^2 | max pairwise KS | source leakage acc (single-feature) |
|---|---:|---:|---:|---:|
| avg_url_length | 0.1166 | 0.0608 | 0.5398 | 0.5747 |
| exclamation_count | 0.1483 | 0.0303 | 0.3718 | 0.5347 |
| shortener_count | 0.0335 | 0.0172 | 0.1216 | 0.4639 |
| has_ip_url | 0.1311 | 0.0161 | 0.0330 | 0.4439 |
| capital_ratio | 0.2109 | 0.0090 | 0.1762 | 0.3853 |
| url_count | 0.0512 | 0.0044 | 0.5387 | 0.5275 |
| digit_ratio | 0.0286 | 0.0024 | 0.1263 | 0.4224 |
| body_length | 0.0130 | 0.0002 | 0.2132 | 0.4325 |
| suspicious_tld_count | 0.0000 | 0.0000 | 0.0000 | 0.4289 |

## 3. Features Strongly Tied to Source

| Feature | source eta^2 | max KS | source leakage acc |
|---|---:|---:|---:|
| avg_url_length | 0.0608 | 0.5398 | 0.5747 |
| exclamation_count | 0.0303 | 0.3718 | 0.5347 |
| shortener_count | 0.0172 | 0.1216 | 0.4639 |
| has_ip_url | 0.0161 | 0.0330 | 0.4439 |
| capital_ratio | 0.0090 | 0.1762 | 0.3853 |

## 4. Features Weakly Tied to Label

| Feature | abs(label corr) | source eta^2 |
|---|---:|---:|
| suspicious_tld_count | 0.0000 | 0.0000 |
| body_length | 0.0130 | 0.0002 |
| digit_ratio | 0.0286 | 0.0024 |
| shortener_count | 0.0335 | 0.0172 |
| url_count | 0.0512 | 0.0044 |

## 5. Lightweight Ablation (TF-IDF text + one feature)
- Text-only reference F1: **0.9635**

| Feature | F1(text + feature) | Delta vs text-only |
|---|---:|---:|
| avg_url_length | 0.9651 | +0.0017 |
| capital_ratio | 0.9650 | +0.0015 |
| shortener_count | 0.9643 | +0.0009 |
| digit_ratio | 0.9643 | +0.0009 |
| body_length | 0.9643 | +0.0009 |
| has_ip_url | 0.9643 | +0.0008 |
| suspicious_tld_count | 0.9635 | +0.0000 |
| url_count | 0.9634 | -0.0001 |
| exclamation_count | 0.9633 | -0.0002 |

## 6. Conclusion
- Portability verdict: **NOT portable**.
- Top problematic features: ['avg_url_length', 'url_count', 'exclamation_count'].
- Numeric features are not portable across datasets due to distribution shift and source-specific patterns, which explains degradation in fusion models.
