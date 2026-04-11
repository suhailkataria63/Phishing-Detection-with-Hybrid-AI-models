#!/usr/bin/env python3
"""Train a first baseline email classifier using TF-IDF + Logistic Regression.

Input:
- data/processed/email_dataset_v1.csv

Outputs:
- models/email_baseline_tfidf_logreg.joblib
- reports/email_baseline_report.md
"""

from __future__ import annotations

import argparse
import os
from typing import Dict, Optional

import pandas as pd
from joblib import dump
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DATA_CSV = os.path.join(ROOT, "data", "processed", "email_dataset_v1.csv")
MODEL_OUT = os.path.join(ROOT, "models", "email_baseline_tfidf_logreg.joblib")
REPORT_OUT = os.path.join(ROOT, "reports", "email_baseline_report.md")

RANDOM_SEED = 1337
TEST_SIZE = 0.2


def build_text(subject: pd.Series, body: pd.Series) -> pd.Series:
    sub = subject.fillna("").astype(str).str.strip()
    bod = body.fillna("").astype(str).str.strip()
    text = (sub + " " + bod).str.strip()
    return text


def evaluate(
    y_true: pd.Series,
    y_pred,
    y_proba: Optional[pd.Series],
) -> Dict[str, Optional[float]]:
    metrics: Dict[str, Optional[float]] = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "roc_auc": None,
    }

    if y_proba is not None and y_true.nunique() > 1:
        metrics["roc_auc"] = float(roc_auc_score(y_true, y_proba))

    return metrics


def write_report(
    path: str,
    dataset_rel: str,
    train_size: int,
    test_size: int,
    label_counts: Dict[int, int],
    metrics: Dict[str, Optional[float]],
    cm,
    clf_report: str,
    max_features: int,
    min_df: int,
    ngram_max: int,
) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)

    lines = []
    lines.append("# Email Baseline Report")
    lines.append("")
    lines.append("## Setup")
    lines.append(f"- Dataset: `{dataset_rel}`")
    lines.append("- Text input: `subject + body`")
    lines.append("- Vectorizer: `TF-IDF`")
    lines.append("- Model: `LogisticRegression`")
    lines.append(f"- Train size: {train_size:,}")
    lines.append(f"- Test size: {test_size:,}")
    lines.append(f"- Label counts (full dataset): {label_counts}")
    lines.append(
        f"- TF-IDF params: max_features={max_features}, min_df={min_df}, ngram_range=(1,{ngram_max})"
    )
    lines.append("")

    lines.append("## Metrics")
    lines.append(f"- Accuracy: **{metrics['accuracy']:.4f}**")
    lines.append(f"- Precision: **{metrics['precision']:.4f}**")
    lines.append(f"- Recall: **{metrics['recall']:.4f}**")
    lines.append(f"- F1: **{metrics['f1']:.4f}**")
    if metrics["roc_auc"] is None:
        lines.append("- ROC-AUC: n/a")
    else:
        lines.append(f"- ROC-AUC: **{metrics['roc_auc']:.4f}**")
    lines.append("")

    lines.append("## Confusion Matrix")
    lines.append("Rows=true [0,1], Cols=pred [0,1]")
    lines.append("```")
    lines.append(str(cm))
    lines.append("```")
    lines.append("")

    lines.append("## Classification Report")
    lines.append("```")
    lines.append(clf_report.strip())
    lines.append("```")
    lines.append("")

    lines.append("## Notes")
    lines.append("- Label mapping: `0=legitimate`, `1=suspicious/phishing-like`.")
    lines.append("- This is a lexical baseline and may overfit dataset/source artifacts.")

    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Train baseline email TF-IDF + Logistic Regression model")
    parser.add_argument("--data", type=str, default=DATA_CSV, help="Input CSV path")
    parser.add_argument("--model-out", type=str, default=MODEL_OUT, help="Output model artifact")
    parser.add_argument("--report-out", type=str, default=REPORT_OUT, help="Output markdown report")
    parser.add_argument("--test-size", type=float, default=TEST_SIZE, help="Test split ratio")
    parser.add_argument("--seed", type=int, default=RANDOM_SEED, help="Random seed")
    parser.add_argument("--max-features", type=int, default=80000, help="TF-IDF max features")
    parser.add_argument("--min-df", type=int, default=2, help="TF-IDF min_df")
    parser.add_argument("--ngram-max", type=int, default=2, help="Max n-gram size (starting at 1)")
    args = parser.parse_args()

    os.makedirs(os.path.join(ROOT, "models"), exist_ok=True)
    os.makedirs(os.path.join(ROOT, "reports"), exist_ok=True)

    if not os.path.exists(args.data):
        raise FileNotFoundError(f"Missing dataset: {args.data}")

    df = pd.read_csv(args.data)
    required_cols = {"subject", "body", "label"}
    missing = sorted(required_cols - set(df.columns))
    if missing:
        raise ValueError(f"Dataset missing required columns: {missing}")

    df["label"] = pd.to_numeric(df["label"], errors="coerce")
    df = df.dropna(subset=["label"]).copy()
    df["label"] = df["label"].astype(int)
    df = df[df["label"].isin([0, 1])].copy()

    df["text"] = build_text(df["subject"], df["body"])
    df = df[df["text"].str.len() > 0].copy()

    if df["label"].nunique() < 2:
        raise ValueError("Need at least two label classes to train baseline model")

    label_counts = {int(k): int(v) for k, v in df["label"].value_counts().sort_index().items()}

    X_train, X_test, y_train, y_test = train_test_split(
        df["text"],
        df["label"],
        test_size=args.test_size,
        random_state=args.seed,
        stratify=df["label"],
    )

    pipeline = Pipeline(
        steps=[
            (
                "tfidf",
                TfidfVectorizer(
                    lowercase=True,
                    strip_accents="unicode",
                    ngram_range=(1, max(1, args.ngram_max)),
                    max_features=args.max_features,
                    min_df=max(1, args.min_df),
                    max_df=0.98,
                    sublinear_tf=True,
                ),
            ),
            (
                "clf",
                LogisticRegression(
                    solver="liblinear",
                    max_iter=2000,
                    class_weight="balanced",
                    random_state=args.seed,
                ),
            ),
        ]
    )

    pipeline.fit(X_train, y_train)

    y_pred = pipeline.predict(X_test)
    y_proba = None
    if hasattr(pipeline, "predict_proba"):
        y_proba = pipeline.predict_proba(X_test)[:, 1]

    metrics = evaluate(y_test, y_pred, y_proba)
    cm = confusion_matrix(y_test, y_pred)
    clf_report = classification_report(y_test, y_pred, digits=4)

    write_report(
        path=args.report_out,
        dataset_rel=os.path.relpath(args.data, ROOT),
        train_size=len(X_train),
        test_size=len(X_test),
        label_counts=label_counts,
        metrics=metrics,
        cm=cm,
        clf_report=clf_report,
        max_features=args.max_features,
        min_df=args.min_df,
        ngram_max=args.ngram_max,
    )

    dump(
        {
            "pipeline": pipeline,
            "version": "email_baseline_tfidf_logreg_v1",
            "label_mapping": {0: "legitimate", 1: "suspicious/phishing-like"},
            "seed": args.seed,
            "metrics": metrics,
        },
        args.model_out,
    )

    print("=== Email Baseline (TF-IDF + Logistic Regression) ===")
    print(f"Dataset: {os.path.relpath(args.data, ROOT)}")
    print(f"Train size: {len(X_train):,} | Test size: {len(X_test):,}")
    print(f"Accuracy:  {metrics['accuracy']:.4f}")
    print(f"Precision: {metrics['precision']:.4f}")
    print(f"Recall:    {metrics['recall']:.4f}")
    print(f"F1:        {metrics['f1']:.4f}")
    if metrics["roc_auc"] is None:
        print("ROC-AUC:   n/a")
    else:
        print(f"ROC-AUC:   {metrics['roc_auc']:.4f}")
    print(f"Saved model: {os.path.relpath(args.model_out, ROOT)}")
    print(f"Saved report: {os.path.relpath(args.report_out, ROOT)}")


if __name__ == "__main__":
    main()
