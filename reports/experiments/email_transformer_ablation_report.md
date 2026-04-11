# Email Transformer Ablation Report (TG-5.9)

Generated: 2026-04-09T17:07:37.217287+00:00

## 1. Overview
- Purpose: isolate contributions of transformer context, numeric fusion, freeze/unfreeze behavior, and threshold choice.
- Compared variants: fusion_frozen, fusion_unfrozen, textonly_frozen, textonly_unfrozen.

## 2. Dataset and Split Validity
- Rows: 6,992
- Label distribution: {0: 3992, 1: 3000}
- Source distribution: {'enron': 994, 'nazario': 2998, 'spamassassin': 3000}
- Numeric feature count: 9

| Split | Train Label Counts | Test Label Counts | Valid For Phishing Metrics | Note |
|---|---|---|---|---|
| random | `{0: 856, 1: 644}` | `{0: 799, 1: 600}` | True | valid |
| cross_source_a | `{0: 936, 1: 564}` | `{0: 750, 1: 750}` | True | valid |
| cross_source_b | `{0: 937, 1: 563}` | `{0: 749, 1: 751}` | True | valid |
| cross_source_c | `{0: 750, 1: 750}` | `{0: 994}` | False | invalid_single_class_test_set |

## 3. Variant Configuration
| Variant | Uses Numeric Features | Encoder Frozen | Epochs |
|---|---|---|---:|
| fusion_frozen | True | True | 3 |
| fusion_unfrozen | True | False | 2 |
| textonly_frozen | False | True | 3 |
| textonly_unfrozen | False | False | 2 |
- Unfrozen training cap: max 20 batches per epoch (CPU practicality constraint).

## 4. Main Metrics (Threshold=0.5)
| Variant | Split | Status | Accuracy | Precision | Recall | F1 | ROC-AUC |
|---|---|---|---:|---:|---:|---:|---:|
| fusion_frozen | random | ok | 0.8420 | 0.7858 | 0.8683 | 0.8250 | 0.9300 |
| fusion_frozen | cross_source_a | ok | 0.7660 | 0.9607 | 0.5547 | 0.7033 | 0.9346 |
| fusion_frozen | cross_source_b | ok | 0.8787 | 0.8375 | 0.9401 | 0.8858 | 0.9514 |
| fusion_frozen | cross_source_c | invalid_split | n/a | n/a | n/a | n/a | n/a |
| fusion_unfrozen | random | ok | 0.9292 | 0.9253 | 0.9083 | 0.9167 | 0.9810 |
| fusion_unfrozen | cross_source_a | ok | 0.7000 | 0.9688 | 0.4133 | 0.5794 | 0.9488 |
| fusion_unfrozen | cross_source_b | ok | 0.9293 | 0.8890 | 0.9814 | 0.9329 | 0.9874 |
| fusion_unfrozen | cross_source_c | invalid_split | n/a | n/a | n/a | n/a | n/a |
| textonly_frozen | random | ok | 0.8578 | 0.8089 | 0.8750 | 0.8407 | 0.9310 |
| textonly_frozen | cross_source_a | ok | 0.8113 | 0.9414 | 0.6640 | 0.7787 | 0.9296 |
| textonly_frozen | cross_source_b | ok | 0.8887 | 0.8687 | 0.9161 | 0.8918 | 0.9475 |
| textonly_frozen | cross_source_c | invalid_split | n/a | n/a | n/a | n/a | n/a |
| textonly_unfrozen | random | ok | 0.9299 | 0.9240 | 0.9117 | 0.9178 | 0.9812 |
| textonly_unfrozen | cross_source_a | ok | 0.7720 | 0.9679 | 0.5627 | 0.7116 | 0.9518 |
| textonly_unfrozen | cross_source_b | ok | 0.9153 | 0.9138 | 0.9174 | 0.9156 | 0.9657 |
| textonly_unfrozen | cross_source_c | invalid_split | n/a | n/a | n/a | n/a | n/a |

## 5. Threshold Comparison (0.2 / 0.5 / 0.8)
### cross_source_a
| Variant | Threshold | Precision | Recall | F1 |
|---|---:|---:|---:|---:|
| fusion_frozen | 0.2 | 0.5000 | 1.0000 | 0.6667 |
| fusion_frozen | 0.5 | 0.9607 | 0.5547 | 0.7033 |
| fusion_frozen | 0.8 | 0.0000 | 0.0000 | 0.0000 |
| fusion_unfrozen | 0.2 | 0.9475 | 0.6973 | 0.8034 |
| fusion_unfrozen | 0.5 | 0.9688 | 0.4133 | 0.5794 |
| fusion_unfrozen | 0.8 | 0.9688 | 0.2480 | 0.3949 |
| textonly_frozen | 0.2 | 0.5000 | 1.0000 | 0.6667 |
| textonly_frozen | 0.5 | 0.9414 | 0.6640 | 0.7787 |
| textonly_frozen | 0.8 | 0.0000 | 0.0000 | 0.0000 |
| textonly_unfrozen | 0.2 | 0.8841 | 0.8440 | 0.8636 |
| textonly_unfrozen | 0.5 | 0.9679 | 0.5627 | 0.7116 |
| textonly_unfrozen | 0.8 | 0.9788 | 0.3080 | 0.4686 |

### cross_source_b
| Variant | Threshold | Precision | Recall | F1 |
|---|---:|---:|---:|---:|
| fusion_frozen | 0.2 | 0.5007 | 1.0000 | 0.6673 |
| fusion_frozen | 0.5 | 0.8375 | 0.9401 | 0.8858 |
| fusion_frozen | 0.8 | 0.0000 | 0.0000 | 0.0000 |
| fusion_unfrozen | 0.2 | 0.5384 | 1.0000 | 0.6999 |
| fusion_unfrozen | 0.5 | 0.8890 | 0.9814 | 0.9329 |
| fusion_unfrozen | 0.8 | 0.9571 | 0.9214 | 0.9389 |
| textonly_frozen | 0.2 | 0.5007 | 1.0000 | 0.6673 |
| textonly_frozen | 0.5 | 0.8687 | 0.9161 | 0.8918 |
| textonly_frozen | 0.8 | 0.0000 | 0.0000 | 0.0000 |
| textonly_unfrozen | 0.2 | 0.7946 | 0.9840 | 0.8792 |
| textonly_unfrozen | 0.5 | 0.9138 | 0.9174 | 0.9156 |
| textonly_unfrozen | 0.8 | 0.9576 | 0.6618 | 0.7827 |

## 6. Fusion Value Analysis
- Compare fusion vs text-only under same freeze setting using A/B results.
- frozen: mean F1 delta (fusion - text-only) on A/B = -0.0407
- unfrozen: mean F1 delta (fusion - text-only) on A/B = -0.0574

## 7. Freeze vs Unfreeze Analysis
- Compare unfrozen vs frozen under same input mode (A/B).
- fusion: mean F1 delta (unfrozen - frozen) on A/B = -0.0384
- text-only: mean F1 delta (unfrozen - frozen) on A/B = -0.0216

## 8. Invalid Benchmark Analysis
- Cross-source C is limited/invalid for phishing generalization because its test set contains a single class only.
- Phishing-class precision/recall/F1/ROC-AUC are not comparable there.
- Recommended fix: construct a held-out Enron-like test set with both legitimate and phishing labels.

## 9. Key Findings (Research Questions)
- **Q1**: Unfreezing reduced fusion F1 on A/B by -0.0384 on average, so extra cost was not justified under current setup.
- **Q2**: Fusion minus text-only F1 on A/B: frozen=-0.0407 if available, unfrozen=-0.0574 if available. Numeric fusion reduced cross-source F1 versus text-only under this setup.
- **Q3**: Best random split variant by F1: textonly_unfrozen (0.9178).
- **Q4**: Best on A: textonly_frozen (0.7787); best on B: fusion_unfrozen (0.9329).
- **Q5**: Threshold behavior remains a major driver where ROC-AUC is high but decision metrics vary strongly: cross_source_a: ROC-AUC=0.9296, F1@0.2=0.6667, F1@0.5=0.7787, F1@0.8=0.0000; cross_source_b: ROC-AUC=0.9874, F1@0.2=0.6999, F1@0.5=0.9329, F1@0.8=0.9389
- **Q6**: Cross-source C is not a valid phishing generalization benchmark in current form because the test set is single-class (label 0 only).
- **Q7**: Next direction: fix evaluation by creating a label-balanced held-out benchmark for Enron-like domains, then optimize threshold-calibrated fusion (possibly temperature scaling + source-aware calibration).

## 10. Recommended Next TG
- Build a repaired cross-source benchmark with valid class balance for C-like evaluation.
- Add probability calibration per-source and re-run threshold policy analysis.
- Consider lightweight domain-adaptation regularization before larger model changes.

Total runtime: 5985.3 seconds
