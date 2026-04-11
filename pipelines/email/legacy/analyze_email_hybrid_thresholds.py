#!/usr/bin/env python3
"""Threshold analysis for hybrid email baseline model.

Outputs:
- reports/email_hybrid_threshold_report.md
- reports/email_hybrid_threshold_metrics.csv
"""

from __future__ import annotations

import argparse
import csv
import os
from typing import Dict, List, Sequence

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DATA_CSV = os.path.join(ROOT, "data", "processed", "email_dataset_v2_features.csv")
REPORT_MD = os.path.join(ROOT, "reports", "email_hybrid_threshold_report.md")
REPORT_CSV = os.path.join(ROOT, "reports", "email_hybrid_threshold_metrics.csv")

RANDOM_SEED = 1337
TEST_SIZE = 0.2

TEXT_COLUMN = "text"
NUMERIC_COLUMNS = [
    "url_count",
    "has_ip_url",
    "avg_url_length",
    "suspicious_tld_count",
    "shortener_count",
    "exclamation_count",
    "digit_ratio",
    "capital_ratio",
    "body_length",
]
THRESHOLDS = [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]


def make_pipeline() -> Pipeline:
    preprocessor = ColumnTransformer(
        transformers=[
            (
                "text",
                TfidfVectorizer(
                    max_features=80000,
                    ngram_range=(1, 2),
                    lowercase=True,
                    strip_accents="unicode",
                    sublinear_tf=True,
                ),
                TEXT_COLUMN,
            ),
            ("numeric", StandardScaler(), NUMERIC_COLUMNS),
        ]
    )

    return Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            (
                "classifier",
                LogisticRegression(
                    solver="liblinear",
                    max_iter=2000,
                    class_weight="balanced",
                    random_state=RANDOM_SEED,
                ),
            ),
        ]
    )


def evaluate_thresholds(
    y_true: pd.Series,
    probs,
    thresholds: Sequence[float],
) -> List[Dict[str, float]]:
    rows: List[Dict[str, float]] = []

    for thr in thresholds:
        preds = (probs >= thr).astype(int)
        precision = precision_score(y_true, preds, zero_division=0)
        recall = recall_score(y_true, preds, zero_division=0)
        f1 = f1_score(y_true, preds, zero_division=0)
        tn, fp, fn, tp = confusion_matrix(y_true, preds, labels=[0, 1]).ravel()
        rows.append(
            {
                "threshold": float(thr),
                "precision": float(precision),
                "recall": float(recall),
                "f1": float(f1),
                "false_positives": int(fp),
                "false_negatives": int(fn),
                "true_positives": int(tp),
                "true_negatives": int(tn),
            }
        )
    return rows


def pick_recommendations(rows: Sequence[Dict[str, float]]) -> Dict[str, Dict[str, float]]:
    # High recall recommendation: maximize recall, then F1, then precision.
    high_recall = max(
        rows,
        key=lambda r: (r["recall"], r["f1"], r["precision"]),
    )
    # High precision recommendation: maximize precision, then F1, then recall.
    high_precision = max(
        rows,
        key=lambda r: (r["precision"], r["f1"], r["recall"]),
    )
    return {"high_recall": high_recall, "high_precision": high_precision}


def write_csv(path: str, rows: Sequence[Dict[str, float]]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fieldnames = [
        "threshold",
        "precision",
        "recall",
        "f1",
        "false_positives",
        "false_negatives",
        "true_positives",
        "true_negatives",
    ]
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_markdown(
    path: str,
    dataset_rel: str,
    train_size: int,
    test_size: int,
    label_counts: Dict[int, int],
    roc_auc: float,
    rows: Sequence[Dict[str, float]],
    recommendations: Dict[str, Dict[str, float]],
) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)

    lines: List[str] = []
    lines.append("# Email Hybrid Threshold Report")
    lines.append("")
    lines.append("## Setup")
    lines.append(f"- Dataset: `{dataset_rel}`")
    lines.append(f"- Train size: {train_size:,}")
    lines.append(f"- Test size: {test_size:,}")
    lines.append(f"- Label counts (full dataset): {label_counts}")
    lines.append("- Model: TF-IDF(text) + StandardScaler(numeric) + LogisticRegression")
    lines.append("- Split: deterministic train/test with random_state=1337, stratified by label")
    lines.append(f"- ROC-AUC (test probabilities): **{roc_auc:.4f}**")
    lines.append("")

    lines.append("## Threshold Metrics")
    lines.append("| Threshold | Precision | Recall | F1 | False Positives | False Negatives |")
    lines.append("|---:|---:|---:|---:|---:|---:|")
    for r in rows:
        lines.append(
            f"| {r['threshold']:.1f} | {r['precision']:.4f} | {r['recall']:.4f} | {r['f1']:.4f} | "
            f"{int(r['false_positives'])} | {int(r['false_negatives'])} |"
        )
    lines.append("")

    hr = recommendations["high_recall"]
    hp = recommendations["high_precision"]
    lines.append("## Recommendation")
    lines.append(
        f"- High-recall phishing detection: threshold **{hr['threshold']:.1f}** "
        f"(recall={hr['recall']:.4f}, precision={hr['precision']:.4f}, F1={hr['f1']:.4f})."
    )
    lines.append(
        f"- High-precision alerting: threshold **{hp['threshold']:.1f}** "
        f"(precision={hp['precision']:.4f}, recall={hp['recall']:.4f}, F1={hp['f1']:.4f})."
    )
    lines.append(
        "- Operational note: lower thresholds reduce false negatives but increase false positives; "
        "higher thresholds do the opposite."
    )

    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze thresholds for hybrid email baseline model")
    parser.add_argument("--data", type=str, default=DATA_CSV, help="Input dataset path")
    parser.add_argument("--report-md", type=str, default=REPORT_MD, help="Output markdown report")
    parser.add_argument("--report-csv", type=str, default=REPORT_CSV, help="Output CSV report")
    args = parser.parse_args()

    if not os.path.exists(args.data):
        raise FileNotFoundError(f"Missing dataset: {args.data}")

    df = pd.read_csv(args.data)
    required = {TEXT_COLUMN, "label", *NUMERIC_COLUMNS}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"Dataset missing required columns: {missing}")

    df["label"] = pd.to_numeric(df["label"], errors="coerce")
    df = df.dropna(subset=["label"]).copy()
    df["label"] = df["label"].astype(int)
    df = df[df["label"].isin([0, 1])].copy()
    df[TEXT_COLUMN] = df[TEXT_COLUMN].fillna("").astype(str).str.strip()
    df = df[df[TEXT_COLUMN].str.len() > 0].copy()

    for col in NUMERIC_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    label_counts = {int(k): int(v) for k, v in df["label"].value_counts().sort_index().items()}

    X = df[[TEXT_COLUMN] + NUMERIC_COLUMNS]
    y = df["label"]

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=TEST_SIZE,
        random_state=RANDOM_SEED,
        stratify=y,
    )

    model = make_pipeline()
    model.fit(X_train, y_train)
    probs = model.predict_proba(X_test)[:, 1]

    roc_auc = roc_auc_score(y_test, probs)
    rows = evaluate_thresholds(y_test, probs, THRESHOLDS)
    recs = pick_recommendations(rows)

    write_csv(args.report_csv, rows)
    write_markdown(
        path=args.report_md,
        dataset_rel=os.path.relpath(args.data, ROOT),
        train_size=len(X_train),
        test_size=len(X_test),
        label_counts=label_counts,
        roc_auc=roc_auc,
        rows=rows,
        recommendations=recs,
    )

    print("=== Email Hybrid Threshold Analysis ===")
    print(f"Dataset: {os.path.relpath(args.data, ROOT)}")
    print(f"Train size: {len(X_train):,} | Test size: {len(X_test):,}")
    print(f"ROC-AUC: {roc_auc:.4f}")
    for r in rows:
        print(
            f"thr={r['threshold']:.1f} "
            f"prec={r['precision']:.4f} rec={r['recall']:.4f} f1={r['f1']:.4f} "
            f"fp={int(r['false_positives'])} fn={int(r['false_negatives'])}"
        )
    print(f"Saved markdown: {os.path.relpath(args.report_md, ROOT)}")
    print(f"Saved csv: {os.path.relpath(args.report_csv, ROOT)}")


if __name__ == "__main__":
    main()

