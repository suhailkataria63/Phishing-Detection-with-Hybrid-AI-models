# Email Baseline Report

## Setup
- Dataset: `data/processed/email_dataset_v1.csv`
- Text input: `subject + body`
- Vectorizer: `TF-IDF`
- Model: `LogisticRegression`
- Train size: 5,593
- Test size: 1,399
- Label counts (full dataset): {0: 3992, 1: 3000}
- TF-IDF params: max_features=80000, min_df=2, ngram_range=(1,2)

## Metrics
- Accuracy: **0.9685**
- Precision: **0.9603**
- Recall: **0.9667**
- F1: **0.9635**
- ROC-AUC: **0.9950**

## Confusion Matrix
Rows=true [0,1], Cols=pred [0,1]
```
[[775  24]
 [ 20 580]]
```

## Classification Report
```
precision    recall  f1-score   support

           0     0.9748    0.9700    0.9724       799
           1     0.9603    0.9667    0.9635       600

    accuracy                         0.9685      1399
   macro avg     0.9676    0.9683    0.9679      1399
weighted avg     0.9686    0.9685    0.9686      1399
```

## Notes
- Label mapping: `0=legitimate`, `1=suspicious/phishing-like`.
- This is a lexical baseline and may overfit dataset/source artifacts.
