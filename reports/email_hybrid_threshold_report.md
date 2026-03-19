# Email Hybrid Threshold Report

## Setup
- Dataset: `data/processed/email_dataset_v2_features.csv`
- Train size: 5,593
- Test size: 1,399
- Label counts (full dataset): {0: 3992, 1: 3000}
- Model: TF-IDF(text) + StandardScaler(numeric) + LogisticRegression
- Split: deterministic train/test with random_state=1337, stratified by label
- ROC-AUC (test probabilities): **0.9922**

## Threshold Metrics
| Threshold | Precision | Recall | F1 | False Positives | False Negatives |
|---:|---:|---:|---:|---:|---:|
| 0.2 | 0.8070 | 0.9967 | 0.8919 | 143 | 2 |
| 0.3 | 0.8897 | 0.9950 | 0.9394 | 74 | 3 |
| 0.4 | 0.9405 | 0.9750 | 0.9574 | 37 | 15 |
| 0.5 | 0.9695 | 0.9533 | 0.9613 | 18 | 28 |
| 0.6 | 0.9826 | 0.9400 | 0.9608 | 10 | 36 |
| 0.7 | 0.9873 | 0.9100 | 0.9471 | 7 | 54 |
| 0.8 | 0.9918 | 0.8100 | 0.8917 | 4 | 114 |

## Recommendation
- High-recall phishing detection: threshold **0.2** (recall=0.9967, precision=0.8070, F1=0.8919).
- High-precision alerting: threshold **0.8** (precision=0.9918, recall=0.8100, F1=0.8917).
- Operational note: lower thresholds reduce false negatives but increase false positives; higher thresholds do the opposite.
