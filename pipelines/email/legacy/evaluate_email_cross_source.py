#!/usr/bin/env python3
"""Cross-source robustness evaluation for email baseline classifier.

Experiments:
- A: train on Enron + Nazario, test on SpamAssassin
- B: train on Enron + SpamAssassin, test on Nazario
- C: train on Nazario + SpamAssassin, test on Enron

Outputs:
- reports/email_cross_source_eval.md
"""

from __future__ import annotations

import argparse
import os
from typing import Dict, List, Optional, Sequence, Tuple

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DATA_CSV = os.path.join(ROOT, "data", "processed", "email_dataset_v1.csv")
REPORT_OUT = os.path.join(ROOT, "reports", "email_cross_source_eval.md")

RANDOM_SEED = 1337

EXPERIMENTS = [
    {
        "id": "A",
        "name": "Train Enron+Nazario, Test SpamAssassin",
        "train_sources": ["enron", "nazario"],
        "test_source": "spamassassin",
    },
    {
        "id": "B",
        "name": "Train Enron+SpamAssassin, Test Nazario",
        "train_sources": ["enron", "spamassassin"],
        "test_source": "nazario",
    },
    {
        "id": "C",
        "name": "Train Nazario+SpamAssassin, Test Enron",
        "train_sources": ["nazario", "spamassassin"],
        "test_source": "enron",
    },
]


def build_text(subject: pd.Series, body: pd.Series) -> pd.Series:
    sub = subject.fillna("").astype(str).str.strip()
    bod = body.fillna("").astype(str).str.strip()
    return (sub + " " + bod).str.strip()


def make_pipeline(
    max_features: int,
    min_df: int,
    ngram_max: int,
    seed: int,
) -> Pipeline:
    return Pipeline(
        steps=[
            (
                "tfidf",
                TfidfVectorizer(
                    lowercase=True,
                    strip_accents="unicode",
                    ngram_range=(1, max(1, ngram_max)),
                    max_features=max_features,
                    min_df=max(1, min_df),
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
                    random_state=seed,
                ),
            ),
        ]
    )


def evaluate_predictions(
    y_true: pd.Series,
    y_pred,
    y_score: Optional[pd.Series],
) -> Tuple[Dict[str, Optional[float]], List[List[int]]]:
    metrics: Dict[str, Optional[float]] = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "roc_auc": None,
    }

    if y_score is not None and y_true.nunique() > 1:
        metrics["roc_auc"] = float(roc_auc_score(y_true, y_score))

    cm = confusion_matrix(y_true, y_pred, labels=[0, 1]).tolist()
    return metrics, cm


def top_weighted_features(pipeline: Pipeline, n: int = 30) -> Tuple[List[Tuple[str, float]], List[Tuple[str, float]]]:
    vectorizer: TfidfVectorizer = pipeline.named_steps["tfidf"]
    clf: LogisticRegression = pipeline.named_steps["clf"]

    feature_names = vectorizer.get_feature_names_out()
    coefs = clf.coef_[0]

    top_pos_idx = coefs.argsort()[-n:][::-1]
    top_neg_idx = coefs.argsort()[:n]

    top_pos = [(feature_names[i], float(coefs[i])) for i in top_pos_idx]
    top_neg = [(feature_names[i], float(coefs[i])) for i in top_neg_idx]
    return top_pos, top_neg


def format_feature_block(items: Sequence[Tuple[str, float]]) -> List[str]:
    lines = []
    for feat, weight in items:
        lines.append(f"- `{feat}`: {weight:.4f}")
    return lines


def run_experiment(
    df: pd.DataFrame,
    exp: Dict[str, object],
    max_features: int,
    min_df: int,
    ngram_max: int,
    seed: int,
) -> Dict[str, object]:
    train_sources = list(exp["train_sources"])
    test_source = str(exp["test_source"])

    train_df = df[df["source"].isin(train_sources)].copy()
    test_df = df[df["source"] == test_source].copy()

    if train_df.empty:
        raise ValueError(f"Empty training split for experiment {exp['id']}")
    if test_df.empty:
        raise ValueError(f"Empty test split for experiment {exp['id']}")

    X_train = train_df["text"]
    y_train = train_df["label"]
    X_test = test_df["text"]
    y_test = test_df["label"]

    pipeline = make_pipeline(max_features, min_df, ngram_max, seed)
    pipeline.fit(X_train, y_train)

    y_pred = pipeline.predict(X_test)
    y_score = None
    if hasattr(pipeline, "predict_proba"):
        y_score = pipeline.predict_proba(X_test)[:, 1]

    metrics, cm = evaluate_predictions(y_test, y_pred, y_score)
    top_pos, top_neg = top_weighted_features(pipeline, n=30)

    return {
        "id": exp["id"],
        "name": exp["name"],
        "train_sources": train_sources,
        "test_source": test_source,
        "train_size": int(len(train_df)),
        "test_size": int(len(test_df)),
        "train_label_counts": {
            int(k): int(v) for k, v in train_df["label"].value_counts().sort_index().items()
        },
        "test_label_counts": {
            int(k): int(v) for k, v in test_df["label"].value_counts().sort_index().items()
        },
        "metrics": metrics,
        "confusion_matrix": cm,
        "top_positive_features": top_pos,
        "top_negative_features": top_neg,
    }


def write_report(
    path: str,
    dataset_rel: str,
    results: Sequence[Dict[str, object]],
    max_features: int,
    min_df: int,
    ngram_max: int,
) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)

    lines: List[str] = []
    lines.append("# Email Cross-Source Robustness Evaluation")
    lines.append("")
    lines.append("## Setup")
    lines.append(f"- Dataset: `{dataset_rel}`")
    lines.append("- Model pipeline: `TF-IDF + LogisticRegression`")
    lines.append("- Label mapping: `0=legitimate`, `1=suspicious/phishing-like`")
    lines.append(
        f"- TF-IDF params: max_features={max_features}, min_df={min_df}, ngram_range=(1,{ngram_max})"
    )
    lines.append("")

    for result in results:
        metrics = result["metrics"]
        roc_auc = metrics["roc_auc"]

        lines.append(f"## Experiment {result['id']}: {result['name']}")
        lines.append(
            f"- Train sources: {', '.join(result['train_sources'])} | Test source: {result['test_source']}"
        )
        lines.append(
            f"- Train size: {result['train_size']:,} | Test size: {result['test_size']:,}"
        )
        lines.append(f"- Train label counts: {result['train_label_counts']}")
        lines.append(f"- Test label counts: {result['test_label_counts']}")
        lines.append("")
        lines.append("### Metrics")
        lines.append(f"- Accuracy: **{metrics['accuracy']:.4f}**")
        lines.append(f"- Precision: **{metrics['precision']:.4f}**")
        lines.append(f"- Recall: **{metrics['recall']:.4f}**")
        lines.append(f"- F1: **{metrics['f1']:.4f}**")
        if roc_auc is None:
            lines.append("- ROC-AUC: n/a (single-class test set)")
        else:
            lines.append(f"- ROC-AUC: **{roc_auc:.4f}**")
        lines.append("")
        lines.append("### Confusion Matrix")
        lines.append("Rows=true [0,1], Cols=pred [0,1]")
        lines.append("```")
        lines.append(str(result["confusion_matrix"]))
        lines.append("```")
        lines.append("")

        lines.append("### Top 30 Positive Features (push toward label=1)")
        lines.extend(format_feature_block(result["top_positive_features"]))
        lines.append("")

        lines.append("### Top 30 Negative Features (push toward label=0)")
        lines.extend(format_feature_block(result["top_negative_features"]))
        lines.append("")

    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate baseline email model across dataset sources")
    parser.add_argument("--data", type=str, default=DATA_CSV, help="Input dataset path")
    parser.add_argument("--report-out", type=str, default=REPORT_OUT, help="Output markdown report")
    parser.add_argument("--seed", type=int, default=RANDOM_SEED, help="Random seed")
    parser.add_argument("--max-features", type=int, default=80000, help="TF-IDF max features")
    parser.add_argument("--min-df", type=int, default=2, help="TF-IDF min_df")
    parser.add_argument("--ngram-max", type=int, default=2, help="Max n-gram size (starting at 1)")
    args = parser.parse_args()

    if not os.path.exists(args.data):
        raise FileNotFoundError(f"Missing dataset: {args.data}")

    df = pd.read_csv(args.data)
    required_cols = {"subject", "body", "label", "source"}
    missing = sorted(required_cols - set(df.columns))
    if missing:
        raise ValueError(f"Dataset missing required columns: {missing}")

    df["label"] = pd.to_numeric(df["label"], errors="coerce")
    df = df.dropna(subset=["label"]).copy()
    df["label"] = df["label"].astype(int)
    df = df[df["label"].isin([0, 1])].copy()
    df["source"] = df["source"].astype(str).str.strip().str.lower()
    df["text"] = build_text(df["subject"], df["body"])
    df = df[df["text"].str.len() > 0].copy()

    results = []
    for exp in EXPERIMENTS:
        results.append(
            run_experiment(
                df=df,
                exp=exp,
                max_features=args.max_features,
                min_df=args.min_df,
                ngram_max=args.ngram_max,
                seed=args.seed,
            )
        )

    write_report(
        path=args.report_out,
        dataset_rel=os.path.relpath(args.data, ROOT),
        results=results,
        max_features=args.max_features,
        min_df=args.min_df,
        ngram_max=args.ngram_max,
    )

    print("=== Email Cross-Source Evaluation ===")
    for result in results:
        m = result["metrics"]
        roc = "n/a" if m["roc_auc"] is None else f"{m['roc_auc']:.4f}"
        print(
            f"Experiment {result['id']} | Acc={m['accuracy']:.4f} "
            f"Prec={m['precision']:.4f} Rec={m['recall']:.4f} "
            f"F1={m['f1']:.4f} ROC-AUC={roc}"
        )
    print(f"Saved report: {os.path.relpath(args.report_out, ROOT)}")


if __name__ == "__main__":
    main()
