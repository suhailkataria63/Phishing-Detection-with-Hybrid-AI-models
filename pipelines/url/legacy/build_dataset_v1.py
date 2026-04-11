#!/usr/bin/env python3
"""
Build dataset_v1.csv from:
- data/raw/phishtank_online_valid.json (PhishTank)
- data/raw/top-1m.csv (Tranco/top list)

Output:
- data/processed/dataset_v1.csv with columns: url,label,source,phish_id
"""

from __future__ import annotations

import os
import re
import json
import random
import html
from typing import Iterable, Dict, Any, List, Optional, Tuple
from urllib.parse import urlsplit, urlunsplit

import pandas as pd


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
RAW_DIR = os.path.join(ROOT, "data", "raw")
OUT_DIR = os.path.join(ROOT, "data", "processed")

PHISHTANK_JSON = os.path.join(RAW_DIR, "phishtank_online_valid.json")
TOP_CSV = os.path.join(RAW_DIR, "top-1m.csv")
OUT_CSV = os.path.join(OUT_DIR, "dataset_v1.csv")

# How many benign domains to use (top N)
BENIGN_TOP_N = 100_000

# Create benign URLs from each domain
# v1 (recommended): keep it simple to reduce label noise
BENIGN_PREFIXES = ["https://", "https://www."]

# Reproducibility
RANDOM_SEED = 1337


def normalize_url(u: str) -> Optional[str]:
    """
    Normalize URL lightly:
    - strip whitespace/control chars
    - html-unescape (&amp; etc.)
    - ensure it has a scheme (http/https). If missing, prepend http://
    - remove fragment (#...)
    - lowercase only the hostname (netloc)
    Keep path/query as-is (phishing often encodes signal there).
    """
    if not u:
        return None

    u = u.strip()
    if not u:
        return None

    # Remove common control characters
    u = re.sub(r"[\x00-\x1f\x7f]", "", u)

    # Decode HTML entities (&amp; etc.)
    u = html.unescape(u)

    # Some feeds contain spaces or weird separators
    u = u.replace(" ", "")

    # Add scheme if missing
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+\-.]*://", u):
        u = "http://" + u

    try:
        parts = urlsplit(u)
    except Exception:
        return None

    if not parts.netloc:
        return None

    # Lowercase netloc (host + optional port)
    netloc = parts.netloc.lower()

    # Drop fragment
    cleaned = urlunsplit((parts.scheme.lower(), netloc, parts.path, parts.query, ""))

    # Basic sanity: must contain at least one dot in host (avoid "http://localhost")
    host = netloc.split("@")[-1].split(":")[0]
    if "." not in host:
        return None

    return cleaned


def iter_phishtank_records(path: str) -> Iterable[Tuple[str, int]]:
    """
    Yields (url, phish_id).
    Uses streaming (ijson) if installed; otherwise loads whole JSON.
    """
    file_size_mb = os.path.getsize(path) / (1024 * 1024)

    # Try streaming parser if available (helps with large files)
    try:
        import ijson  # type: ignore

        with open(path, "rb") as f:
            for item in ijson.items(f, "item"):
                url = item.get("url")
                pid = item.get("phish_id")
                if isinstance(url, str) and isinstance(pid, int):
                    yield url, pid
        return
    except ImportError:
        # No ijson, fallback to json.load
        pass

    # Fallback: load whole file (OK for smaller dumps)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("PhishTank JSON is not a list. Expected top-level array.")

    for item in data:
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        pid = item.get("phish_id")
        if isinstance(url, str) and isinstance(pid, int):
            yield url, pid


def load_tranco_domains(path: str, top_n: int) -> List[str]:
    """
    Robust CSV reader:
    - Some lists are "rank,domain"
    - Some are just "domain"
    We'll take the most domain-looking column.
    """
    # Read a small sample first to infer columns safely
    df = pd.read_csv(path, header=None, nrows=10)

    # If single column: it's the domain
    if df.shape[1] == 1:
        col_idx = 0
    else:
        # Prefer the column that looks most like domains (has dots)
        scores = []
        for i in range(df.shape[1]):
            s = df[i].astype(str)
            score = (s.str.contains(r"\.", regex=True)).mean()
            scores.append((score, i))
        scores.sort(reverse=True)
        col_idx = scores[0][1]

    # Now read full (or top_n) using that column only
    df2 = pd.read_csv(path, header=None, usecols=[col_idx], nrows=top_n)
    domains = df2.iloc[:, 0].astype(str).str.strip().tolist()

    # Clean domain strings
    out = []
    for d in domains:
        d = d.strip().lower()
        # Remove protocol if present
        d = re.sub(r"^https?://", "", d)
        # Remove path if present
        d = d.split("/")[0]
        # Remove leading www.
        d = d[4:] if d.startswith("www.") else d
        # Basic sanity
        if "." in d and " " not in d and len(d) <= 253:
            out.append(d)

    # Dedup while preserving order
    seen = set()
    deduped = []
    for d in out:
        if d not in seen:
            seen.add(d)
            deduped.append(d)

    return deduped


def make_benign_urls(domains: List[str]) -> List[str]:
    urls: List[str] = []
    for d in domains:
        for p in BENIGN_PREFIXES:
            urls.append(f"{p}{d}/")
    return urls


def main() -> None:
    random.seed(RANDOM_SEED)

    os.makedirs(OUT_DIR, exist_ok=True)

    if not os.path.exists(PHISHTANK_JSON):
        raise FileNotFoundError(f"Missing: {PHISHTANK_JSON}")
    if not os.path.exists(TOP_CSV):
        raise FileNotFoundError(f"Missing: {TOP_CSV}")

    # --------- Load phishing URLs ----------
    phishing_rows = []
    bad_phish = 0
    total_phish = 0

    for raw_url, pid in iter_phishtank_records(PHISHTANK_JSON):
        total_phish += 1
        nu = normalize_url(raw_url)
        if not nu:
            bad_phish += 1
            continue
        phishing_rows.append(
            {"url": nu, "label": 1, "source": "phishtank", "phish_id": pid}
        )

    phish_df = pd.DataFrame(phishing_rows).drop_duplicates(subset=["url"])

    # --------- Load benign domains and generate benign URLs ----------
    domains = load_tranco_domains(TOP_CSV, top_n=BENIGN_TOP_N)
    benign_urls_raw = make_benign_urls(domains)

    benign_rows = []
    bad_benign = 0
    for u in benign_urls_raw:
        nu = normalize_url(u)
        if not nu:
            bad_benign += 1
            continue
        benign_rows.append({"url": nu, "label": 0, "source": "tranco", "phish_id": None})

    benign_df = pd.DataFrame(benign_rows).drop_duplicates(subset=["url"])

    # --------- Merge and final dedupe ----------
    df = pd.concat([phish_df, benign_df], ignore_index=True)

    # IMPORTANT: if any URL appears in both, prefer phishing label
    # We sort so phishing rows come first, then drop duplicates by url
    df = df.sort_values(by=["label"], ascending=False).drop_duplicates(subset=["url"], keep="first")

    # Shuffle (so training split later isn’t ordered)
    df = df.sample(frac=1.0, random_state=RANDOM_SEED).reset_index(drop=True)

    # --------- Save ----------
    df.to_csv(OUT_CSV, index=False)

    # --------- Print summary ----------
    print("\n=== Dataset Build Summary (v1) ===")
    print(f"PhishTank input records: {total_phish}")
    print(f"PhishTank invalid/filtered: {bad_phish}")
    print(f"PhishTank unique URLs kept: {len(phish_df)}")
    print(f"Tranco domains used: {len(domains)} (top_n={BENIGN_TOP_N})")
    print(f"Benign invalid/filtered: {bad_benign}")
    print(f"Benign unique URLs kept: {len(benign_df)}")
    print(f"Final dataset rows: {len(df)}")
    print(df["label"].value_counts().to_string())
    print(f"\nSaved: {OUT_CSV}\n")


if __name__ == "__main__":
    main()
