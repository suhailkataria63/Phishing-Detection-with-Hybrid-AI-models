# Joint Detector Optimization Report

- Dataset: `data/eval/email_url_joint_test_dataset_v2.csv`
- Total rows: **200**
- Dev rows: **140**, Holdout test rows: **60**
- Joint label distribution (all): {0: 86, 1: 114} (0=legitimate,1=phishing)

## Threshold Selection (Dev)
| Model | Best Accuracy | Best F1 | Best Tradeoff |
|---|---:|---:|---:|
| email | 0.75 | 0.65 | 0.65 |
| url | 0.05 | 0.05 | 0.05 |
| joint_baseline | 0.45 | 0.45 | 0.45 |
| joint_rule_optimized | 0.55 | 0.55 | 0.55 |
| joint_meta | 0.30 | 0.30 | 0.30 |

## Metrics (Dev, using best tradeoff threshold)
| Model | Accuracy | Balanced Acc | Precision | Recall | F1 | ROC-AUC | Confusion Matrix |
|---|---:|---:|---:|---:|---:|---:|---|
| email | 0.650 | 0.641 | 0.602 | 0.944 | 0.735 | 0.635 | [[23, 45], [4, 68]] |
| url | 0.757 | 0.779 | 0.652 | 0.968 | 0.779 | 0.864 | [[46, 32], [2, 60]] |
| joint_baseline | 0.850 | 0.835 | 0.824 | 0.938 | 0.877 | 0.849 | [[44, 16], [5, 75]] |
| joint_rule_optimized | 0.943 | 0.942 | 0.950 | 0.950 | 0.950 | 0.968 | [[56, 4], [4, 76]] |
| joint_meta | 0.993 | 0.992 | 0.988 | 1.000 | 0.994 | 1.000 | [[59, 1], [0, 80]] |

## Metrics (Holdout Test, fixed thresholds from dev)
| Model | Accuracy | Balanced Acc | Precision | Recall | F1 | ROC-AUC | Confusion Matrix |
|---|---:|---:|---:|---:|---:|---:|---|
| email | 0.650 | 0.650 | 0.596 | 0.933 | 0.727 | 0.640 | [[11, 19], [2, 28]] |
| url | 0.833 | 0.839 | 0.744 | 1.000 | 0.853 | 0.831 | [[21, 10], [0, 29]] |
| joint_baseline | 0.850 | 0.836 | 0.821 | 0.941 | 0.877 | 0.852 | [[19, 7], [2, 32]] |
| joint_rule_optimized | 0.883 | 0.883 | 0.909 | 0.882 | 0.896 | 0.982 | [[23, 3], [4, 30]] |
| joint_meta | 0.967 | 0.966 | 0.971 | 0.971 | 0.971 | 0.998 | [[25, 1], [1, 33]] |

## Best Strategy
- Best holdout joint strategy by accuracy: **meta** (0.967)
- Compared variants:
  - baseline joint API
  - optimized rule-assisted joint
  - logistic-regression meta-classifier

## Error Analysis Summary (Test)
- Corrected by optimized rules: **6**
- Newly broken by optimized rules: **4**
- Detailed errors: `reports/joint_error_analysis.csv`

## Practical Notes
- Small synthetic dataset size can cause unstable split variance.
- Holdout metrics are reported separately to reduce tuning leakage.
- Real-world validation is still required before claiming production robustness.
