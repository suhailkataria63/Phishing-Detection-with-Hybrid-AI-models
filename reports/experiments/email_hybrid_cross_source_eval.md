# Email Hybrid Cross-Source Evaluation

## Setup
- Dataset: `data/processed/email_dataset_v2_features.csv`
- Pipeline: `TF-IDF(text) + StandardScaler(numeric) + LogisticRegression`
- Text column: `text`
- Numeric columns: ['url_count', 'has_ip_url', 'avg_url_length', 'suspicious_tld_count', 'shortener_count', 'exclamation_count', 'digit_ratio', 'capital_ratio', 'body_length']
- TF-IDF params: max_features=80000, ngram_range=(1,2), lowercase=True, strip_accents=unicode, sublinear_tf=True
- Classifier params: solver=liblinear, max_iter=2000, class_weight=balanced

## Experiment A: Train Enron+Nazario, Test SpamAssassin
- Train sources: enron, nazario | Test source: spamassassin
- Train size: 3,992 | Test size: 3,000
- Train label counts: {0: 2492, 1: 1500}
- Test label counts: {0: 1500, 1: 1500}

### Metrics
- Accuracy: **0.5543**
- Precision: **0.9880**
- Recall: **0.1100**
- F1: **0.1980**
- ROC-AUC: **0.9181**

### Confusion Matrix
Rows=true [0,1], Cols=pred [0,1]
```
[[1498, 2], [1335, 165]]
```

### Interpretation
- Recall/F1 improved vs text-only baseline (recall 0.0680 -> 0.1100, F1 0.1273 -> 0.1980).

## Experiment B: Train Enron+SpamAssassin, Test Nazario
- Train sources: enron, spamassassin | Test source: nazario
- Train size: 3,994 | Test size: 2,998
- Train label counts: {0: 2494, 1: 1500}
- Test label counts: {0: 1498, 1: 1500}

### Metrics
- Accuracy: **0.7799**
- Precision: **0.9242**
- Recall: **0.6100**
- F1: **0.7349**
- ROC-AUC: **0.9412**

### Confusion Matrix
Rows=true [0,1], Cols=pred [0,1]
```
[[1423, 75], [585, 915]]
```

### Interpretation
- Recall/F1 regressed vs text-only baseline (recall 0.7033 -> 0.6100, F1 0.8044 -> 0.7349).

## Experiment C: Train Nazario+SpamAssassin, Test Enron
- Train sources: nazario, spamassassin | Test source: enron
- Train size: 5,998 | Test size: 994
- Train label counts: {0: 2998, 1: 3000}
- Test label counts: {0: 994}

### Metrics
- Accuracy: **0.8571**
- Precision: **0.0000**
- Recall: **0.0000**
- F1: **0.0000**
- ROC-AUC: n/a (single-class test set)

### Confusion Matrix
Rows=true [0,1], Cols=pred [0,1]
```
[[852, 142], [0, 0]]
```

### Interpretation
- Recall/F1 are broadly unchanged vs text-only baseline (recall 0.0000 -> 0.0000, F1 0.0000 -> 0.0000).

## Comparison vs Text-Only Cross-Source Results
- Experiment A: Recall improved (0.0680 -> 0.1100, delta +0.0420); F1 improved (0.1273 -> 0.1980, delta +0.0707).
- Experiment B: Recall decreased (0.7033 -> 0.6100, delta -0.0933); F1 decreased (0.8044 -> 0.7349, delta -0.0695).
- Experiment C: Recall unchanged (0.0000 -> 0.0000, delta +0.0000); F1 unchanged (0.0000 -> 0.0000, delta +0.0000).
