# Email Final Model Report (TG-6.0)

Generated: 2026-04-09T18:44:17.617131+00:00

## 1. Model Choice Rationale
- Selected model: DistilBERT text-only with frozen encoder.
- Rationale: strongest robustness-cost tradeoff from TG-5.9, while numeric fusion and unfreezing did not consistently improve cross-source F1.
- Operationally safer: frozen encoder is faster and more stable for repeatable packaging.

## 2. Dataset Summary
- Rows: 6,992
- Label distribution: {0: 3992, 1: 3000}
- Source distribution: {'enron': 994, 'nazario': 2998, 'spamassassin': 3000}

## 3. Random Split Metrics (Deployment Candidate)
- Train size: 5,593 | Test size: 1,399
- Train label counts: {0: 3193, 1: 2400}
- Test label counts: {0: 799, 1: 600}
- Accuracy: **0.9078**
- Precision: **0.8932**
- Recall: **0.8917**
- F1: **0.8924**
- ROC-AUC: **0.9634**
- Confusion matrix: `[[735, 64], [65, 535]]`

## 4. Cross-Source A/B Results (Selected Final Model)
- A (Train Enron+Nazario, Test SpamAssassin): F1=0.5336, Precision=0.9701, Recall=0.3680, ROC-AUC=0.9202
- B (Train Enron+SpamAssassin, Test Nazario): F1=0.9125, Precision=0.9212, Recall=0.9040, ROC-AUC=0.9673

### Reference to TG-5.9 Best Variant Logic
- Best variant on A (TG-5.9 run): `textonly_frozen` (F1=0.7787, Precision=0.9414, Recall=0.6640).
- Best variant on B (TG-5.9 run): `fusion_unfrozen` (F1=0.9329, Precision=0.8890, Recall=0.9814).

## 5. Threshold Behavior (Random Split)
| Threshold | Precision | Recall | F1 |
|---:|---:|---:|---:|
| 0.2 | 0.5942 | 0.9933 | 0.7436 |
| 0.5 | 0.8932 | 0.8917 | 0.8924 |
| 0.8 | 0.9804 | 0.5850 | 0.7328 |

## 6. Deployment Recommendation
- Use this packaged frozen text-only DistilBERT as the default production candidate.
- SOC/high-recall triage: threshold 0.2-0.3.
- High-confidence blocking/alerting: threshold 0.7-0.8.
- Keep source-held-out monitoring enabled; A/B drift remains non-trivial.
