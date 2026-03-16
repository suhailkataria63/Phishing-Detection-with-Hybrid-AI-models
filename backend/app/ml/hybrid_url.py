import re

from .url_model import URLModelV1, normalize_url_for_model
from .url_model_v2 import URLModelV2Ngrams
from ..utils.domain_utils import extract_registrable_domain
from ..utils.url_utils import extract_hostname, safe_parse_url


# ---- Guardrails (rules-first hybrid AI) ----

TRUSTED_HOST_SUFFIXES = (
    "python.org",
    "pypi.org",
    "github.com",
    "gitlab.com",
    "microsoft.com",
    "microsoftonline.com",
    "google.com",
    "accounts.google.com",
    "youtube.com",
    "wikipedia.org",
    "mozilla.org",
    "developer.mozilla.org",
    "linkedin.com",
    "amazon.com",
    "amazon.in",
    "yahoo.com",
    "paypal.com",
    "account.live.com", 
    "apple.com",
    "icloud.com"
)

BENIGN_PATH_HINTS = (
    "/docs",
    "/documentation",
    "/reference",
    "/library",
    "/api",
    "/en-us/",
    "/manual",
    "/guide",
    "/tutorial",
    "/learn",
)

BENIGN_EXT_RE = re.compile(r"\.(html?|pdf|md|txt)$", re.IGNORECASE)


def _host_matches_trusted(host: str) -> bool:
    if not host:
        return False
    h = host.lower()
    return any(h == s or h.endswith("." + s) for s in TRUSTED_HOST_SUFFIXES)

def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)

    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        cur = [i]
        for j, cb in enumerate(b, start=1):
            ins = cur[j - 1] + 1
            dele = prev[j] + 1
            sub = prev[j - 1] + (0 if ca == cb else 1)
            cur.append(min(ins, dele, sub))
        prev = cur
    return prev[-1]


def _typosquat_against_trusted(host: str):
    """
    Returns (is_typosquat, info_dict or None)
    """
    if not host:
        return False, None

    reg = extract_registrable_domain(host.lower())

    # Compare against trusted registrable domains (python.org, google.com, etc.)
    trusted_regs = set(extract_registrable_domain(s) for s in TRUSTED_HOST_SUFFIXES)

    best = None
    best_d = 10**9
    for t in trusted_regs:
        if reg == t:
            continue
        d = _levenshtein(reg, t)
        if d < best_d:
            best_d = d
            best = t

    # Distance 1 is the sweet spot for "google.com" vs "googie.com"
    if best is not None and best_d <= 1:
        return True, {"host": host, "registrable": reg, "closest_trusted": best, "distance": best_d}

    return False, None


def _looks_like_docs_path(path: str) -> bool:
    if not path:
        return False
    p = path.lower()
    if any(h in p for h in BENIGN_PATH_HINTS):
        return True
    if BENIGN_EXT_RE.search(p):
        return True
    if "/library/" in p or "/3/" in p:
        return True
    return False


class HybridURLModel:
    """
    Hybrid combiner with guardrails:
      - v1: explainable engineered features (+ rules)
      - v2: char n-gram pattern model
      - guardrails: trusted domain + docs-like paths to prevent “complex URL == phish” errors
    """

    def __init__(self, w1: float = 0.6, w2: float = 0.4):
        self.v1 = URLModelV1()
        self.v2 = URLModelV2Ngrams()
        self.w1 = w1
        self.w2 = w2

    def load(self):
        self.v1.load()
        self.v2.load()

    def predict(self, url: str, enable_explain: bool = True):
        normalized = normalize_url_for_model(url)
        p = safe_parse_url(normalized)
        host = extract_hostname(normalized)
        path = p.path or ""

        is_trusted = _host_matches_trusted(host)
        looks_docs = _looks_like_docs_path(path)

        # ---- v1 prediction ----
        # Always compute base reasons so hard/soft cue logic is stable even when
        # explain output is disabled.
        out_v1 = self.v1.predict(normalized, enable_explain=True)
        v1_score = float(out_v1.get("probability", 0.0))
        v1_label = out_v1.get("label", "legitimate")
        base_reasons = list(out_v1.get("reasons", []))
        reasons = list(base_reasons) if enable_explain else []

        # ---- v2 prediction ----
        v2_score = float(self.v2.predict_proba(normalized))

        # ---- Determine hard cues ONCE ----
        HARD_CUES = {
            "has_ip_host",
            "tld_suspicious",
            "num_at",
            "has_http_in_path",
            "rule_override",
            "fake_brand_domain",
        }

        has_hard_cue = any(r.get("feature") in HARD_CUES for r in base_reasons)

        # ---- Guardrail weights ----
        w1, w2 = self.w1, self.w2
        if is_trusted and looks_docs:
            w1, w2 = 0.85, 0.15
            if enable_explain:
                reasons.insert(0, {
                    "feature": "trusted_docs_guard",
                    "value": {"host": host, "docs_like": True},
                    "note": "Trusted documentation-style URL; reduced string-pattern model influence to avoid false positives.",
                })
        elif is_trusted:
            w1, w2 = 0.75, 0.25
            if enable_explain:
                reasons.insert(0, {
                    "feature": "trusted_domain_guard",
                    "value": host,
                    "note": "Trusted domain detected; reduced string-pattern model influence.",
                })

        # ---- Fusion score ----
        final_score = (w1 * v1_score) + (w2 * v2_score)

        # ---- v2 can force phishing only with hard cue OR untrusted ----
        force_by_v2 = (v2_score >= 0.985) and (has_hard_cue or not is_trusted)

        # ---- Initial decision ----
        if force_by_v2:
            label = "phishing"
        elif v1_label == "phishing" and has_hard_cue and not is_trusted:
            # v1 allowed to force phishing only with hard cues, and only when untrusted
            label = "phishing"
        else:
            label = "phishing" if final_score >= 0.5 else "legitimate"

        # ---- Trusted veto & docs override MUST run for trusted domains ----
        # If trusted and NO hard cues, cap score (prevents entropy/length false positives)
        if is_trusted and not has_hard_cue:
            final_score = min(final_score, 0.25)
            label="legitimate"
            if enable_explain:
                reasons.insert(0, {
                    "feature": "trusted_veto",
                    "value": {"trusted": True, "hard_cue": False},
                    "note": "Trusted URL context with no hard phishing cues → score capped to reduce false positives.",
                })

        # If trusted docs-like and NO hard cues, force legit
        if is_trusted and looks_docs and not has_hard_cue:
            label = "legitimate"
            final_score = min(final_score, 0.25)
            if enable_explain:
                reasons.insert(0, {
                    "feature": "trusted_docs_override",
                    "value": {"trusted": True, "docs_like": True},
                    "note": "Trusted docs URL: forcing legitimate unless hard phishing cues exist.",
                })

        # ---- Add v2 explanation (only when v2 should influence) ----
        # For trusted domains, v2 is downweighted already, so we only add this reason
        # if v2 is extremely high AND there are hard cues.
        if enable_explain:
            if (not is_trusted) or has_hard_cue:
                if v2_score >= 0.90:
                    reasons.insert(0, {
                        "feature": "url_char_patterns",
                        "value": round(v2_score, 4),
                        "note": "String-pattern model strongly matches phishing-like URL character sequences.",
                    })
                elif v2_score >= 0.75:
                    reasons.append({
                        "feature": "url_char_patterns",
                        "value": round(v2_score, 4),
                        "note": "String-pattern model sees moderately suspicious URL character patterns.",
                    })
        is_typosquat, typo_info = _typosquat_against_trusted(host)

        if is_typosquat:
            if enable_explain:
                reasons.insert(0, {
                    "feature": "fake_brand_domain",
                    "value": typo_info,
                    "note": "Domain is a near-match to a trusted brand (typosquat/lookalike).",
                })
        if is_typosquat and not is_trusted:
            label = "phishing"
            final_score = max(final_score, 0.95)

        if is_trusted and not has_hard_cue:
            # Trusted domains should not be flagged just because of common words like /login or /security
            final_score = min(final_score, 0.25)
            label = "legitimate"
            if enable_explain:
                reasons.insert(0, {
                    "feature": "trusted_soft_cues_override",
                    "value": {"trusted": True, "hard_cue": False},
                    "note": "Trusted domain with only soft cues (e.g., login/security) → forced legitimate to reduce false positives.",
                })


        return {
            "label": label,
            "probability": final_score,
            "url_score": final_score,
            "domain_score": None,
            "email_score": None,
            "reasons": reasons,
            "context": None,
            "meta": {
                "engine": "hybrid_url_v1_v2",
                "normalized_url": normalized,
                "v1_score": v1_score,
                "v2_score": v2_score,
                "weights_used": {"v1": w1, "v2": w2},
                "is_trusted": is_trusted,
                "looks_docs": looks_docs,
                "has_hard_cue": has_hard_cue,
                "v1_engine": out_v1.get("meta", {}).get("engine", "url_model_v1"),
                "v2_engine": getattr(self.v2, "version", "url_model_v2_ngrams"),
            },
        }
