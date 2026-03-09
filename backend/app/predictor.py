import re
import math
from urllib.parse import urlparse
from typing import List, Tuple, Dict, Any

SUSPICIOUS_KEYWORDS = [
    "login", "verify", "secure", "update", "account", "password",
    "signin", "confirm", "bank", "wallet", "otp", "reset"
]

SHORTENERS = {"bit.ly", "t.co", "tinyurl.com", "goo.gl", "is.gd", "cutt.ly"}

def shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    freq = {}
    for ch in s:
        freq[ch] = freq.get(ch, 0) + 1
    ent = 0.0
    n = len(s)
    for c in freq.values():
        p = c / n
        ent -= p * math.log2(p)
    return ent

def has_ip_hostname(hostname: str) -> bool:
    # simplistic IPv4 check
    return bool(re.fullmatch(r"(?:\d{1,3}\.){3}\d{1,3}", hostname or ""))

def count_subdomains(hostname: str) -> int:
    if not hostname:
        return 0
    parts = hostname.split(".")
    return max(0, len(parts) - 2)

def extract_basic_signals(url: str) -> Dict[str, Any]:
    u = url.strip()
    if not re.match(r"^[a-zA-Z]+://", u):
        u = "http://" + u  # normalize
    parsed = urlparse(u)

    hostname = (parsed.hostname or "").lower()
    path = parsed.path or ""
    query = parsed.query or ""
    full = (hostname + path + "?" + query).lower()

    signals = {
        "normalized_url": parsed.geturl(),
        "scheme": parsed.scheme,
        "hostname": hostname,
        "url_length": len(parsed.geturl()),
        "host_length": len(hostname),
        "dot_count": hostname.count("."),
        "subdomain_depth": count_subdomains(hostname),
        "has_ip": has_ip_hostname(hostname),
        "has_at": "@" in parsed.geturl(),
        "has_double_slash": parsed.geturl().count("//") > 1,
        "digit_ratio": (sum(ch.isdigit() for ch in parsed.geturl()) / max(1, len(parsed.geturl()))),
        "entropy": shannon_entropy(parsed.geturl()),
        "is_shortener": hostname in SHORTENERS,
        "keyword_hits": [k for k in SUSPICIOUS_KEYWORDS if k in full],
        "keyword_count": sum(1 for k in SUSPICIOUS_KEYWORDS if k in full),
        "has_https": parsed.scheme == "https",
    }
    return signals

def dummy_score(signals: Dict[str, Any]) -> Tuple[float, List[Dict[str, Any]]]:
    """Return (probability-ish score, reasons)."""
    score = 0.05
    reasons = []

    def add(points: float, feature: str, value: Any, note: str):
        nonlocal score
        score += points
        reasons.append({"feature": feature, "value": value, "note": note})

    # Heuristics (tuned for demo, not truth)
    if signals["has_ip"]:
        add(0.35, "has_ip", True, "URL uses an IP address instead of a domain")
    if signals["has_at"]:
        add(0.25, "has_at", True, "Contains '@' which can obscure real destination")
    if signals["subdomain_depth"] >= 3:
        add(0.18, "subdomain_depth", signals["subdomain_depth"], "Unusually deep subdomain structure")
    if signals["url_length"] >= 80:
        add(0.12, "url_length", signals["url_length"], "Very long URL (often used for obfuscation)")
    if signals["entropy"] >= 4.2:
        add(0.10, "entropy", round(signals["entropy"], 2), "High randomness/entropy in URL")
    if signals["digit_ratio"] >= 0.18:
        add(0.08, "digit_ratio", round(signals["digit_ratio"], 2), "Many digits in URL")
    if signals["is_shortener"]:
        add(0.22, "is_shortener", True, "URL shortener hides the destination")
    if signals["keyword_count"] >= 2:
        add(0.18, "keyword_count", signals["keyword_hits"], "Contains multiple high-risk keywords")

    # HTTPS is a weak positive signal (but not “safe”)
    if signals["has_https"]:
        add(-0.03, "has_https", True, "HTTPS present (weak positive signal)")

    # Clamp
    score = max(0.0, min(1.0, score))
    return score, reasons

def predict_url(url: str, enable_explain: bool = True) -> Dict[str, Any]:
    signals = extract_basic_signals(url)
    score, reasons = dummy_score(signals)

    label = "phishing" if score >= 0.5 else "legitimate"

    return {
        "label": label,
        "probability": float(score),
        "url_score": float(score),
        "reasons": reasons if enable_explain else [],
        "context": None,
        "meta": {
            "engine": "dummy-heuristics",
            "feature_version": "v0",
        },
    }
