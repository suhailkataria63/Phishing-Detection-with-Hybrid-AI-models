#!/usr/bin/env python3
"""
Train URL-only phishing model (Option 1: hand-crafted features).
Input:  data/processed/dataset_v1.csv  (url,label,source,phish_id)
Output:
  - models/url_model_v1.joblib
  - models/url_feature_schema_v1.json
  - reports/url_model_v1_report.txt
"""

from __future__ import annotations

import os
import re
import json
import math
from collections import Counter
from urllib.parse import urlsplit

import pandas as pd
from joblib import dump
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    roc_auc_score,
    average_precision_score,
)
from sklearn.ensemble import HistGradientBoostingClassifier


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_CSV = os.path.join(ROOT, "data", "processed", "dataset_v1.csv")

MODEL_OUT = os.path.join(ROOT, "models", "url_model_v1.joblib")
SCHEMA_OUT = os.path.join(ROOT, "models", "url_feature_schema_v1.json")
REPORT_OUT = os.path.join(ROOT, "reports", "url_model_v1_report.txt")

RANDOM_SEED = 1337

# A small, pragmatic suspicious TLD list (v1). We can expand later.
SUSPICIOUS_TLDS = {
    "zip","mov","xyz","top","click","cfd","sbs","cyou","pro","icu","rest","quest","cam","work","live","info"
}

# Keywords we’ll count in path+query (v1). Expand later if needed.
RISK_KEYWORDS = [
    "login","verify","secure","update","account","signin","sign-in","password","pay","billing",
    "confirm","wallet","bank","invoice","support","alert","webscr","icloud","office","microsoft"
]

IPV4_RE = re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}$")


def shannon_entropy(s: str) -> float:
    """Shannon entropy of a string. Higher often indicates randomness/obfuscation."""
    if not s:
        return 0.0
    counts = Counter(s)
    n = len(s)
    ent = 0.0
    for c in counts.values():
        p = c / n
        ent -= p * math.log2(p)
    return ent


def has_ipv4_host(host: str) -> int:
    """1 if host looks like IPv4 (roughly), else 0."""
    if not host:
        return 0
    if IPV4_RE.match(host):
        # Extra sanity: each octet <= 255
        parts = host.split(".")
        try:
            return 1 if all(0 <= int(x) <= 255 for x in parts) else 0
        except ValueError:
            return 0
    return 0


def safe_urlsplit(u: str):
    """Split URL safely; returns (scheme, host, path, query)."""
    try:
        p = urlsplit(u)
        scheme = (p.scheme or "").lower()
        netloc = (p.netloc or "").lower()

        # Drop creds if any: user:pass@host
        host = netloc.split("@")[-1]
        # Drop port if any
        host = host.split(":")[0]

        path = p.path or ""
        query = p.query or ""
        return scheme, host, path, query
    except Exception:
        return "", "", "", ""


def count_keywords(text: str) -> int:
    t = text.lower()
    return sum(1 for k in RISK_KEYWORDS if k in t)


def keyword_hits(text: str):
    t = text.lower()
    return [k for k in RISK_KEYWORDS if k in t]


def tld_of(host: str) -> str:
    if not host or "." not in host:
        return ""
    return host.rsplit(".", 1)[-1]


def extract_features(url: str) -> dict:
    scheme, host, path, query = safe_urlsplit(url)

    full = (url or "")
    host_len = len(host)
    path_len = len(path)
    query_len = len(query)
    url_len = len(full)

    num_dots = host.count(".")
    num_hyphens = full.count("-")
    num_underscores = full.count("_")
    num_digits = sum(ch.isdigit() for ch in full)
    num_at = full.count("@")
    num_pct = full.count("%")
    num_eq = full.count("=")
    num_amp = full.count("&")
    num_qmark = full.count("?")
    num_slash = full.count("/")
    num_colon = full.count(":")
    num_subdomains = max(0, num_dots - 1)  # a.b.c.tld => 2 subdomains (roughly)

    # Suspicious constructs
    has_https = 1 if scheme == "https" else 0
    has_http_in_path = 1 if "http" in (path.lower() + query.lower()) else 0
    has_double_slash_in_path = 1 if "//" in (path + query) else 0
    has_ip = has_ipv4_host(host)

    # TLD
    tld = tld_of(host)
    tld_susp = 1 if tld in SUSPICIOUS_TLDS else 0

    # Entropy (host + path)
    ent_host = shannon_entropy(host)
    ent_path = shannon_entropy(path)
    ent_all = shannon_entropy(full)

    # Keyword counts
    kcount = count_keywords(path + "?" + query)

    # Length ratios (avoid div by zero)
    host_ratio = host_len / url_len if url_len else 0.0
    path_ratio = path_len / url_len if url_len else 0.0
    query_ratio = query_len / url_len if url_len else 0.0

    # Query params count
    qparams = 0
    if query:
        qparams = query.count("&") + 1

    return {
        "url_len": url_len,
        "host_len": host_len,
        "path_len": path_len,
        "query_len": query_len,
        "host_ratio": host_ratio,
        "path_ratio": path_ratio,
        "query_ratio": query_ratio,
        "num_dots": num_dots,
        "num_subdomains": num_subdomains,
        "num_hyphens": num_hyphens,
        "num_underscores": num_underscores,
        "num_digits": num_digits,
        "num_at": num_at,
        "num_pct": num_pct,
        "num_eq": num_eq,
        "num_amp": num_amp,
        "num_qmark": num_qmark,
        "num_slash": num_slash,
        "num_colon": num_colon,
        "qparams": qparams,
        "has_https": has_https,
        "has_http_in_path": has_http_in_path,
        "has_double_slash_in_path": has_double_slash_in_path,
        "has_ip_host": has_ip,
        "tld_suspicious": tld_susp,
        "entropy_host": ent_host,
        "entropy_path": ent_path,
        "entropy_url": ent_all,
        "keyword_count": kcount,
    }


def build_matrix(urls: pd.Series):
    feats = [extract_features(u) for u in urls.astype(str).tolist()]
    X = pd.DataFrame(feats)
    # Make sure no NaNs
    X = X.fillna(0)
    feature_names = X.columns.tolist()
    return X, feature_names


def make_sample_weights(y: pd.Series):
    """Handle class imbalance via weights (benign vs phishing)."""
    counts = y.value_counts().to_dict()
    n0 = counts.get(0, 1)
    n1 = counts.get(1, 1)
    # weight inversely proportional to class frequency
    w0 = 1.0
    w1 = n0 / n1  # phishing gets higher weight
    return y.apply(lambda v: w1 if v == 1 else w0).astype(float).values


def main():
    os.makedirs(os.path.join(ROOT, "models"), exist_ok=True)
    os.makedirs(os.path.join(ROOT, "reports"), exist_ok=True)

    if not os.path.exists(DATA_CSV):
        raise FileNotFoundError(f"Missing dataset: {DATA_CSV}")

    df = pd.read_csv(DATA_CSV)
    df = df.dropna(subset=["url", "label"])
    df["label"] = df["label"].astype(int)

    X, feature_names = build_matrix(df["url"])
    y = df["label"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=0.2,
        random_state=RANDOM_SEED,
        stratify=y
    )

    w_train = make_sample_weights(y_train)

    # Strong baseline, fast, handles non-linearities well.
    model = HistGradientBoostingClassifier(
        random_state=RANDOM_SEED,
        max_depth=6,
        learning_rate=0.08,
        max_iter=250,
        min_samples_leaf=50,
        l2_regularization=0.0
    )

    model.fit(X_train, y_train, sample_weight=w_train)

    # Probabilities
    proba = model.predict_proba(X_test)[:, 1]
    preds = (proba >= 0.5).astype(int)

    # Metrics
    roc = roc_auc_score(y_test, proba)
    ap = average_precision_score(y_test, proba)
    cm = confusion_matrix(y_test, preds)
    report = classification_report(y_test, preds, digits=4)

    lines = []
    lines.append("=== URL Model v1 (Option 1: engineered features) ===")
    lines.append(f"Dataset: {os.path.relpath(DATA_CSV, ROOT)}")
    lines.append(f"Train size: {len(X_train)} | Test size: {len(X_test)}")
    lines.append(f"ROC-AUC: {roc:.4f}")
    lines.append(f"PR-AUC (Average Precision): {ap:.4f}")
    lines.append("")
    lines.append("Confusion Matrix (rows=true, cols=pred):")
    lines.append(str(cm))
    lines.append("")
    lines.append("Classification Report:")
    lines.append(report)
    lines.append("")
    lines.append("Top Features (by permutation importance) will be added in v1.1 if needed.")
    out_text = "\n".join(lines)

    print(out_text)

    with open(REPORT_OUT, "w", encoding="utf-8") as f:
        f.write(out_text)

    # Save model and schema
    dump(
        {"model": model, "feature_names": feature_names, "version": "url_model_v1"},
        MODEL_OUT
    )

    with open(SCHEMA_OUT, "w", encoding="utf-8") as f:
        json.dump(
            {
                "version": "url_model_v1",
                "feature_names": feature_names,
                "suspicious_tlds": sorted(list(SUSPICIOUS_TLDS)),
                "risk_keywords": RISK_KEYWORDS,
            },
            f,
            indent=2
        )

    print(f"\nSaved model: {os.path.relpath(MODEL_OUT, ROOT)}")
    print(f"Saved schema: {os.path.relpath(SCHEMA_OUT, ROOT)}")
    print(f"Saved report: {os.path.relpath(REPORT_OUT, ROOT)}\n")


if __name__ == "__main__":
    main()
