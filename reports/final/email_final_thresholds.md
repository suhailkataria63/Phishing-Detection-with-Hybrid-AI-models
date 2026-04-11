# Email Final Threshold Summary

Selected final model: DistilBERT text-only frozen encoder.

| Threshold | Precision | Recall | F1 |
|---:|---:|---:|---:|
| 0.2 | 0.5942 | 0.9933 | 0.7436 |
| 0.5 | 0.8932 | 0.8917 | 0.8924 |
| 0.8 | 0.9804 | 0.5850 | 0.7328 |

Recommendation:
- low threshold (0.2-0.3) for high-recall SOC detection
- high threshold (0.7-0.8) for high-confidence alerts
