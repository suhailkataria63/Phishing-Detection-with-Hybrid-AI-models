import re

from .url_model import URLModelV1, normalize_url_for_model
from .url_model_v2 import URLModelV2Ngrams
from ..utils.domain_utils import (
    TRUST_EXACT,
    TRUSTED_HOST_SUFFIXES,
    classify_trusted_domain,
    detect_typosquat_against_trusted,
    host_matches_trusted,
)
from ..utils.url_utils import extract_hostname, is_ip_host, safe_parse_url


# ---- Guardrails (rules-first hybrid AI) ----

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
REDIRECT_VALUE_RE = re.compile(
    r"(?:^|[?&])(?:redirect|redir|url|next|return|returnurl|continue|dest|destination|to)="
    r"(?:https?%3a%2f%2f|https?://)",
    re.IGNORECASE,
)

SENSITIVE_PATH_HINTS = (
    "/login",
    "/signin",
    "/auth",
    "/verify",
    "/account",
    "/security",
    "/reset",
    "/password",
    "/otp",
    "/admin",
)

LURE_KEYWORDS = {
    "login",
    "verify",
    "secure",
    "update",
    "account",
    "password",
    "signin",
    "confirm",
    "bank",
    "wallet",
    "otp",
    "reset",
    "gift",
    "card",
    "free",
    "now",
    "urgent",
    "support",
}

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


def _is_sensitive_path(path: str) -> bool:
    if not path:
        return False
    p = path.lower()
    return any(h in p for h in SENSITIVE_PATH_HINTS)


def _has_embedded_redirect_target(query: str) -> bool:
    if not query:
        return False
    q = query.lower()
    return bool(REDIRECT_VALUE_RE.search("?" + q))


def _lure_keyword_count(host: str, path: str, query: str) -> int:
    hay = f"{host} {path} {query}".lower()
    return sum(1 for k in LURE_KEYWORDS if k in hay)


def _has_lure_lexical_pattern(host: str, path: str, query: str) -> bool:
    """
    Lightweight lexical lure detector for untrusted domains.
    Keeps threshold intentionally conservative to reduce false positives.
    """
    keyword_count = _lure_keyword_count(host, path, query)
    host_hyphens = host.count("-")
    return keyword_count >= 3 or (keyword_count >= 2 and host_hyphens >= 2)


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
        query = p.query or ""

        trust_kind = classify_trusted_domain(host, TRUSTED_HOST_SUFFIXES)
        is_trusted = host_matches_trusted(host, TRUSTED_HOST_SUFFIXES)
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
                    "value": {"host": host, "docs_like": True, "trust_kind": trust_kind},
                    "note": "Trusted documentation-style URL; reduced string-pattern model influence to avoid false positives.",
                })
        elif is_trusted:
            w1, w2 = 0.75, 0.25
            trust_note = (
                "Exact trusted brand domain detected; reduced string-pattern model influence."
                if trust_kind == TRUST_EXACT
                else "Trusted domain ecosystem detected; reduced string-pattern model influence."
            )
            if enable_explain:
                reasons.insert(0, {
                    "feature": "trusted_domain_guard",
                    "value": {"host": host, "trust_kind": trust_kind},
                    "note": trust_note,
                })
                if trust_kind == TRUST_EXACT:
                    reasons.insert(0, {
                        "feature": "trusted_exact_domain_exemption",
                        "value": {"host": host, "exemption": "lookalike_checks"},
                        "note": "Exact trusted registrable domain; exempt from fake-brand lookalike flagging.",
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
        is_typosquat, typo_info = detect_typosquat_against_trusted(host, TRUSTED_HOST_SUFFIXES)

        if is_typosquat:
            match_type = (typo_info or {}).get("match_type", "unknown")
            if match_type == "confusable_skeleton":
                typo_note = "Domain skeleton matches a trusted brand via confusable/homoglyph normalization."
            else:
                typo_note = "Domain is a near-match to a trusted brand (typosquat/lookalike)."
            if enable_explain:
                reasons.insert(0, {
                    "feature": "fake_brand_domain",
                    "value": typo_info,
                    "note": typo_note,
                })
        if is_typosquat and not is_trusted:
            label = "phishing"
            final_score = max(final_score, 0.95)

        # ---- TG-4.5: targeted suspicious-pattern hardening (untrusted only) ----
        if not is_trusted:
            ip_sensitive = False
            if is_ip_host(host):
                ip_sensitive = _is_sensitive_path(path)

            if ip_sensitive:
                label = "phishing"
                final_score = max(final_score, 0.88)
                if enable_explain:
                    reasons.insert(0, {
                        "feature": "ip_sensitive_path",
                        "value": {"host": host, "path": path},
                        "note": "IP-host URL with a sensitive auth/admin path is high-risk for phishing.",
                    })

            if _has_embedded_redirect_target(query):
                label = "phishing"
                final_score = max(final_score, 0.78)
                if enable_explain:
                    reasons.insert(0, {
                        "feature": "embedded_redirect_target",
                        "value": {"query": query[:180]},
                        "note": "Query contains embedded http/https redirect target often used in phishing redirection flows.",
                    })

            if _has_lure_lexical_pattern(host, path, query):
                label = "phishing"
                final_score = max(final_score, 0.72)
                if enable_explain:
                    reasons.insert(0, {
                        "feature": "untrusted_lure_pattern",
                        "value": {
                            "host": host,
                            "lure_keyword_count": _lure_keyword_count(host, path, query),
                            "host_hyphens": host.count("-"),
                        },
                        "note": "Untrusted domain shows lure-style lexical phishing patterns.",
                    })

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
                "trust_kind": trust_kind,
                "looks_docs": looks_docs,
                "has_hard_cue": has_hard_cue,
                "v1_engine": out_v1.get("meta", {}).get("engine", "url_model_v1"),
                "v2_engine": getattr(self.v2, "version", "url_model_v2_ngrams"),
            },
        }
