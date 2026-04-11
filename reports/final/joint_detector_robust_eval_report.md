# Joint Detector Robust Evaluation Report (TG-6.2)

- Dataset: `data/eval/email_url_joint_test_dataset_v2.csv`
- Total rows: **200**
- Repeats: **5**
- Category composition: `{'malicious': 80, 'benign': 80, 'edge_case': 40}`
- Joint label distribution: `{0: 86, 1: 114}` (0=legitimate,1=phishing)

## Mean ± Std Metrics Across Repeats

| Strategy | Threshold | Accuracy | Precision | Recall | F1 | ROC-AUC |
|---|---|---:|---:|---:|---:|---:|
| baseline | balanced | 0.770 ± 0.045 | 0.814 ± 0.059 | 0.783 ± 0.053 | 0.796 ± 0.039 | 0.868 ± 0.064 |
| baseline | dev_optimized | 0.805 ± 0.091 | 0.789 ± 0.113 | 0.939 ± 0.050 | 0.851 ± 0.053 | 0.868 ± 0.064 |
| baseline | high_confidence | 0.665 ± 0.068 | 0.906 ± 0.093 | 0.470 ± 0.104 | 0.613 ± 0.097 | 0.868 ± 0.064 |
| baseline | soc | 0.765 ± 0.058 | 0.721 ± 0.037 | 0.965 ± 0.057 | 0.825 ± 0.044 | 0.868 ± 0.064 |
| meta_experimental | balanced | 0.970 ± 0.021 | 0.975 ± 0.023 | 0.974 ± 0.039 | 0.974 ± 0.019 | 0.998 ± 0.002 |
| meta_experimental | dev_optimized | 0.970 ± 0.021 | 0.967 ± 0.034 | 0.983 ± 0.039 | 0.974 ± 0.018 | 0.998 ± 0.002 |
| meta_experimental | high_confidence | 0.985 ± 0.022 | 1.000 ± 0.000 | 0.974 ± 0.039 | 0.986 ± 0.020 | 0.998 ± 0.002 |
| meta_experimental | soc | 0.965 ± 0.014 | 0.966 ± 0.019 | 0.974 ± 0.039 | 0.969 ± 0.013 | 0.998 ± 0.002 |
| optimized | balanced | 0.925 ± 0.031 | 0.892 ± 0.040 | 0.991 ± 0.019 | 0.939 ± 0.025 | 0.984 ± 0.020 |
| optimized | dev_optimized | 0.920 ± 0.054 | 0.918 ± 0.087 | 0.957 ± 0.053 | 0.934 ± 0.042 | 0.984 ± 0.020 |
| optimized | high_confidence | 0.945 ± 0.041 | 0.965 ± 0.036 | 0.939 ± 0.058 | 0.951 ± 0.037 | 0.984 ± 0.020 |
| optimized | soc | 0.895 ± 0.045 | 0.854 ± 0.058 | 0.991 ± 0.019 | 0.917 ± 0.033 | 0.984 ± 0.020 |

## Stability Notes
- Optimized strategy outperformed baseline on balanced-threshold accuracy in **5/5** repeats.
- `meta_experimental` is reported for research only and not set as production default.

## Top False-Positive Scenarios (optimized, balanced)
- banking_alert_official: 4
- travel_confirmation_variant: 3
- multi_url_benign: 2
- bank_notification_variant: 1
- student_portal: 1

## Top False-Negative Scenarios (optimized, balanced)
- subtle_doc_share: 1

## Interpretation
- Repeated-split evaluation reduces single-holdout luck and gives mean+variance estimates.
- If 0.90+ appears only in isolated splits or only for meta model, treat it as unstable/overfit.
- For production-safe operation, prioritize the optimized rule-assisted strategy with stable gains.
