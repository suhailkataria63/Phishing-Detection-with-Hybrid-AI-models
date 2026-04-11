#!/usr/bin/env python3
"""Lightweight threshold calibration for joint email+URL scoring modes."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Dict, List

from fastapi.testclient import TestClient
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.main import app

DEFAULT_DATA = ROOT / "data" / "samples" / "joint_threshold_calibration_set.csv"
DEFAULT_REPORT = ROOT / "reports" / "experiments" / "joint_threshold_calibration.md"

MODE_TO_THRESHOLD = {
    "soc": 0.40,
    "balanced": 0.50,
    "high_confidence": 0.60,
}


def to_label(v: str) -> str:
    s = (v or "").strip().lower()
    return "phishing" if s in {"phishing", "malicious", "1", "true"} else "legitimate"


def to_binary(labels: List[str]) -> List[int]:
    return [1 if x == "phishing" else 0 for x in labels]


def parse_urls(raw: str) -> List[str]:
    text = (raw or "").strip()
    if not text:
        return []
    return [u.strip() for u in text.split("|") if u.strip()]


def evaluate(rows: List[Dict[str, str]], mode: str) -> Dict[str, float]:
    y_true: List[str] = []
    y_pred: List[str] = []
    with TestClient(app) as client:
        for r in rows:
            payload = {
                "subject": r.get("subject", ""),
                "body": r.get("body", ""),
                "sender": r.get("sender", ""),
                "urls": parse_urls(r.get("urls", "")),
                "operating_mode": mode,
                "enable_explain": False,
            }
            resp = client.post("/detect/joint", json=payload)
            out = resp.json() if resp.status_code == 200 else {"final_label": "legitimate"}
            y_true.append(to_label(r.get("expected_joint_label", "legitimate")))
            y_pred.append(to_label(out.get("final_label", "legitimate")))

    yt = to_binary(y_true)
    yp = to_binary(y_pred)
    fp = sum(1 for a, b in zip(yt, yp) if a == 0 and b == 1)
    fn = sum(1 for a, b in zip(yt, yp) if a == 1 and b == 0)
    return {
        "threshold": MODE_TO_THRESHOLD[mode],
        "accuracy": accuracy_score(yt, yp),
        "precision": precision_score(yt, yp, zero_division=0),
        "recall": recall_score(yt, yp, zero_division=0),
        "f1": f1_score(yt, yp, zero_division=0),
        "false_positives": fp,
        "false_negatives": fn,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=DEFAULT_DATA)
    ap.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = ap.parse_args()

    if not args.data.exists():
        raise SystemExit(f"Calibration dataset not found: {args.data}")

    with args.data.open("r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    results = {mode: evaluate(rows, mode) for mode in ["soc", "balanced", "high_confidence"]}

    args.report.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    lines.append("# Joint Threshold Calibration")
    lines.append("")
    lines.append(f"Cases: {len(rows)}")
    lines.append("")
    lines.append("| Mode | Threshold | Accuracy | Precision | Recall | F1 | FP | FN |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for mode in ["soc", "balanced", "high_confidence"]:
        m = results[mode]
        lines.append(
            f"| {mode} | {m['threshold']:.2f} | {m['accuracy']:.3f} | {m['precision']:.3f} | {m['recall']:.3f} | {m['f1']:.3f} | {m['false_positives']} | {m['false_negatives']} |"
        )
    lines.append("")
    lines.append("Recommended operating modes:")
    lines.append("- `soc` (`~0.4`): highest recall for triage-heavy SOC workflows.")
    lines.append("- `balanced` (`0.5`): default production tradeoff.")
    lines.append("- `high_confidence` (`0.6+`): fewer false positives for strict alerting.")

    args.report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote report: {args.report}")
    for mode in ["soc", "balanced", "high_confidence"]:
        print(mode, results[mode])


if __name__ == "__main__":
    main()
