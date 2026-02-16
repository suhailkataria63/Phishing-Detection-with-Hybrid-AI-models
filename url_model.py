import json
import math
import re
from pathlib import Path
from urllib.parse import urlparse, urlunparse, unquote

import joblib
import pandas as pd


# Paths
BACKEND_ROOT = Path(__file__).resolve().parents[2]       # .../phish-detector/backend
PROJECT_ROOT = BACKEND_ROOT.parent                       # .../phish-detector

MODEL_PATH = PROJECT_ROOT / "models" / "url_model_v1_calibrated.joblib"
SCHEMA_PATH = PROJECT_ROOT / "models" / "url_feature_schema_v1.json"

IPV4_RE = re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}$")
SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+\-.]*://")


def normalize_url_for_model(raw: str) -> str:
    """
    Normalize user input into a stable URL form so the feature extractor is consistent.
    - If no scheme, assume https://
    - Lowercase hostname
    - Strip leading www.
    - Upgrade http->https (stability; most legit sites redirect anyway)
    - Ensure path at least "/"
    """
    s = (raw or "").strip()
    s = unquote(s)

    if not SCHEME_RE.match(s):
        s = "https://" + s

    p = urlparse(s)

    scheme = (p.scheme or "https").lower()
    netloc = (p.netloc or "").lower()

    # If still no netloc (rare odd inputs), treat path as host
    if not netloc and p.path:
        p2 = urlparse("https://" + p.path)
        scheme = (p2.scheme or "https").lower()
        netloc = (p2.netloc or "").lower()
        p = p2

    # strip default ports
    if netloc.endswith(":80"):
        netloc = netloc[:-3]
    if netloc.endswith(":443"):
        netloc = netloc[:-4]

    # strip leading www.
    if netloc.startswith("www."):
        netloc = netloc[4:]

    # upgrade http -> https for stability
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
    # validate octets <= 255
    parts = host.split(".")
    try:
        return 1 if all(0 <= int(x) <= 255 for x in parts) else 0
    except ValueError:
        return 0


class URLModelV1:
    def __init__(self):
        self.model = None
        self.schema = None
        self.feature_names = []
        self.keywords = []
        self.suspicious_tlds = set()

    def load(self):
        if not MODEL_PATH.exists():
            raise FileNotFoundError(f"Model not found: {MODEL_PATH}")
        if not SCHEMA_PATH.exists():
            raise FileNotFoundError(f"Schema not found: {SCHEMA_PATH}")

        obj = joblib.load(MODEL_PATH)

        # If joblib contains a bundle dict, unwrap the estimator/pipeline
        if isinstance(obj, dict):
            for k in ("model", "pipeline", "clf", "estimator"):
                if k in obj:
                    obj = obj[k]
                    break

        self.model = obj

        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            self.schema = json.load(f)

        self.feature_names = list(self.schema.get("feature_names", []))
        self.keywords = list(self.schema.get("risk_keywords", []))
        self.suspicious_tlds = set(self.schema.get("suspicious_tlds", []))

        # sanity: feature count match (only if estimator exposes it)
        n_model = getattr(self.model, "n_features_in_", None)
        if n_model is not None and len(self.feature_names) != n_model:
            raise ValueError(
                f"Feature mismatch: model expects {n_model}, schema has {len(self.feature_names)}"
            )

        # sanity: must support predict_proba
        if not hasattr(self.model, "predict_proba"):
            raise TypeError(f"Loaded model has no predict_proba(): {type(self.model)}")

    def extract_features(self, normalized_url: str) -> dict:
        """
        Extract engineered features from an already-normalized URL.
        Returns a dict containing:
          - model features listed in schema.feature_names
          - extra debug fields prefixed with '_' (for explanations only)
        """
        url = normalized_url
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

        # TLD
        tld = ""
        if host and "." in host:
            tld = host.rsplit(".", 1)[-1]
        tld_suspicious = 1 if (tld in self.suspicious_tlds) else 0

        entropy_host = shannon_entropy(host)
        entropy_path = shannon_entropy(path)
        entropy_url = shannon_entropy(url)

        # Keywords across full normalized URL
        url_lc = url.lower()
        keyword_hits = [k for k in self.keywords if k in url_lc]
        keyword_count = len(keyword_hits)

        feats = {
            # --- model features ---
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

            # --- explain/debug extras (not in model input) ---
            "_keyword_hits": keyword_hits,
            "_tld": tld,
            "_normalized_url": url,
        }
        return feats

    def build_reasons(self, feats: dict) -> list:
        """
        Deterministic reasons based on feature triggers.
        Explainable, stable, and maps directly to engineered features.
        """
        reasons = []

        # Strong/high-signal triggers
        if feats.get("has_ip_host", 0) == 1:
            reasons.append({
                "feature": "has_ip_host",
                "value": 1,
                "note": "Host is an IP address (often used to evade domain reputation).",
            })

        if feats.get("tld_suspicious", 0) == 1:
            reasons.append({
                "feature": "tld_suspicious",
                "value": feats.get("_tld", ""),
                "note": "Suspicious / low-reputation TLD detected.",
            })

        hits = feats.get("_keyword_hits", [])
        if hits:
            reasons.append({
                "feature": "keyword_count",
                "value": hits[:8],
                "note": "Contains high-risk keywords often seen in phishing lures.",
            })

        # Structure/obfuscation triggers
        if feats.get("num_subdomains", 0) >= 3:
            reasons.append({
                "feature": "num_subdomains",
                "value": int(feats.get("num_subdomains", 0)),
                "note": "Unusually deep subdomain chain (common in spoofing).",
            })

        if feats.get("num_at", 0) > 0:
            reasons.append({
                "feature": "num_at",
                "value": int(feats.get("num_at", 0)),
                "note": "Contains '@' in URL (can confuse users about the real host).",
            })

        if feats.get("has_http_in_path", 0) == 1:
            reasons.append({
                "feature": "has_http_in_path",
                "value": 1,
                "note": "Contains 'http' inside path/query (often used in redirect tricks).",
            })

        if feats.get("num_pct", 0) >= 3:
            reasons.append({
                "feature": "num_pct",
                "value": int(feats.get("num_pct", 0)),
                "note": "Heavy URL encoding detected (can indicate obfuscation).",
            })

        if feats.get("qparams", 0) >= 4:
            reasons.append({
                "feature": "qparams",
                "value": int(feats.get("qparams", 0)),
                "note": "Many query parameters (tracking/redirect patterns are common in phishing).",
            })

        # Entropy and length heuristics
        if feats.get("entropy_url", 0.0) >= 4.2:
            reasons.append({
                "feature": "entropy_url",
                "value": round(float(feats.get("entropy_url", 0.0)), 3),
                "note": "High randomness/entropy in URL (often seen in generated phishing links).",
            })

        if feats.get("url_len", 0) >= 90:
            reasons.append({
                "feature": "url_len",
                "value": int(feats.get("url_len", 0)),
                "note": "Very long URL (often used to hide the real destination).",
            })

        if feats.get("num_digits", 0) >= 12:
            reasons.append({
                "feature": "num_digits",
                "value": int(feats.get("num_digits", 0)),
                "note": "Many digits in URL (common in campaign IDs / tracking).",
            })

        return reasons[:8]

    def predict(self, url: str, enable_explain: bool = True):
        if self.model is None:
            raise RuntimeError("Model not loaded. Did startup_event call url_model.load()?")

        normalized = normalize_url_for_model(url)
        feats = self.extract_features(normalized)

        # Build row in schema order (ONLY model features)
        row = {name: feats.get(name, 0) for name in self.feature_names}
        X = pd.DataFrame([row], columns=self.feature_names)

        proba_phish = float(self.model.predict_proba(X)[0][1])

        # Rule override (hybrid logic)
        force_phishing = False
        if feats.get("tld_suspicious", 0) == 1 and feats.get("keyword_count", 0) >= 2:
            force_phishing = True

        label = "phishing" if (force_phishing or proba_phish >= 0.5) else "legitimate"

        reasons = self.build_reasons(feats) if enable_explain else []
        if enable_explain and force_phishing:
            reasons.insert(0, {
                "feature": "rule_override",
                "value": "tld_suspicious + >=2 risk keywords",
                "note": "Forced phishing due to high-confidence rule match.",
            })

        return {
            "label": label,
            "probability": proba_phish,
            "url_score": proba_phish,
            "domain_score": None,
            "email_score": None,
            "reasons": reasons,
            "context": None,
            "meta": {
                "engine": "url_model_v1",
                "normalized_url": feats.get("_normalized_url"),
            },
        }
