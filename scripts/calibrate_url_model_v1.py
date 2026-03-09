import json
import math
import re
from pathlib import Path
from urllib.parse import urlparse, urlunparse, unquote

import joblib
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import train_test_split

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_ROOT / "data" / "processed" / "dataset_v1.csv"

IN_MODEL_PATH = PROJECT_ROOT / "models" / "url_model_v1.joblib"
OUT_MODEL_PATH = PROJECT_ROOT / "models" / "url_model_v1_calibrated.joblib"
SCHEMA_PATH = PROJECT_ROOT / "models" / "url_feature_schema_v1.json"

IPV4_RE = re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}$")
SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+\-.]*://")


def normalize_url_for_model(raw: str) -> str:
    s = (raw or "").strip()
    s = unquote(s)

    if not SCHEME_RE.match(s):
        s = "https://" + s

    p = urlparse(s)

    scheme = (p.scheme or "https").lower()
    netloc = (p.netloc or "").lower()

    if not netloc and p.path:
        p2 = urlparse("https://" + p.path)
        scheme = (p2.scheme or "https").lower()
        netloc = (p2.netloc or "").lower()
        p = p2

    if netloc.endswith(":80"):
        netloc = netloc[:-3]
    if netloc.endswith(":443"):
        netloc = netloc[:-4]

    if netloc.startswith("www."):
        netloc = netloc[4:]

    if scheme == "http":
        scheme = "https"

    path = p.path if p.path else "/"
    return urlunparse((scheme, netloc, path, "", p.query or "", ""))


def shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    freq = {}
    for ch in s:
        freq[ch] = freq.get(ch, 0) + 1
    n = len(s)
    ent = 0.0
    for c in freq.values():
        p = c / n
        ent -= p * math.log2(p)
    return float(ent)


def is_ipv4_host(host: str) -> int:
    if not host:
        return 0
    if not IPV4_RE.match(host):
        return 0
    parts = host.split(".")
    try:
        return 1 if all(0 <= int(x) <= 255 for x in parts) else 0
    except ValueError:
        return 0


def extract_features(url_raw: str, keywords: list[str], suspicious_tlds: set[str]) -> dict:
    url = normalize_url_for_model(url_raw)
    p = urlparse(url)

    host = (p.netloc or "").lower()
    if ":" in host:
        host = host.split(":")[0]

    path = p.path or ""
    query = p.query or ""

    url_len = len(url)
    host_len = len(host)
    path_len = len(path)
    query_len = len(query)

    host_ratio = host_len / url_len if url_len else 0.0
    path_ratio = path_len / url_len if url_len else 0.0
    query_ratio = query_len / url_len if url_len else 0.0

    num_dots = host.count(".")
    num_subdomains = max(0, num_dots - 1)

    num_hyphens = url.count("-")
    num_underscores = url.count("_")
    num_digits = sum(ch.isdigit() for ch in url)

    num_at = url.count("@")
    num_pct = url.count("%")
    num_eq = url.count("=")
    num_amp = url.count("&")
    num_qmark = url.count("?")
    num_slash = url.count("/")
    num_colon = url.count(":")

    qparams = query.count("&") + 1 if query else 0

    has_https = 1 if (p.scheme or "").lower() == "https" else 0
    has_http_in_path = 1 if ("http" in (path.lower() + query.lower())) else 0
    has_double_slash_in_path = 1 if ("//" in (path + query)) else 0

    has_ip_host = is_ipv4_host(host)

    tld = host.rsplit(".", 1)[-1] if host and "." in host else ""
    tld_suspicious = 1 if tld in suspicious_tlds else 0

    entropy_host = shannon_entropy(host)
    entropy_path = shannon_entropy(path)
    entropy_url = shannon_entropy(url)

    url_lc = url.lower()
    keyword_hits = [k for k in keywords if k in url_lc]
    keyword_count = len(keyword_hits)

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
        "has_ip_host": has_ip_host,
        "tld_suspicious": tld_suspicious,
        "entropy_host": entropy_host,
        "entropy_path": entropy_path,
        "entropy_url": entropy_url,
        "keyword_count": keyword_count,
    }


def main():
    df = pd.read_csv(DATA_PATH).sample(frac=1.0, random_state=42).reset_index(drop=True)

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    feature_names = schema["feature_names"]
    keywords = schema.get("risk_keywords", [])
    suspicious_tlds = set(schema.get("suspicious_tlds", []))

    feats = df["url"].astype(str).apply(lambda u: extract_features(u, keywords, suspicious_tlds)).apply(pd.Series)
    X = feats[feature_names]
    y = df["label"].astype(int)

    _, X_cal, _, y_cal = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    base = joblib.load(IN_MODEL_PATH)
    if isinstance(base, dict):
        for k in ("model", "pipeline", "clf", "estimator"):
            if k in base:
                base = base[k]
                break

    # sklearn 1.8+: use cv=int (no more "prefit")
    # We calibrate using internal CV on the calibration slice.
    try:
        cal = CalibratedClassifierCV(estimator=base, method="isotonic", cv=3)
    except TypeError:
        # fallback for older sklearn versions
        cal = CalibratedClassifierCV(base_estimator=base, method="isotonic", cv=3)

    cal.fit(X_cal, y_cal)


    joblib.dump({"model": cal, "version": "url_model_v1_calibrated"}, OUT_MODEL_PATH)

    print("Saved:", OUT_MODEL_PATH)


if __name__ == "__main__":
    main()
