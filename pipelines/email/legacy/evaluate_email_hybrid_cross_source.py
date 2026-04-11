#!/usr/bin/env python3
"""Cross-source robustness evaluation for hybrid email baseline classifier.

Uses text + handcrafted numeric features from:
- data/processed/email_dataset_v2_features.csv

Outputs:
- reports/email_hybrid_cross_source_eval.md
"""

from __future__ import annotations

import argparse
import os
import re
from typing import Dict, List, Optional, Sequence, Tuple

import pandas as pd
from sklearn.compose import ColumnTransformer
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
from sklearn.preprocessing import StandardScaler


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DATA_CSV = os.path.join(ROOT, "data", "processed", "email_dataset_v2_features.csv")
TEXT_ONLY_REPORT = os.path.join(ROOT, "reports", "email_cross_source_eval.md")
OUT_REPORT = os.path.join(ROOT, "reports", "email_hybrid_cross_source_eval.md")

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


def make_pipeline(
    max_features: int,
    ngram_max: int,
    seed: int,
) -> Pipeline:
    preprocessor = ColumnTransformer(
        transformers=[
            (
                "text",
                TfidfVectorizer(
                    max_features=max_features,
                    ngram_range=(1, max(1, ngram_max)),
                    lowercase=True,
                    strip_accents="unicode",
                    sublinear_tf=True,
                ),
                TEXT_COLUMN,
            ),
            ("numeric", StandardScaler(), NUMERIC_COLUMNS),
        ]
    )

    model = Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            (
                "classifier",
                LogisticRegression(
                    solver="liblinear",
                    max_iter=2000,
                    class_weight="balanced",
                    random_state=seed,
                ),
            ),
        ]
    )
    return model


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


def parse_text_only_cross_source(path: str) -> Dict[str, Dict[str, Optional[float]]]:
    """Parse prior text-only report metrics by experiment id (A/B/C)."""
    if not os.path.exists(path):
        return {}

    text = open(path, "r", encoding="utf-8").read()
    out: Dict[str, Dict[str, Optional[float]]] = {}

    for exp_id in ("A", "B", "C"):
        section_match = re.search(
            rf"## Experiment {exp_id}:(.*?)(?:\n## Experiment [ABC]:|\Z)",
            text,
            flags=re.S,
        )
        if not section_match:
            continue
        section = section_match.group(1)

        def metric(name: str) -> Optional[float]:
            m = re.search(rf"- {name}: \*\*(.*?)\*\*", section)
            if not m:
                return None
            token = m.group(1).strip().lower()
            if token in {"n/a", "na"}:
                return None
            try:
                return float(token)
            except ValueError:
                return None

        out[exp_id] = {
            "accuracy": metric("Accuracy"),
            "precision": metric("Precision"),
            "recall": metric("Recall"),
            "f1": metric("F1"),
            "roc_auc": metric("ROC-AUC"),
        }

    return out


def interpretation_note(
    exp_id: str,
    hybrid_metrics: Dict[str, Optional[float]],
    baseline_metrics: Optional[Dict[str, Optional[float]]],
) -> str:
    recall = hybrid_metrics["recall"] or 0.0

    if baseline_metrics is None or baseline_metrics.get("recall") is None:
        if recall < 0.20:
            return "Recall remains collapsed on this holdout source."
        if recall >= 0.70:
            return "Recall is strong on this holdout source."
        return "Recall is moderate on this holdout source."

    base_recall = baseline_metrics["recall"] or 0.0
    base_f1 = baseline_metrics.get("f1") or 0.0
    delta_recall = recall - base_recall
    delta_f1 = (hybrid_metrics["f1"] or 0.0) - base_f1

    if delta_recall > 0.02 and delta_f1 > 0.02:
        return (
            f"Recall/F1 improved vs text-only baseline "
            f"(recall {base_recall:.4f} -> {recall:.4f}, "
            f"F1 {base_f1:.4f} -> {(hybrid_metrics['f1'] or 0.0):.4f})."
        )
    if delta_recall < -0.02 and delta_f1 < -0.02:
        return (
            f"Recall/F1 regressed vs text-only baseline "
            f"(recall {base_recall:.4f} -> {recall:.4f}, "
            f"F1 {base_f1:.4f} -> {(hybrid_metrics['f1'] or 0.0):.4f})."
        )
    return (
        f"Recall/F1 are broadly unchanged vs text-only baseline "
        f"(recall {base_recall:.4f} -> {recall:.4f}, "
        f"F1 {base_f1:.4f} -> {(hybrid_metrics['f1'] or 0.0):.4f})."
    )


def run_experiment(
    df: pd.DataFrame,
    exp: Dict[str, object],
    max_features: int,
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

    X_train = train_df[[TEXT_COLUMN] + NUMERIC_COLUMNS]
    y_train = train_df["label"]
    X_test = test_df[[TEXT_COLUMN] + NUMERIC_COLUMNS]
    y_test = test_df["label"]

    model = make_pipeline(max_features=max_features, ngram_max=ngram_max, seed=seed)
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    y_score = None
    if hasattr(model, "predict_proba"):
        y_score = model.predict_proba(X_test)[:, 1]

    metrics, cm = evaluate_predictions(y_test, y_pred, y_score)

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
    }


def write_report(
    path: str,
    dataset_rel: str,
    results: Sequence[Dict[str, object]],
    text_only_metrics: Dict[str, Dict[str, Optional[float]]],
    max_features: int,
    ngram_max: int,
) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)

    lines: List[str] = []
    lines.append("# Email Hybrid Cross-Source Evaluation")
    lines.append("")
    lines.append("## Setup")
    lines.append(f"- Dataset: `{dataset_rel}`")
    lines.append("- Pipeline: `TF-IDF(text) + StandardScaler(numeric) + LogisticRegression`")
    lines.append(f"- Text column: `{TEXT_COLUMN}`")
    lines.append(f"- Numeric columns: {NUMERIC_COLUMNS}")
    lines.append(
        f"- TF-IDF params: max_features={max_features}, ngram_range=(1,{ngram_max}), lowercase=True, strip_accents=unicode, sublinear_tf=True"
    )
    lines.append("- Classifier params: solver=liblinear, max_iter=2000, class_weight=balanced")
    lines.append("")

    for result in results:
        exp_id = result["id"]
        metrics = result["metrics"]
        roc_auc = metrics["roc_auc"]
        note = interpretation_note(exp_id, metrics, text_only_metrics.get(exp_id))

        lines.append(f"## Experiment {exp_id}: {result['name']}")
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
        lines.append("### Interpretation")
        lines.append(f"- {note}")
        lines.append("")

    lines.append("## Comparison vs Text-Only Cross-Source Results")
    if not text_only_metrics:
        lines.append(
            f"- Could not parse text-only baseline report at `{os.path.relpath(TEXT_ONLY_REPORT, ROOT)}`."
        )
    else:
        for result in results:
            exp_id = result["id"]
            hybrid = result["metrics"]
            base = text_only_metrics.get(exp_id)
            if not base:
                lines.append(f"- Experiment {exp_id}: no text-only baseline metrics found.")
                continue
            h_recall = hybrid["recall"] or 0.0
            h_f1 = hybrid["f1"] or 0.0
            b_recall = base.get("recall") or 0.0
            b_f1 = base.get("f1") or 0.0
            d_recall = h_recall - b_recall
            d_f1 = h_f1 - b_f1

            recall_state = "improved" if d_recall > 0 else ("decreased" if d_recall < 0 else "unchanged")
            f1_state = "improved" if d_f1 > 0 else ("decreased" if d_f1 < 0 else "unchanged")

            lines.append(
                f"- Experiment {exp_id}: Recall {recall_state} "
                f"({b_recall:.4f} -> {h_recall:.4f}, delta {d_recall:+.4f}); "
                f"F1 {f1_state} ({b_f1:.4f} -> {h_f1:.4f}, delta {d_f1:+.4f})."
            )

    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate hybrid email model across source-held-out splits")
    parser.add_argument("--data", type=str, default=DATA_CSV, help="Input dataset path")
    parser.add_argument("--report-out", type=str, default=OUT_REPORT, help="Output markdown report")
    parser.add_argument("--seed", type=int, default=RANDOM_SEED, help="Random seed")
    parser.add_argument("--max-features", type=int, default=80000, help="TF-IDF max features")
    parser.add_argument("--ngram-max", type=int, default=2, help="Max n-gram size (starting at 1)")
    args = parser.parse_args()

    if not os.path.exists(args.data):
        raise FileNotFoundError(f"Missing dataset: {args.data}")

    df = pd.read_csv(args.data)
    required = {TEXT_COLUMN, "label", "source", *NUMERIC_COLUMNS}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"Dataset missing required columns: {missing}")

    df["label"] = pd.to_numeric(df["label"], errors="coerce")
    df = df.dropna(subset=["label"]).copy()
    df["label"] = df["label"].astype(int)
    df = df[df["label"].isin([0, 1])].copy()
    df["source"] = df["source"].astype(str).str.strip().str.lower()
    df[TEXT_COLUMN] = df[TEXT_COLUMN].fillna("").astype(str).str.strip()
    df = df[df[TEXT_COLUMN].str.len() > 0].copy()

    for col in NUMERIC_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    text_only_metrics = parse_text_only_cross_source(TEXT_ONLY_REPORT)
    results: List[Dict[str, object]] = []
    for exp in EXPERIMENTS:
        results.append(
            run_experiment(
                df=df,
                exp=exp,
                max_features=args.max_features,
                ngram_max=args.ngram_max,
                seed=args.seed,
            )
        )

    write_report(
        path=args.report_out,
        dataset_rel=os.path.relpath(args.data, ROOT),
        results=results,
        text_only_metrics=text_only_metrics,
        max_features=args.max_features,
        ngram_max=args.ngram_max,
    )

    print("=== Email Hybrid Cross-Source Evaluation ===")
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

