#!/usr/bin/env python3
"""Optimize and evaluate email/url/joint detector on synthetic dataset.

This script:
- Splits data into dev + holdout test
- Collects baseline model outputs through backend API contracts
- Builds heuristic features
- Compares:
  - Baseline joint detector
  - Rule-assisted optimized joint detector
  - Lightweight meta-classifier
- Sweeps thresholds and reports holdout metrics honestly
"""

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
from backend.app.utils.joint_optimization import (
    apply_rule_assisted_joint_score,
    extract_joint_heuristic_features,
    flatten_feature_vector,
)


REPORTS_DIR = ROOT / "reports" / "experiments"
DEFAULT_CANDIDATES = [
    ROOT / "data" / "eval" / "email_url_joint_test_dataset_v2.csv",
    ROOT / "reports" / "experiments" / "email_url_joint_test_dataset.xlsx",
    ROOT / "data" / "processed" / "email_url_joint_test_dataset.xlsx",
    Path("/Users/paveilkataria/Downloads/email_url_joint_test_dataset.xlsx"),
]


def to_label(v: Any) -> str:
    s = str(v).strip().lower()
    return "phishing" if s in {"malicious", "phishing", "1", "true", "yes"} else "legitimate"


def parse_urls(raw: Any) -> List[str]:
    text = "" if raw is None else str(raw).strip()
    if not text or text.lower() == "nan":
        return []
    return [u.strip() for u in re.split(r"\s*\|\s*|[\n,]+", text) if u.strip()]


def discover_dataset(explicit: str | None) -> Path:
    if explicit:
        p = Path(explicit).expanduser()
        if not p.exists():
            raise FileNotFoundError(f"Dataset path does not exist: {p}")
        return p
    for p in DEFAULT_CANDIDATES:
        if p.exists():
            return p
    # Fallback search for likely dataset names.
    for pat in ("*joint*test*.xlsx", "*joint*test*.csv", "*synthetic*joint*.xlsx"):
        hits = list(ROOT.rglob(pat))
        if hits:
            return hits[0]
    raise FileNotFoundError("Could not auto-discover synthetic evaluation dataset. Pass --dataset.")


def load_cases(dataset_path: Path) -> pd.DataFrame:
    if dataset_path.suffix.lower() in {".xlsx", ".xls"}:
        df = pd.read_excel(dataset_path, sheet_name="test_cases")
    else:
        df = pd.read_csv(dataset_path)
    required = {"subject", "body", "expected_joint_label"}
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Dataset missing required columns: {missing}")
    if "sender" not in df.columns and "sender_name" in df.columns:
        df["sender"] = df["sender_name"]
    if "sender" not in df.columns:
        df["sender"] = ""
    if "urls" not in df.columns:
        df["urls"] = ""
    if "case_id" not in df.columns:
        df["case_id"] = [f"case_{i:03d}" for i in range(len(df))]
    if "difficulty" not in df.columns:
        df["difficulty"] = "unknown"
    if "scenario" not in df.columns:
        df["scenario"] = "unknown"
    if "notes" not in df.columns:
        df["notes"] = ""
    return df.copy()


def metric_dict(y_true: Iterable[int], y_pred: Iterable[int], y_score: Iterable[float]) -> Dict[str, Any]:
    yt = np.array(list(y_true), dtype=int)
    yp = np.array(list(y_pred), dtype=int)
    ys = np.array(list(y_score), dtype=float)
    out = {
        "accuracy": float(accuracy_score(yt, yp)),
        "balanced_accuracy": float(balanced_accuracy_score(yt, yp)),
        "precision": float(precision_score(yt, yp, zero_division=0)),
        "recall": float(recall_score(yt, yp, zero_division=0)),
        "f1": float(f1_score(yt, yp, zero_division=0)),
        "confusion_matrix": confusion_matrix(yt, yp).tolist(),
    }
    if len(set(yt.tolist())) > 1:
        out["roc_auc"] = float(roc_auc_score(yt, ys))
    else:
        out["roc_auc"] = None
    return out


def threshold_sweep(scores: np.ndarray, y_true: np.ndarray, model_name: str, split_name: str) -> pd.DataFrame:
    rows = []
    for t in np.round(np.arange(0.05, 0.951, 0.05), 2):
        yp = (scores >= float(t)).astype(int)
        rows.append(
            {
                "model": model_name,
                "split": split_name,
                "threshold": float(t),
                "accuracy": float(accuracy_score(y_true, yp)),
                "balanced_accuracy": float(balanced_accuracy_score(y_true, yp)),
                "precision": float(precision_score(y_true, yp, zero_division=0)),
                "recall": float(recall_score(y_true, yp, zero_division=0)),
                "f1": float(f1_score(y_true, yp, zero_division=0)),
                "false_positives": int(np.sum((y_true == 0) & (yp == 1))),
                "false_negatives": int(np.sum((y_true == 1) & (yp == 0))),
            }
        )
    return pd.DataFrame(rows)


def pick_thresholds(sweep_dev: pd.DataFrame) -> Dict[str, float]:
    best_acc = float(sweep_dev.sort_values(["accuracy", "f1"], ascending=False).iloc[0]["threshold"])
    best_f1 = float(sweep_dev.sort_values(["f1", "balanced_accuracy"], ascending=False).iloc[0]["threshold"])
    sweep = sweep_dev.copy()
    sweep["tradeoff"] = 0.5 * sweep["accuracy"] + 0.5 * sweep["f1"]
    best_tradeoff = float(sweep.sort_values(["tradeoff", "balanced_accuracy"], ascending=False).iloc[0]["threshold"])
    return {
        "best_accuracy_threshold": best_acc,
        "best_f1_threshold": best_f1,
        "best_tradeoff_threshold": best_tradeoff,
    }


def run_baseline_predictions(df: pd.DataFrame) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    with TestClient(app) as client:
        for _, r in df.iterrows():
            subject = "" if pd.isna(r.get("subject")) else str(r.get("subject"))
            body = "" if pd.isna(r.get("body")) else str(r.get("body"))
            sender = "" if pd.isna(r.get("sender")) else str(r.get("sender"))
            urls = parse_urls(r.get("urls"))

            email_resp = client.post(
                "/detect/email",
                json={
                    "subject": subject,
                    "body": body,
                    "sender": sender,
                    "operating_mode": "balanced",
                    "enable_explain": True,
                },
            ).json()
            email_score = float(email_resp.get("email_score", email_resp.get("probability", 0.0)))

            url_scores: List[float] = []
            url_reason_features: List[str] = []
            for u in urls:
                out = client.post("/detect/url", json={"url": u, "enable_explain": True}).json()
                url_scores.append(float(out.get("url_score", out.get("probability", 0.0))))
                for rr in (out.get("reasons") or []):
                    if isinstance(rr, dict):
                        f = str(rr.get("feature", "")).strip()
                        if f:
                            url_reason_features.append(f)
            url_score = max(url_scores) if url_scores else 0.0

            joint_baseline = client.post(
                "/detect/joint",
                json={
                    "subject": subject,
                    "body": body,
                    "sender": sender,
                    "urls": urls,
                    "operating_mode": "balanced",
                    "joint_strategy": "baseline",
                    "enable_explain": True,
                },
            ).json()
            baseline_joint_score = float(joint_baseline.get("final_score", 0.0))

            joint_opt_api = client.post(
                "/detect/joint",
                json={
                    "subject": subject,
                    "body": body,
                    "sender": sender,
                    "urls": urls,
                    "operating_mode": "balanced",
                    "joint_strategy": "optimized",
                    "enable_explain": True,
                },
            ).json()
            optimized_joint_api_score = float(joint_opt_api.get("final_score", 0.0))

            heur = extract_joint_heuristic_features(
                subject=subject,
                body=body,
                sender=sender,
                urls=urls,
                email_score=email_score,
                url_scores=url_scores,
                url_reason_features=url_reason_features,
            )
            optimized_joint_rule_score, _, rule_notes, rule_flags = apply_rule_assisted_joint_score(
                email_score=email_score,
                url_scores=url_scores,
                heuristic=heur,
                threshold=0.5,
            )
            exp_email = to_label(r.get("expected_email_label", "legitimate"))
            exp_url = to_label(r.get("expected_url_label", "legitimate"))
            exp_joint = to_label(r.get("expected_joint_label", "legitimate"))
            rows.append(
                {
                    "case_id": str(r.get("case_id", "")),
                    "difficulty": str(r.get("difficulty", "")),
                    "scenario": str(r.get("scenario", "")),
                    "notes": str(r.get("notes", "")),
                    "subject": subject,
                    "body": body,
                    "sender": sender,
                    "urls_raw": "" if pd.isna(r.get("urls")) else str(r.get("urls")),
                    "url_count": len(urls),
                    "expected_email_label": exp_email,
                    "expected_url_label": exp_url,
                    "expected_joint_label": exp_joint,
                    "y_email": 1 if exp_email == "phishing" else 0,
                    "y_url": 1 if exp_url == "phishing" else 0,
                    "y_joint": 1 if exp_joint == "phishing" else 0,
                    "email_score": email_score,
                    "url_score": url_score,
                    "baseline_joint_score": baseline_joint_score,
                    "optimized_joint_api_score": optimized_joint_api_score,
                    "optimized_joint_rule_score": optimized_joint_rule_score,
                    "optimized_rule_flags_json": json.dumps(rule_flags, ensure_ascii=True),
                    "rule_notes_json": json.dumps(rule_notes, ensure_ascii=True),
                    **{f"h_{k}": float(v) for k, v in heur.items()},
                }
            )
    return pd.DataFrame(rows)


def train_meta_classifier(
    dev_df: pd.DataFrame,
    test_df: pd.DataFrame,
    feature_cols: List[str],
) -> Tuple[np.ndarray, np.ndarray]:
    X_dev = dev_df[feature_cols].fillna(0.0).to_numpy(dtype=float)
    y_dev = dev_df["y_joint"].to_numpy(dtype=int)
    X_test = test_df[feature_cols].fillna(0.0).to_numpy(dtype=float)

    clf = LogisticRegression(max_iter=2000, class_weight="balanced", solver="liblinear")
    clf.fit(X_dev, y_dev)
    dev_proba = clf.predict_proba(X_dev)[:, 1]
    test_proba = clf.predict_proba(X_test)[:, 1]
    return dev_proba, test_proba


def split_dev_test(df: pd.DataFrame, test_size: float, random_state: int) -> Tuple[pd.DataFrame, pd.DataFrame]:
    stratify = df["y_joint"] if len(df["y_joint"].unique()) > 1 else None
    dev_idx, test_idx = train_test_split(
        df.index.values,
        test_size=test_size,
        random_state=random_state,
        stratify=stratify,
    )
    return df.loc[dev_idx].copy(), df.loc[test_idx].copy()


def summarize_errors(test_df: pd.DataFrame, baseline_col: str, optimized_col: str) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    for _, r in test_df.iterrows():
        y = int(r["y_joint"])
        b = int(r[baseline_col])
        o = int(r[optimized_col])
        if b == y and o == y:
            status = "both_correct"
        elif b != y and o == y:
            status = "corrected_by_optimized"
        elif b == y and o != y:
            status = "newly_broken_by_optimized"
        else:
            status = "both_wrong"
        rows.append(
            {
                "case_id": r["case_id"],
                "difficulty": r["difficulty"],
                "scenario": r["scenario"],
                "expected_label": "phishing" if y == 1 else "legitimate",
                "baseline_pred": "phishing" if b == 1 else "legitimate",
                "optimized_pred": "phishing" if o == 1 else "legitimate",
                "status": status,
                "baseline_score": r["baseline_joint_score"],
                "optimized_score": r["optimized_joint_rule_score"],
                "email_score": r["email_score"],
                "url_score": r["url_score"],
            }
        )
    return pd.DataFrame(rows)


def format_metric_row(name: str, m: Dict[str, Any]) -> str:
    auc = "n/a" if m["roc_auc"] is None else f"{m['roc_auc']:.3f}"
    return (
        f"| {name} | {m['accuracy']:.3f} | {m['balanced_accuracy']:.3f} | {m['precision']:.3f} | "
        f"{m['recall']:.3f} | {m['f1']:.3f} | {auc} | "
        f"{m['confusion_matrix']} |"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default=None, help="Path to synthetic dataset (xlsx/csv).")
    ap.add_argument("--test-size", type=float, default=0.30)
    ap.add_argument("--random-state", type=int, default=42)
    args = ap.parse_args()

    dataset_path = discover_dataset(args.dataset)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    raw_df = load_cases(dataset_path)
    pred_df = run_baseline_predictions(raw_df)
    dev_df, test_df = split_dev_test(pred_df, test_size=args.test_size, random_state=args.random_state)

    heuristic_cols = sorted([c for c in pred_df.columns if c.startswith("h_")])
    meta_feature_cols = ["email_score", "url_score", "baseline_joint_score", *heuristic_cols]
    dev_meta_scores, test_meta_scores = train_meta_classifier(dev_df, test_df, meta_feature_cols)
    dev_df["meta_joint_score"] = dev_meta_scores
    test_df["meta_joint_score"] = test_meta_scores

    score_cols = [
        ("email", "email_score", "y_email"),
        ("url", "url_score", "y_url"),
        ("joint_baseline", "baseline_joint_score", "y_joint"),
        ("joint_rule_optimized", "optimized_joint_rule_score", "y_joint"),
        ("joint_meta", "meta_joint_score", "y_joint"),
    ]

    sweeps: List[pd.DataFrame] = []
    threshold_choices: Dict[str, Dict[str, float]] = {}
    for model_name, score_col, y_col in score_cols:
        sweep = threshold_sweep(dev_df[score_col].to_numpy(float), dev_df[y_col].to_numpy(int), model_name, "dev")
        sweeps.append(sweep)
        threshold_choices[model_name] = pick_thresholds(sweep)

    sweep_df = pd.concat(sweeps, ignore_index=True)
    sweep_df.to_csv(REPORTS_DIR / "joint_threshold_sweep.csv", index=False)

    def eval_model(df: pd.DataFrame, model_name: str, score_col: str, y_col: str, threshold: float) -> Dict[str, Any]:
        y = df[y_col].to_numpy(int)
        s = df[score_col].to_numpy(float)
        yp = (s >= threshold).astype(int)
        return metric_dict(y, yp, s)

    comparisons: Dict[str, Dict[str, Dict[str, Any]]] = {"dev": {}, "test": {}}
    selected_thresholds: Dict[str, float] = {}
    for model_name, score_col, y_col in score_cols:
        t = threshold_choices[model_name]["best_tradeoff_threshold"]
        selected_thresholds[model_name] = t
        comparisons["dev"][model_name] = eval_model(dev_df, model_name, score_col, y_col, t)
        comparisons["test"][model_name] = eval_model(test_df, model_name, score_col, y_col, t)

    # Store final predictions using selected thresholds.
    for model_name, score_col, y_col in score_cols:
        t = selected_thresholds[model_name]
        dev_df[f"pred_{model_name}"] = (dev_df[score_col].to_numpy(float) >= t).astype(int)
        test_df[f"pred_{model_name}"] = (test_df[score_col].to_numpy(float) >= t).astype(int)

    dev_df.to_csv(REPORTS_DIR / "joint_detector_predictions_dev.csv", index=False)
    test_df.to_csv(REPORTS_DIR / "joint_detector_predictions_test.csv", index=False)

    err_df = summarize_errors(test_df, "pred_joint_baseline", "pred_joint_rule_optimized")
    err_df.to_csv(REPORTS_DIR / "joint_error_analysis.csv", index=False)

    best_test_joint = max(
        [
            ("baseline", comparisons["test"]["joint_baseline"]["accuracy"]),
            ("rule_optimized", comparisons["test"]["joint_rule_optimized"]["accuracy"]),
            ("meta", comparisons["test"]["joint_meta"]["accuracy"]),
        ],
        key=lambda x: x[1],
    )

    report_lines: List[str] = []
    report_lines.append("# Joint Detector Optimization Report")
    report_lines.append("")
    report_lines.append(f"- Dataset: `{dataset_path}`")
    report_lines.append(f"- Total rows: **{len(pred_df)}**")
    report_lines.append(f"- Dev rows: **{len(dev_df)}**, Holdout test rows: **{len(test_df)}**")
    report_lines.append(
        f"- Joint label distribution (all): {pred_df['y_joint'].value_counts().sort_index().to_dict()} (0=legitimate,1=phishing)"
    )
    report_lines.append("")
    report_lines.append("## Threshold Selection (Dev)")
    report_lines.append("| Model | Best Accuracy | Best F1 | Best Tradeoff |")
    report_lines.append("|---|---:|---:|---:|")
    for model_name in ["email", "url", "joint_baseline", "joint_rule_optimized", "joint_meta"]:
        th = threshold_choices[model_name]
        report_lines.append(
            f"| {model_name} | {th['best_accuracy_threshold']:.2f} | {th['best_f1_threshold']:.2f} | {th['best_tradeoff_threshold']:.2f} |"
        )
    report_lines.append("")

    report_lines.append("## Metrics (Dev, using best tradeoff threshold)")
    report_lines.append("| Model | Accuracy | Balanced Acc | Precision | Recall | F1 | ROC-AUC | Confusion Matrix |")
    report_lines.append("|---|---:|---:|---:|---:|---:|---:|---|")
    for model_name in ["email", "url", "joint_baseline", "joint_rule_optimized", "joint_meta"]:
        report_lines.append(format_metric_row(model_name, comparisons["dev"][model_name]))
    report_lines.append("")

    report_lines.append("## Metrics (Holdout Test, fixed thresholds from dev)")
    report_lines.append("| Model | Accuracy | Balanced Acc | Precision | Recall | F1 | ROC-AUC | Confusion Matrix |")
    report_lines.append("|---|---:|---:|---:|---:|---:|---:|---|")
    for model_name in ["email", "url", "joint_baseline", "joint_rule_optimized", "joint_meta"]:
        report_lines.append(format_metric_row(model_name, comparisons["test"][model_name]))
    report_lines.append("")

    report_lines.append("## Best Strategy")
    report_lines.append(
        f"- Best holdout joint strategy by accuracy: **{best_test_joint[0]}** ({best_test_joint[1]:.3f})"
    )
    report_lines.append("- Compared variants:")
    report_lines.append("  - baseline joint API")
    report_lines.append("  - optimized rule-assisted joint")
    report_lines.append("  - logistic-regression meta-classifier")
    report_lines.append("")

    corrected = int((err_df["status"] == "corrected_by_optimized").sum())
    broken = int((err_df["status"] == "newly_broken_by_optimized").sum())
    report_lines.append("## Error Analysis Summary (Test)")
    report_lines.append(f"- Corrected by optimized rules: **{corrected}**")
    report_lines.append(f"- Newly broken by optimized rules: **{broken}**")
    report_lines.append("- Detailed errors: `reports/joint_error_analysis.csv`")
    report_lines.append("")

    report_lines.append("## Practical Notes")
    report_lines.append("- Small synthetic dataset size can cause unstable split variance.")
    report_lines.append("- Holdout metrics are reported separately to reduce tuning leakage.")
    report_lines.append("- Real-world validation is still required before claiming production robustness.")

    report_path = REPORTS_DIR / "joint_detector_optimization_report.md"
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print(f"Dataset: {dataset_path}")
    print(f"Wrote: {report_path}")
    print(f"Wrote: {REPORTS_DIR / 'joint_detector_predictions_dev.csv'}")
    print(f"Wrote: {REPORTS_DIR / 'joint_detector_predictions_test.csv'}")
    print(f"Wrote: {REPORTS_DIR / 'joint_threshold_sweep.csv'}")
    print(f"Wrote: {REPORTS_DIR / 'joint_error_analysis.csv'}")
    print("Holdout accuracies:")
    for name in ["joint_baseline", "joint_rule_optimized", "joint_meta"]:
        print(f"  {name}: {comparisons['test'][name]['accuracy']:.4f}")
    print(f"Best holdout strategy: {best_test_joint[0]} @ {best_test_joint[1]:.4f}")


if __name__ == "__main__":
    main()
