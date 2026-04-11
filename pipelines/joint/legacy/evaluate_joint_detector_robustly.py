#!/usr/bin/env python3
"""Robust repeated-split evaluation for joint phishing detector (TG-6.2)."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.utils.joint_optimization import extract_joint_heuristic_features


REPORTS_DIR_FINAL = ROOT / "reports" / "final"
REPORTS_DIR_EXPERIMENTS = ROOT / "reports" / "experiments"
DEFAULT_DATASET = ROOT / "data" / "eval" / "email_url_joint_test_dataset_v2.csv"
OP_THRESHOLDS = {
    "soc": 0.4,
    "balanced": 0.5,
    "high_confidence": 0.6,
}


def to_label(v: Any) -> str:
    s = str(v).strip().lower()
    return "phishing" if s in {"malicious", "phishing", "1", "true", "yes"} else "legitimate"


def parse_urls(raw: Any) -> List[str]:
    txt = "" if raw is None else str(raw).strip()
    if not txt or txt.lower() == "nan":
        return []
    return [u.strip() for u in re.split(r"\s*\|\s*|[\n,]+", txt) if u.strip()]


def load_df(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    if path.suffix.lower() in {".xlsx", ".xls"}:
        df = pd.read_excel(path, sheet_name="test_cases")
    else:
        df = pd.read_csv(path)
    required = {"subject", "body", "expected_joint_label"}
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required cols: {missing}")
    if "sender_name" not in df.columns:
        df["sender_name"] = ""
    if "urls" not in df.columns:
        df["urls"] = ""
    if "case_id" not in df.columns:
        df["case_id"] = [f"case_{i:04d}" for i in range(len(df))]
    if "scenario" not in df.columns:
        df["scenario"] = "unknown"
    if "difficulty" not in df.columns:
        df["difficulty"] = "unknown"
    return df.copy()


def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray, y_score: np.ndarray) -> Dict[str, Any]:
    out = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "confusion_matrix": confusion_matrix(y_true, y_pred).tolist(),
    }
    if len(set(y_true.tolist())) > 1:
        out["roc_auc"] = float(roc_auc_score(y_true, y_score))
    else:
        out["roc_auc"] = np.nan
    return out


def choose_dev_threshold(scores: np.ndarray, y_true: np.ndarray) -> float:
    best_t = 0.5
    best = -1.0
    for t in np.round(np.arange(0.05, 0.951, 0.05), 2):
        yp = (scores >= t).astype(int)
        acc = accuracy_score(y_true, yp)
        bal = balanced_accuracy_score(y_true, yp)
        f1 = f1_score(y_true, yp, zero_division=0)
        score = (acc + bal + f1) / 3.0
        if score > best:
            best = score
            best_t = float(t)
    return best_t


def precompute_predictions(df: pd.DataFrame) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    with TestClient(app) as client:
        for _, r in df.iterrows():
            subject = "" if pd.isna(r.get("subject")) else str(r.get("subject"))
            body = "" if pd.isna(r.get("body")) else str(r.get("body"))
            sender = "" if pd.isna(r.get("sender_name")) else str(r.get("sender_name"))
            urls = parse_urls(r.get("urls"))

            email_out = client.post(
                "/detect/email",
                json={
                    "subject": subject,
                    "body": body,
                    "sender": sender,
                    "operating_mode": "balanced",
                    "enable_explain": False,
                },
            ).json()
            email_score = float(email_out.get("email_score", email_out.get("probability", 0.0)))

            url_scores: List[float] = []
            url_reason_features: List[str] = []
            for u in urls:
                uo = client.post("/detect/url", json={"url": u, "enable_explain": True}).json()
                url_scores.append(float(uo.get("url_score", uo.get("probability", 0.0))))
                for rr in (uo.get("reasons") or []):
                    if isinstance(rr, dict):
                        feat = str(rr.get("feature", "")).strip()
                        if feat:
                            url_reason_features.append(feat)
            url_score = max(url_scores) if url_scores else 0.0

            joint_base = client.post(
                "/detect/joint",
                json={
                    "subject": subject,
                    "body": body,
                    "sender": sender,
                    "urls": urls,
                    "joint_strategy": "baseline",
                    "operating_mode": "balanced",
                    "enable_explain": False,
                },
            ).json()
            base_score = float(joint_base.get("final_score", 0.0))

            joint_opt = client.post(
                "/detect/joint",
                json={
                    "subject": subject,
                    "body": body,
                    "sender": sender,
                    "urls": urls,
                    "joint_strategy": "optimized",
                    "operating_mode": "balanced",
                    "enable_explain": False,
                },
            ).json()
            opt_score = float(joint_opt.get("final_score", 0.0))

            heur = extract_joint_heuristic_features(
                subject=subject,
                body=body,
                sender=sender,
                urls=urls,
                email_score=email_score,
                url_scores=url_scores,
                url_reason_features=url_reason_features,
            )

            rows.append(
                {
                    "case_id": str(r.get("case_id", "")),
                    "scenario": str(r.get("scenario", "")),
                    "difficulty": str(r.get("difficulty", "")),
                    "category": str(r.get("category", "")),
                    "y_joint": 1 if to_label(r.get("expected_joint_label")) == "phishing" else 0,
                    "email_score": email_score,
                    "url_score": url_score,
                    "joint_baseline_score": base_score,
                    "joint_optimized_score": opt_score,
                    **{f"h_{k}": float(v) for k, v in heur.items()},
                }
            )
    return pd.DataFrame(rows)


def evaluate_repeated(df: pd.DataFrame, repeats: int) -> Tuple[pd.DataFrame, pd.DataFrame]:
    metric_rows: List[Dict[str, Any]] = []
    error_rows: List[Dict[str, Any]] = []

    feature_cols = ["email_score", "url_score", "joint_baseline_score"] + sorted(
        [c for c in df.columns if c.startswith("h_")]
    )
    seeds = [17, 23, 31, 47, 59, 73, 89, 97]
    seeds = seeds[: max(5, repeats)]

    for ridx, seed in enumerate(seeds, start=1):
        train_dev_idx, test_idx = train_test_split(
            df.index.values,
            test_size=0.2,
            random_state=seed,
            stratify=df["y_joint"],
        )
        train_idx, dev_idx = train_test_split(
            train_dev_idx,
            test_size=0.25,
            random_state=seed + 1000,
            stratify=df.loc[train_dev_idx, "y_joint"],
        )
        train = df.loc[train_idx].copy()
        dev = df.loc[dev_idx].copy()
        test = df.loc[test_idx].copy()

        # Meta classifier (experimental)
        clf = LogisticRegression(max_iter=3000, class_weight="balanced", solver="liblinear")
        clf.fit(train[feature_cols].to_numpy(float), train["y_joint"].to_numpy(int))
        dev_meta = clf.predict_proba(dev[feature_cols].to_numpy(float))[:, 1]
        test_meta = clf.predict_proba(test[feature_cols].to_numpy(float))[:, 1]

        strategy_scores = {
            "baseline": (dev["joint_baseline_score"].to_numpy(float), test["joint_baseline_score"].to_numpy(float)),
            "optimized": (dev["joint_optimized_score"].to_numpy(float), test["joint_optimized_score"].to_numpy(float)),
            "meta_experimental": (dev_meta, test_meta),
        }

        for strategy, (dev_scores, test_scores) in strategy_scores.items():
            dev_y = dev["y_joint"].to_numpy(int)
            test_y = test["y_joint"].to_numpy(int)

            dev_opt_threshold = choose_dev_threshold(dev_scores, dev_y)
            threshold_map = {
                "soc": OP_THRESHOLDS["soc"],
                "balanced": OP_THRESHOLDS["balanced"],
                "high_confidence": OP_THRESHOLDS["high_confidence"],
                "dev_optimized": dev_opt_threshold,
            }
            for tname, thr in threshold_map.items():
                preds = (test_scores >= thr).astype(int)
                m = compute_metrics(test_y, preds, test_scores)
                metric_rows.append(
                    {
                        "repeat": ridx,
                        "seed": seed,
                        "strategy": strategy,
                        "threshold_name": tname,
                        "threshold": float(thr),
                        **m,
                    }
                )

            # Error rows for baseline/optimized @ balanced threshold
            if strategy in {"baseline", "optimized"}:
                preds = (test_scores >= OP_THRESHOLDS["balanced"]).astype(int)
                for i, (_, row) in enumerate(test.iterrows()):
                    y = int(row["y_joint"])
                    p = int(preds[i])
                    if y != p:
                        error_rows.append(
                            {
                                "repeat": ridx,
                                "strategy": strategy,
                                "case_id": row["case_id"],
                                "scenario": row["scenario"],
                                "difficulty": row["difficulty"],
                                "category": row["category"],
                                "error_type": "false_positive" if y == 0 else "false_negative",
                            }
                        )

    return pd.DataFrame(metric_rows), pd.DataFrame(error_rows)


def build_error_summary(errors: pd.DataFrame) -> pd.DataFrame:
    if errors.empty:
        return pd.DataFrame(
            columns=[
                "scenario",
                "baseline_false_positive",
                "baseline_false_negative",
                "optimized_false_positive",
                "optimized_false_negative",
                "net_error_change_optimized_minus_baseline",
            ]
        )
    pivot = (
        errors.groupby(["scenario", "strategy", "error_type"])
        .size()
        .unstack(["strategy", "error_type"], fill_value=0)
    )
    def _get(col):
        return pivot[col] if col in pivot.columns else pd.Series(0, index=pivot.index)
    out = pd.DataFrame(
        {
            "scenario": pivot.index,
            "baseline_false_positive": _get(("baseline", "false_positive")).astype(int).values,
            "baseline_false_negative": _get(("baseline", "false_negative")).astype(int).values,
            "optimized_false_positive": _get(("optimized", "false_positive")).astype(int).values,
            "optimized_false_negative": _get(("optimized", "false_negative")).astype(int).values,
        }
    )
    out["net_error_change_optimized_minus_baseline"] = (
        (out["optimized_false_positive"] + out["optimized_false_negative"])
        - (out["baseline_false_positive"] + out["baseline_false_negative"])
    )
    out = out.sort_values(
        ["net_error_change_optimized_minus_baseline", "optimized_false_negative", "optimized_false_positive"],
        ascending=[True, False, False],
    )
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default=str(DEFAULT_DATASET))
    ap.add_argument("--repeats", type=int, default=5)
    args = ap.parse_args()

    dataset_path = Path(args.dataset).expanduser()
    REPORTS_DIR_FINAL.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR_EXPERIMENTS.mkdir(parents=True, exist_ok=True)

    raw = load_df(dataset_path)
    pred = precompute_predictions(raw)
    metrics, errors = evaluate_repeated(pred, repeats=args.repeats)

    metrics_path = REPORTS_DIR_EXPERIMENTS / "joint_detector_robust_metrics.csv"
    metrics.to_csv(metrics_path, index=False)

    err_summary = build_error_summary(errors)
    err_path = REPORTS_DIR_EXPERIMENTS / "joint_detector_v2_error_analysis.csv"
    err_summary.to_csv(err_path, index=False)

    agg = (
        metrics.groupby(["strategy", "threshold_name"], as_index=False)
        .agg(
            accuracy_mean=("accuracy", "mean"),
            accuracy_std=("accuracy", "std"),
            precision_mean=("precision", "mean"),
            precision_std=("precision", "std"),
            recall_mean=("recall", "mean"),
            recall_std=("recall", "std"),
            f1_mean=("f1", "mean"),
            f1_std=("f1", "std"),
            roc_auc_mean=("roc_auc", "mean"),
            roc_auc_std=("roc_auc", "std"),
        )
        .sort_values(["strategy", "threshold_name"])
    )

    # Stability check: optimized vs baseline at balanced threshold.
    bal = metrics[metrics["threshold_name"] == "balanced"]
    per_repeat = bal.pivot_table(index="repeat", columns="strategy", values="accuracy", aggfunc="first")
    repeats_where_opt_better = int((per_repeat.get("optimized", 0) > per_repeat.get("baseline", 0)).sum())

    top_fp = err_summary[err_summary["optimized_false_positive"] > 0].sort_values(
        "optimized_false_positive", ascending=False
    ).head(5)
    top_fn = err_summary[err_summary["optimized_false_negative"] > 0].sort_values(
        "optimized_false_negative", ascending=False
    ).head(5)

    report = []
    report.append("# Joint Detector Robust Evaluation Report (TG-6.2)")
    report.append("")
    report.append(f"- Dataset: `{dataset_path}`")
    report.append(f"- Total rows: **{len(raw)}**")
    report.append(f"- Repeats: **{max(5, args.repeats)}**")
    report.append(f"- Category composition: `{raw['category'].value_counts().to_dict()}`")
    report.append(
        f"- Joint label distribution: `{pred['y_joint'].value_counts().sort_index().to_dict()}` (0=legitimate,1=phishing)"
    )
    report.append("")
    report.append("## Mean ± Std Metrics Across Repeats")
    report.append("")
    report.append("| Strategy | Threshold | Accuracy | Precision | Recall | F1 | ROC-AUC |")
    report.append("|---|---|---:|---:|---:|---:|---:|")
    for _, r in agg.iterrows():
        report.append(
            "| {strategy} | {threshold_name} | {acc:.3f} ± {acc_s:.3f} | {prec:.3f} ± {prec_s:.3f} | "
            "{rec:.3f} ± {rec_s:.3f} | {f1:.3f} ± {f1_s:.3f} | {auc:.3f} ± {auc_s:.3f} |".format(
                strategy=r["strategy"],
                threshold_name=r["threshold_name"],
                acc=r["accuracy_mean"],
                acc_s=0.0 if pd.isna(r["accuracy_std"]) else r["accuracy_std"],
                prec=r["precision_mean"],
                prec_s=0.0 if pd.isna(r["precision_std"]) else r["precision_std"],
                rec=r["recall_mean"],
                rec_s=0.0 if pd.isna(r["recall_std"]) else r["recall_std"],
                f1=r["f1_mean"],
                f1_s=0.0 if pd.isna(r["f1_std"]) else r["f1_std"],
                auc=r["roc_auc_mean"],
                auc_s=0.0 if pd.isna(r["roc_auc_std"]) else r["roc_auc_std"],
            )
        )
    report.append("")
    report.append("## Stability Notes")
    report.append(
        f"- Optimized strategy outperformed baseline on balanced-threshold accuracy in **{repeats_where_opt_better}/{len(per_repeat)}** repeats."
    )
    report.append("- `meta_experimental` is reported for research only and not set as production default.")
    report.append("")
    report.append("## Top False-Positive Scenarios (optimized, balanced)")
    if top_fp.empty:
        report.append("- none")
    else:
        for _, r in top_fp.iterrows():
            report.append(f"- {r['scenario']}: {int(r['optimized_false_positive'])}")
    report.append("")
    report.append("## Top False-Negative Scenarios (optimized, balanced)")
    if top_fn.empty:
        report.append("- none")
    else:
        for _, r in top_fn.iterrows():
            report.append(f"- {r['scenario']}: {int(r['optimized_false_negative'])}")
    report.append("")
    report.append("## Interpretation")
    report.append("- Repeated-split evaluation reduces single-holdout luck and gives mean+variance estimates.")
    report.append("- If 0.90+ appears only in isolated splits or only for meta model, treat it as unstable/overfit.")
    report.append("- For production-safe operation, prioritize the optimized rule-assisted strategy with stable gains.")

    report_path = REPORTS_DIR_FINAL / "joint_detector_robust_eval_report.md"
    report_path.write_text("\n".join(report) + "\n", encoding="utf-8")

    print(f"Wrote: {metrics_path}")
    print(f"Wrote: {err_path}")
    print(f"Wrote: {report_path}")
    # brief console snapshot
    snap = agg[
        (agg["strategy"].isin(["baseline", "optimized", "meta_experimental"]))
        & (agg["threshold_name"].isin(["balanced", "dev_optimized"]))
    ][["strategy", "threshold_name", "accuracy_mean", "f1_mean"]]
    print(snap.to_string(index=False))


if __name__ == "__main__":
    main()
