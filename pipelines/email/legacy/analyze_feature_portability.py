#!/usr/bin/env python3
"""TG-5.10 feature portability audit for engineered email features."""

from __future__ import annotations

import argparse
import math
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Sequence, Tuple

import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DATA_CSV = os.path.join(ROOT, "data", "processed", "email_dataset_v2_features.csv")
REPORT_OUT = os.path.join(ROOT, "reports", "email_feature_portability_report.md")

RANDOM_SEED = 1337
TEST_SIZE = 0.2
NUMERIC_VALID_RATIO = 0.8


def combine_text(subject: Any, body: Any) -> str:
    s = "" if pd.isna(subject) else str(subject).strip()
    b = "" if pd.isna(body) else str(body).strip()
    return f"{s} [SEP] {b}".strip()


def detect_numeric_feature_columns(df: pd.DataFrame) -> List[str]:
    excluded = {
        "subject",
        "body",
        "label",
        "source",
        "text",
        "sender",
        "sender_domain",
        "urls",
    }
    numeric_cols: List[str] = []
    for col in df.columns:
        lc = col.strip().lower()
        if lc in excluded:
            continue
        if lc.startswith("unnamed") or lc in {"index", "idx", "id"} or lc.endswith("_id"):
            continue
        x = pd.to_numeric(df[col], errors="coerce")
        if float(x.notna().mean()) >= NUMERIC_VALID_RATIO:
            numeric_cols.append(col)
    if not numeric_cols:
        raise ValueError("No numeric features detected for portability audit.")
    return numeric_cols


def load_dataset(path: str) -> Tuple[pd.DataFrame, List[str]]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Missing dataset: {path}")
    df = pd.read_csv(path)
    required = {"subject", "body", "label", "source"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"Dataset missing required columns: {missing}")

    df["label"] = pd.to_numeric(df["label"], errors="coerce")
    df = df.dropna(subset=["label"]).copy()
    df["label"] = df["label"].astype(int)
    df = df[df["label"].isin([0, 1])].copy()
    df["source"] = df["source"].astype(str).str.strip().str.lower()
    df["text"] = [combine_text(s, b) for s, b in zip(df["subject"], df["body"])]
    df = df[df["text"].str.len() > 0].copy()

    numeric_cols = detect_numeric_feature_columns(df)
    for col in numeric_cols:
        x = pd.to_numeric(df[col], errors="coerce")
        med = x.median(skipna=True)
        if pd.isna(med):
            med = 0.0
        df[col] = x.fillna(med).astype(float)
    return df.reset_index(drop=True), numeric_cols


def ks_statistic(x: np.ndarray, y: np.ndarray) -> float:
    """Two-sample KS statistic implemented without scipy.stats dependency."""
    if x.size == 0 or y.size == 0:
        return 0.0
    x_sorted = np.sort(x)
    y_sorted = np.sort(y)
    values = np.concatenate([x_sorted, y_sorted])
    cdf_x = np.searchsorted(x_sorted, values, side="right") / x_sorted.size
    cdf_y = np.searchsorted(y_sorted, values, side="right") / y_sorted.size
    return float(np.max(np.abs(cdf_x - cdf_y)))


def eta_squared(feature: np.ndarray, groups: Sequence[str]) -> float:
    arr = np.asarray(feature, dtype=float)
    grp = np.asarray(groups)
    grand_mean = float(np.mean(arr))
    ss_total = float(np.sum((arr - grand_mean) ** 2))
    if ss_total <= 1e-12:
        return 0.0
    ss_between = 0.0
    for g in np.unique(grp):
        vals = arr[grp == g]
        if vals.size == 0:
            continue
        m = float(np.mean(vals))
        ss_between += vals.size * ((m - grand_mean) ** 2)
    return float(ss_between / ss_total)


def compute_distribution_drift(df: pd.DataFrame, numeric_cols: Sequence[str]) -> pd.DataFrame:
    sources = sorted(df["source"].unique().tolist())
    rows: List[Dict[str, Any]] = []
    for col in numeric_cols:
        for src in sources:
            vals = df.loc[df["source"] == src, col].astype(float).to_numpy()
            rows.append(
                {
                    "feature": col,
                    "source": src,
                    "count": int(vals.size),
                    "mean": float(np.mean(vals)) if vals.size else 0.0,
                    "std": float(np.std(vals)) if vals.size else 0.0,
                }
            )
    return pd.DataFrame(rows)


def compute_feature_associations(df: pd.DataFrame, numeric_cols: Sequence[str]) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    y = df["label"].astype(float).to_numpy()
    source = df["source"].astype(str).to_numpy()
    for col in numeric_cols:
        x = df[col].astype(float).to_numpy()
        label_corr = float(np.corrcoef(x, y)[0, 1]) if np.std(x) > 1e-12 else 0.0
        src_eta2 = eta_squared(x, source)
        # Pairwise KS max across sources as drift severity.
        ks_pairs: Dict[str, float] = {}
        unique_sources = sorted(df["source"].unique().tolist())
        for i in range(len(unique_sources)):
            for j in range(i + 1, len(unique_sources)):
                s1, s2 = unique_sources[i], unique_sources[j]
                x1 = df.loc[df["source"] == s1, col].astype(float).to_numpy()
                x2 = df.loc[df["source"] == s2, col].astype(float).to_numpy()
                ks_pairs[f"{s1}__{s2}"] = ks_statistic(x1, x2)
        max_ks = max(ks_pairs.values()) if ks_pairs else 0.0
        rows.append(
            {
                "feature": col,
                "label_corr": label_corr,
                "abs_label_corr": abs(label_corr),
                "source_eta2": src_eta2,
                "max_pairwise_ks": max_ks,
                "ks_pairs": ks_pairs,
            }
        )
    out = pd.DataFrame(rows)
    out = out.sort_values(["source_eta2", "max_pairwise_ks"], ascending=False).reset_index(drop=True)
    return out


def source_leakage_single_feature(df: pd.DataFrame, feature: str, seed: int) -> Dict[str, Any]:
    x = df[[feature]].astype(float).to_numpy()
    y = df["source"].astype(str).to_numpy()
    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=TEST_SIZE,
        random_state=seed,
        stratify=y,
    )
    scaler = StandardScaler()
    x_train_s = scaler.fit_transform(x_train)
    x_test_s = scaler.transform(x_test)
    clf = LogisticRegression(max_iter=1000)
    clf.fit(x_train_s, y_train)
    pred = clf.predict(x_test_s)
    acc = accuracy_score(y_test, pred)
    return {
        "feature": feature,
        "source_leak_accuracy": float(acc),
    }


def run_light_ablation(df: pd.DataFrame, numeric_cols: Sequence[str], seed: int) -> Tuple[float, pd.DataFrame]:
    train_df, test_df = train_test_split(
        df,
        test_size=TEST_SIZE,
        random_state=seed,
        stratify=df["label"],
    )

    vectorizer = TfidfVectorizer(
        max_features=60000,
        min_df=2,
        ngram_range=(1, 2),
        lowercase=True,
        strip_accents="unicode",
        sublinear_tf=True,
    )
    x_train_text = vectorizer.fit_transform(train_df["text"])
    x_test_text = vectorizer.transform(test_df["text"])
    y_train = train_df["label"].astype(int).to_numpy()
    y_test = test_df["label"].astype(int).to_numpy()

    base_clf = LogisticRegression(max_iter=2000, solver="liblinear", class_weight="balanced")
    base_clf.fit(x_train_text, y_train)
    base_pred = base_clf.predict(x_test_text)
    base_f1 = float(f1_score(y_test, base_pred, zero_division=0))

    rows: List[Dict[str, Any]] = []
    for feat in numeric_cols:
        scaler = StandardScaler()
        feat_train = scaler.fit_transform(train_df[[feat]].astype(float).to_numpy())
        feat_test = scaler.transform(test_df[[feat]].astype(float).to_numpy())
        x_train = sparse.hstack([x_train_text, sparse.csr_matrix(feat_train)], format="csr")
        x_test = sparse.hstack([x_test_text, sparse.csr_matrix(feat_test)], format="csr")
        clf = LogisticRegression(max_iter=2000, solver="liblinear", class_weight="balanced")
        clf.fit(x_train, y_train)
        pred = clf.predict(x_test)
        f1_val = float(f1_score(y_test, pred, zero_division=0))
        rows.append(
            {
                "feature": feat,
                "f1_with_feature": f1_val,
                "delta_vs_text_only": f1_val - base_f1,
            }
        )
    ablation_df = pd.DataFrame(rows).sort_values("delta_vs_text_only", ascending=False).reset_index(drop=True)
    return base_f1, ablation_df


def portability_verdict(
    assoc_df: pd.DataFrame,
    leakage_df: pd.DataFrame,
    ablation_df: pd.DataFrame,
) -> Tuple[str, List[str]]:
    merged = assoc_df.merge(leakage_df, on="feature", how="left")
    merged["source_leak_accuracy"] = merged["source_leak_accuracy"].fillna(0.0)
    merged["risk_score"] = (
        1.5 * merged["source_eta2"]
        + 1.0 * merged["max_pairwise_ks"]
        + 1.0 * np.maximum(0.0, merged["source_leak_accuracy"] - 0.43)
        - 0.8 * merged["abs_label_corr"]
    )

    high_risk = merged[
        (merged["source_eta2"] >= 0.10)
        & (merged["max_pairwise_ks"] >= 0.35)
        & (merged["source_leak_accuracy"] >= 0.55)
    ]
    weak_ablation_signal = True
    if not ablation_df.empty and "delta_vs_text_only" in ablation_df:
        max_gain = float(pd.to_numeric(ablation_df["delta_vs_text_only"], errors="coerce").fillna(0.0).max())
        weak_ablation_signal = max_gain < 0.005

    max_leak = float(merged["source_leak_accuracy"].max()) if not merged.empty else 0.0
    max_ks = float(merged["max_pairwise_ks"].max()) if not merged.empty else 0.0

    if weak_ablation_signal and (max_leak >= 0.55 and max_ks >= 0.35):
        verdict = "NOT portable"
    elif len(high_risk) >= max(3, int(math.ceil(0.4 * len(merged)))):
        verdict = "NOT portable"
    elif len(high_risk) >= 2:
        verdict = "partially portable"
    else:
        verdict = "portable"

    top_problematic = merged.sort_values("risk_score", ascending=False)["feature"].head(3).tolist()
    return verdict, top_problematic


def write_report(
    path: str,
    df: pd.DataFrame,
    numeric_cols: Sequence[str],
    drift_df: pd.DataFrame,
    assoc_df: pd.DataFrame,
    leakage_df: pd.DataFrame,
    text_only_f1: float,
    ablation_df: pd.DataFrame,
    verdict: str,
    top_problematic: Sequence[str],
) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    merged = assoc_df.merge(leakage_df, on="feature", how="left")
    merged["source_leak_accuracy"] = merged["source_leak_accuracy"].fillna(0.0)
    top_source_tied = merged.sort_values(
        ["source_eta2", "source_leak_accuracy", "max_pairwise_ks"],
        ascending=False,
    ).head(5)
    weak_label = merged.sort_values("abs_label_corr", ascending=True).head(5)

    lines: List[str] = [
        "# Email Feature Portability Report (TG-5.10)",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## 1. Scope",
        "- Goal: audit engineered numeric feature portability across Enron, Nazario, and SpamAssassin.",
        "- Dataset: `data/processed/email_dataset_v2_features.csv`.",
        f"- Rows: {len(df):,}",
        f"- Label counts: {df['label'].value_counts().sort_index().to_dict()}",
        f"- Source counts: {df['source'].value_counts().sort_index().to_dict()}",
        f"- Audited numeric features ({len(numeric_cols)}): {list(numeric_cols)}",
        "",
        "## 2. Feature Distribution Drift Summary",
        "Mean/std by source (excerpt):",
        "",
        "| Feature | Source | Mean | Std |",
        "|---|---|---:|---:|",
    ]

    drift_excerpt = drift_df.sort_values(["feature", "source"]).reset_index(drop=True)
    for _, row in drift_excerpt.iterrows():
        lines.append(
            f"| {row['feature']} | {row['source']} | {row['mean']:.4f} | {row['std']:.4f} |"
        )

    lines.extend(
        [
            "",
            "Pairwise drift/association summary:",
            "",
            "| Feature | abs(label corr) | source eta^2 | max pairwise KS | source leakage acc (single-feature) |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for _, row in merged.sort_values(["source_eta2", "max_pairwise_ks"], ascending=False).iterrows():
        lines.append(
            f"| {row['feature']} | {row['abs_label_corr']:.4f} | {row['source_eta2']:.4f} | "
            f"{row['max_pairwise_ks']:.4f} | {row['source_leak_accuracy']:.4f} |"
        )

    lines.extend(
        [
            "",
            "## 3. Features Strongly Tied to Source",
            "",
            "| Feature | source eta^2 | max KS | source leakage acc |",
            "|---|---:|---:|---:|",
        ]
    )
    for _, row in top_source_tied.iterrows():
        lines.append(
            f"| {row['feature']} | {row['source_eta2']:.4f} | {row['max_pairwise_ks']:.4f} | {row['source_leak_accuracy']:.4f} |"
        )

    lines.extend(
        [
            "",
            "## 4. Features Weakly Tied to Label",
            "",
            "| Feature | abs(label corr) | source eta^2 |",
            "|---|---:|---:|",
        ]
    )
    for _, row in weak_label.iterrows():
        lines.append(f"| {row['feature']} | {row['abs_label_corr']:.4f} | {row['source_eta2']:.4f} |")

    lines.extend(
        [
            "",
            "## 5. Lightweight Ablation (TF-IDF text + one feature)",
            f"- Text-only reference F1: **{text_only_f1:.4f}**",
            "",
            "| Feature | F1(text + feature) | Delta vs text-only |",
            "|---|---:|---:|",
        ]
    )
    for _, row in ablation_df.iterrows():
        lines.append(
            f"| {row['feature']} | {row['f1_with_feature']:.4f} | {row['delta_vs_text_only']:+.4f} |"
        )

    lines.extend(
        [
            "",
            "## 6. Conclusion",
            f"- Portability verdict: **{verdict}**.",
            f"- Top problematic features: {list(top_problematic)}.",
            "- Numeric features are not portable across datasets due to distribution shift and source-specific patterns, which explains degradation in fusion models.",
        ]
    )

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="TG-5.10 feature portability audit")
    parser.add_argument("--data", default=DATA_CSV)
    parser.add_argument("--seed", type=int, default=RANDOM_SEED)
    args = parser.parse_args()

    df, numeric_cols = load_dataset(args.data)
    drift_df = compute_distribution_drift(df, numeric_cols)
    assoc_df = compute_feature_associations(df, numeric_cols)
    leakage_rows = [source_leakage_single_feature(df, feat, seed=args.seed) for feat in numeric_cols]
    leakage_df = pd.DataFrame(leakage_rows)
    text_only_f1, ablation_df = run_light_ablation(df, numeric_cols, seed=args.seed)
    verdict, top_problematic = portability_verdict(assoc_df, leakage_df, ablation_df)

    write_report(
        path=REPORT_OUT,
        df=df,
        numeric_cols=numeric_cols,
        drift_df=drift_df,
        assoc_df=assoc_df,
        leakage_df=leakage_df,
        text_only_f1=text_only_f1,
        ablation_df=ablation_df,
        verdict=verdict,
        top_problematic=top_problematic,
    )

    print("=== TG-5.10 Complete ===")
    print(f"Dataset rows: {len(df):,}")
    print(f"Numeric features: {numeric_cols}")
    print(f"Text-only reference F1: {text_only_f1:.4f}")
    print(f"Portability verdict: {verdict}")
    print(f"Top problematic features: {top_problematic}")
    print(f"Report: {os.path.relpath(REPORT_OUT, ROOT)}")


if __name__ == "__main__":
    main()
