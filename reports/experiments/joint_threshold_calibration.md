# Joint Threshold Calibration

Cases: 12

| Mode | Threshold | Accuracy | Precision | Recall | F1 | FP | FN |
|---|---:|---:|---:|---:|---:|---:|---:|
| soc | 0.40 | 0.750 | 0.667 | 1.000 | 0.800 | 3 | 0 |
| balanced | 0.50 | 0.833 | 0.750 | 1.000 | 0.857 | 2 | 0 |
| high_confidence | 0.60 | 0.750 | 0.714 | 0.833 | 0.769 | 2 | 1 |

Recommended operating modes:
- `soc` (`~0.4`): highest recall for triage-heavy SOC workflows.
- `balanced` (`0.5`): default production tradeoff.
- `high_confidence` (`0.6+`): fewer false positives for strict alerting.
