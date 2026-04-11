"""Heuristic feature extraction and optimized rule-assisted joint scoring.

TG-6.2 focus:
- stronger hard-negative suppression
- cleaner-phish URL escalation
- trusted-domain + sender/domain consistency handling
- explicit decision flags for API metadata
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from .domain_utils import (
    TRUST_UNTRUSTED,
    classify_trusted_domain,
    detect_typosquat_against_trusted,
    extract_registrable_domain,
    is_top_ranked_domain,
)
from .email_utils import extract_sender_domain
from .url_utils import extract_hostname, is_ip_host, safe_parse_url


STRATEGY_VERSION = "optimized_v2"

TRUSTED_BENIGN_REGISTRABLES = {
    "google.com",
    "accounts.google.com",
    "meet.google.com",
    "maps.google.com",
    "github.com",
    "amazon.in",
    "hdfcbank.com",
    "notion.so",
    "dropbox.com",
}
TRUSTED_SUBDOMAIN_HOSTS = {
    "accounts.google.com",
    "meet.google.com",
    "maps.google.com",
    "docs.google.com",
    "mail.google.com",
    "support.github.com",
    "www.hdfcbank.com",
    "www.amazon.in",
    "www.dropbox.com",
    "www.notion.so",
}
SENDER_BRAND_TO_REGISTRABLE = {
    "google": "google.com",
    "github": "github.com",
    "amazon": "amazon.in",
    "hdfc": "hdfcbank.com",
    "notion": "notion.so",
    "dropbox": "dropbox.com",
    "paypal": "paypal.com",
    "microsoft": "microsoft.com",
    "outlook": "outlook.com",
    "docusign": "docusign.com",
    "bank": "hdfcbank.com",
}
SHORTENER_HOSTS = {
    "bit.ly",
    "tinyurl.com",
    "t.co",
    "goo.gl",
    "ow.ly",
    "is.gd",
    "cutt.ly",
    "buff.ly",
    "rb.gy",
}
SUSPICIOUS_TLDS = {
    "zip",
    "xyz",
    "top",
    "click",
    "work",
    "shop",
    "live",
    "gq",
    "tk",
    "ml",
    "cf",
}
URL_KEYWORDS = (
    "login",
    "verify",
    "update",
    "auth",
    "reset",
    "secure",
    "account",
    "password",
    "otp",
)
EMAIL_URGENCY = (
    "urgent",
    "immediately",
    "within 24 hours",
    "today",
    "expire",
    "final warning",
    "action required",
)
EMAIL_CREDENTIAL = (
    "verify your account",
    "verify identity",
    "sign in",
    "login",
    "password",
    "otp",
    "authentication",
)
EMAIL_FINANCE = (
    "payment",
    "invoice",
    "bank",
    "salary",
    "payroll",
    "wire transfer",
    "gift card",
)
EMAIL_RESTRICTION = (
    "restricted access",
    "suspended",
    "termination",
    "locked",
    "disable",
)
EMAIL_BENIGN = (
    "no action required",
    "for awareness only",
    "monthly statement",
    "order has been shipped",
    "track your shipment",
    "available in portal",
)
EMAIL_INTERNAL_TONE = (
    "thanks",
    "regards",
    "please review",
    "for your reference",
)
EMAIL_HIGH_INTENT_PHISH = (
    "permanent suspension",
    "permanently disabled",
    "within 24 hours",
    "final warning",
    "validate now",
    "avoid suspension",
    "account termination",
)
BRAND_TOKENS = tuple(SENDER_BRAND_TO_REGISTRABLE.keys())
PUNYCODE_RE = re.compile(r"xn--", re.IGNORECASE)


def _count_matches(text: str, needles: Sequence[str]) -> int:
    t = (text or "").lower()
    return sum(1 for n in needles if n in t)


def _sender_brand_hint(sender: str) -> str:
    s = (sender or "").lower()
    for k, v in SENDER_BRAND_TO_REGISTRABLE.items():
        if k in s:
            return v
    return ""


def _tokenize_hostname(host: str) -> List[str]:
    h = (host or "").lower().strip()
    if not h:
        return []
    bits = re.split(r"[\.\-_]+", h)
    return [b for b in bits if b]


def _brand_token_hits(host_tokens: Sequence[str]) -> int:
    token_set = set(host_tokens)
    return sum(1 for b in BRAND_TOKENS if b in token_set)


def _path_risk_score(path_q: str) -> int:
    pq = (path_q or "").lower()
    risk_terms = (
        "login",
        "signin",
        "verify",
        "verification",
        "auth",
        "reset",
        "password",
        "account",
        "session",
        "security",
        "confirm",
    )
    return sum(1 for t in risk_terms if t in pq)


def _is_trusted_subdomain(host: str) -> bool:
    h = (host or "").lower().strip()
    if not h:
        return False
    if h in TRUSTED_SUBDOMAIN_HOSTS:
        return True
    # allow nested trusted subdomain ecosystems conservatively
    return any(h.endswith("." + s) for s in TRUSTED_SUBDOMAIN_HOSTS)


def _url_heuristics(url: str) -> Dict[str, Any]:
    p = safe_parse_url(url)
    host = extract_hostname(url)
    reg = extract_registrable_domain(host or "")
    path_q = f"{p.path or ''} {p.query or ''}".lower()
    host_l = (host or "").lower()

    host_tokens = _tokenize_hostname(host_l)
    subdomain_depth = max(0, len([x for x in host_l.split(".") if x]) - 2)
    tld = reg.split(".")[-1] if "." in reg else ""
    has_shortener = reg in SHORTENER_HOSTS
    is_suspicious_tld = tld in SUSPICIOUS_TLDS
    keyword_hits = _count_matches(f"{host_l} {path_q}", URL_KEYWORDS)
    path_risk_score = _path_risk_score(path_q)
    typosquat_hit, _ = detect_typosquat_against_trusted(host_l)
    non_https = str((p.scheme or "")).lower() != "https"
    suspicious_host_shape = (host_l.count("-") >= 2) or bool(re.search(r"\d{3,}", host_l))
    punycode_like = bool(PUNYCODE_RE.search(host_l))
    trusted = classify_trusted_domain(host_l) != TRUST_UNTRUSTED
    trusted_subdomain = _is_trusted_subdomain(host_l)
    top_ranked = is_top_ranked_domain(host_l, max_rank=20000)
    trusted_exact = reg in TRUSTED_BENIGN_REGISTRABLES
    brand_hits = _brand_token_hits(host_tokens)
    suspicious_compound_hostname = (
        (len(host_tokens) >= 4 and host_l.count("-") >= 1)
        or (brand_hits >= 1 and host_l.count("-") >= 1 and not (trusted or trusted_subdomain))
        or (brand_hits >= 2 and not trusted)
    )
    reputable = trusted or trusted_subdomain or top_ranked or trusted_exact

    return {
        "host": host_l,
        "registrable": reg,
        "host_token_count": len(host_tokens),
        "brand_token_hits": brand_hits,
        "is_ip": is_ip_host(host_l),
        "has_shortener": has_shortener,
        "suspicious_tld": is_suspicious_tld,
        "subdomain_depth": subdomain_depth,
        "keyword_hits": keyword_hits,
        "path_risk_score": path_risk_score,
        "typosquat_hit": bool(typosquat_hit),
        "non_https": non_https,
        "suspicious_host_shape": suspicious_host_shape,
        "suspicious_compound_hostname": suspicious_compound_hostname,
        "punycode_like": punycode_like,
        "trusted": trusted,
        "trusted_subdomain": trusted_subdomain,
        "trusted_exact": trusted_exact,
        "top_ranked": top_ranked,
        "reputable": reputable,
    }


def extract_joint_heuristic_features(
    *,
    subject: str,
    body: str,
    sender: str,
    urls: Iterable[str],
    email_score: float,
    url_scores: Sequence[float],
    url_reason_features: Iterable[str] | None = None,
) -> Dict[str, float]:
    """Extract numeric heuristic features for rule/meta optimization."""
    url_list = [u for u in urls if (u or "").strip()]
    url_h = [_url_heuristics(u) for u in url_list]
    url_count = len(url_h)

    ip_count = sum(int(x["is_ip"]) for x in url_h)
    shortener_count = sum(int(x["has_shortener"]) for x in url_h)
    suspicious_tld_count = sum(int(x["suspicious_tld"]) for x in url_h)
    deep_subdomain_count = sum(int(x["subdomain_depth"] >= 3) for x in url_h)
    url_keyword_total = sum(int(x["keyword_hits"]) for x in url_h)
    path_risk_total = sum(int(x["path_risk_score"]) for x in url_h)
    non_https_count = sum(int(x["non_https"]) for x in url_h)
    punycode_count = sum(int(x["punycode_like"]) for x in url_h)
    suspicious_shape_count = sum(int(x["suspicious_host_shape"]) for x in url_h)
    suspicious_compound_count = sum(int(x["suspicious_compound_hostname"]) for x in url_h)
    brand_token_total = sum(int(x["brand_token_hits"]) for x in url_h)
    typosquat_count = sum(int(x["typosquat_hit"]) for x in url_h)
    trusted_count = sum(int(x["trusted"]) for x in url_h)
    trusted_subdomain_count = sum(int(x["trusted_subdomain"]) for x in url_h)
    trusted_exact_count = sum(int(x["trusted_exact"]) for x in url_h)
    reputable_count = sum(int(x["reputable"]) for x in url_h)
    untrusted_count = max(0, url_count - trusted_count)
    mixed_reputation = int(trusted_count > 0 and untrusted_count > 0)

    sender_domain = extract_sender_domain(sender)
    sender_reg = extract_registrable_domain(sender_domain) if sender_domain else ""
    sender_brand_reg = _sender_brand_hint(sender)
    sender_hint_reg = sender_reg or sender_brand_reg
    url_regs = {x["registrable"] for x in url_h if x["registrable"]}

    sender_url_match = int(bool(sender_hint_reg and sender_hint_reg in url_regs))
    sender_url_mismatch = int(bool(sender_hint_reg and url_regs and sender_hint_reg not in url_regs))
    sender_url_mismatch_score = 0.0
    if sender_url_mismatch:
        mismatch_to_untrusted = any(
            (x["registrable"] != sender_hint_reg) and (not x["reputable"])
            for x in url_h
        )
        if mismatch_to_untrusted:
            sender_url_mismatch_score = 0.85
        else:
            sender_url_mismatch_score = 0.45

    text = f"{subject or ''} {body or ''}".lower()
    urgency_hits = _count_matches(text, EMAIL_URGENCY)
    credential_hits = _count_matches(text, EMAIL_CREDENTIAL)
    finance_hits = _count_matches(text, EMAIL_FINANCE)
    restriction_hits = _count_matches(text, EMAIL_RESTRICTION)
    benign_hits = _count_matches(text, EMAIL_BENIGN)
    internal_hits = _count_matches(text, EMAIL_INTERNAL_TONE)
    high_intent_hits = _count_matches(text, EMAIL_HIGH_INTENT_PHISH)
    suspicious_email_lex = urgency_hits + credential_hits + finance_hits + restriction_hits

    max_url_score = max([float(s) for s in url_scores], default=0.0)
    trusted_domain_match = int(
        sender_url_match
        and any(x["registrable"] == sender_hint_reg and x["reputable"] for x in url_h)
    )
    brand_domain_mismatch = int(sender_url_mismatch and sender_hint_reg != "")
    baseline_url_hard = int(
        ip_count > 0
        or typosquat_count > 0
        or suspicious_tld_count > 0
        or punycode_count > 0
        or max_url_score >= 0.8
    )
    if url_reason_features:
        hard_feats = {
            "has_ip_host",
            "fake_brand_domain",
            "embedded_redirect_target",
            "ip_sensitive_path",
            "untrusted_lure_pattern",
        }
        if any(f in hard_feats for f in url_reason_features):
            baseline_url_hard = 1

    has_urls = int(url_count > 0)
    malicious_email_no_url = int((not has_urls) and (email_score >= 0.55) and suspicious_email_lex >= 2)
    benign_email_bad_url_conflict = int(benign_hits >= 2 and max_url_score >= 0.7)
    no_url_benign_support = int(
        (not has_urls)
        and urgency_hits <= 2
        and credential_hits == 0
        and finance_hits <= 1
        and restriction_hits == 0
        and (benign_hits >= 1 or internal_hits >= 1)
    )
    legit_security_alert_support = int(
        has_urls
        and trusted_domain_match
        and brand_domain_mismatch == 0
        and suspicious_email_lex <= 2
        and urgency_hits <= 1
        and high_intent_hits == 0
        and (credential_hits + restriction_hits >= 1)
        and max_url_score <= 0.45
        and baseline_url_hard == 0
    )
    suspicious_url_escalation = int(
        has_urls
        and (
            suspicious_compound_count > 0
            or (brand_token_total > 0 and trusted_count == 0 and trusted_subdomain_count == 0)
        )
        and (path_risk_total > 0 or url_keyword_total > 0)
        and (untrusted_count > 0 or max_url_score >= 0.55)
    )
    multi_url_conflict = int(url_count > 1 and reputable_count > 0 and (baseline_url_hard > 0 or max_url_score >= 0.68))
    strongest_url_malicious = int(
        baseline_url_hard > 0
        or max_url_score >= 0.82
        or (suspicious_url_escalation and max_url_score >= 0.6)
    )

    return {
        "has_urls": float(has_urls),
        "url_count": float(url_count),
        "max_url_score": float(max_url_score),
        "ip_url_count": float(ip_count),
        "shortener_count": float(shortener_count),
        "suspicious_tld_count": float(suspicious_tld_count),
        "deep_subdomain_count": float(deep_subdomain_count),
        "url_keyword_total": float(url_keyword_total),
        "path_risk_total": float(path_risk_total),
        "non_https_count": float(non_https_count),
        "punycode_count": float(punycode_count),
        "suspicious_host_shape_count": float(suspicious_shape_count),
        "suspicious_compound_count": float(suspicious_compound_count),
        "brand_token_total": float(brand_token_total),
        "typosquat_count": float(typosquat_count),
        "trusted_url_count": float(trusted_count),
        "trusted_subdomain_count": float(trusted_subdomain_count),
        "trusted_exact_count": float(trusted_exact_count),
        "reputable_url_count": float(reputable_count),
        "untrusted_url_count": float(untrusted_count),
        "mixed_url_reputation": float(mixed_reputation),
        "sender_url_match": float(sender_url_match),
        "sender_url_mismatch": float(sender_url_mismatch),
        "sender_url_mismatch_score": float(sender_url_mismatch_score),
        "trusted_domain_match": float(trusted_domain_match),
        "brand_domain_mismatch": float(brand_domain_mismatch),
        "urgency_hits": float(urgency_hits),
        "credential_hits": float(credential_hits),
        "finance_hits": float(finance_hits),
        "restriction_hits": float(restriction_hits),
        "benign_hits": float(benign_hits),
        "internal_hits": float(internal_hits),
        "high_intent_hits": float(high_intent_hits),
        "suspicious_email_lex": float(suspicious_email_lex),
        "baseline_url_hard": float(baseline_url_hard),
        "malicious_email_no_url": float(malicious_email_no_url),
        "benign_email_bad_url_conflict": float(benign_email_bad_url_conflict),
        "no_url_benign_support": float(no_url_benign_support),
        "legit_security_alert_support": float(legit_security_alert_support),
        "suspicious_url_escalation": float(suspicious_url_escalation),
        "multi_url_conflict": float(multi_url_conflict),
        "strongest_url_malicious": float(strongest_url_malicious),
    }


def apply_rule_assisted_joint_score(
    *,
    email_score: float,
    url_scores: Sequence[float],
    heuristic: Dict[str, float],
    threshold: float = 0.5,
) -> Tuple[float, str, List[str], Dict[str, Any]]:
    """Rule-assisted optimized joint score.

    Returns tuple: (final_score, final_label, rule_notes)
    """
    e = float(max(0.0, min(1.0, email_score)))
    u = max([float(max(0.0, min(1.0, s))) for s in url_scores], default=0.0)
    h = heuristic

    reasons: List[str] = []
    flags: Dict[str, Any] = {
        "trusted_domain_match": bool(h.get("trusted_domain_match", 0.0) > 0),
        "brand_domain_mismatch": bool(h.get("brand_domain_mismatch", 0.0) > 0),
        "no_url_benign_support": False,
        "suspicious_url_escalation": False,
        "strategy_version": STRATEGY_VERSION,
    }
    score = 0.56 * e + 0.44 * u
    reasons.append("Base blend: 0.56*email + 0.44*max_url")

    suspicious_url_signal = (
        h.get("ip_url_count", 0.0)
        + h.get("shortener_count", 0.0)
        + h.get("suspicious_tld_count", 0.0)
        + h.get("deep_subdomain_count", 0.0)
        + h.get("typosquat_count", 0.0)
        + h.get("punycode_count", 0.0)
        + h.get("baseline_url_hard", 0.0)
    )

    if h.get("has_urls", 0.0) > 0:
        if suspicious_url_signal >= 2:
            score += 0.10
            reasons.append("Boost: strong suspicious URL indicator stack.")
        elif suspicious_url_signal >= 1:
            score += 0.05
            reasons.append("Boost: moderate suspicious URL indicators.")

        mismatch_score = h.get("sender_url_mismatch_score", 0.0)
        if mismatch_score >= 0.75:
            score += 0.12
            reasons.append("Boost: reputable sender/domain mismatch to untrusted URL.")
            flags["brand_domain_mismatch"] = True
        elif mismatch_score >= 0.35:
            score += 0.06
            reasons.append("Boost: sender/URL domain mismatch.")
            flags["brand_domain_mismatch"] = True

        if h.get("trusted_domain_match", 0.0) > 0 and suspicious_url_signal == 0:
            score -= 0.12
            reasons.append("Dampen: trusted domain match with sender/context.")
            flags["trusted_domain_match"] = True

        if (
            h.get("legit_security_alert_support", 0.0) > 0
            and h.get("trusted_domain_match", 0.0) > 0
            and h.get("brand_domain_mismatch", 0.0) == 0
        ):
            score = min(score, 0.32)
            reasons.append("Cap: legitimate security alert pattern on trusted matching domain.")
            flags["trusted_domain_match"] = True

        if (
            h.get("reputable_url_count", 0.0) >= h.get("url_count", 0.0) >= 1
            and h.get("brand_domain_mismatch", 0.0) == 0
            and suspicious_url_signal == 0
            and h.get("benign_hits", 0.0) + h.get("internal_hits", 0.0) >= 1
            and u <= 0.60
        ):
            score = min(score, 0.42)
            reasons.append("Cap: all URLs reputable with benign status-update language.")
            flags["trusted_domain_match"] = True

        if h.get("benign_hits", 0.0) >= 2 and h.get("reputable_url_count", 0.0) >= 1 and suspicious_url_signal == 0 and u <= 0.35:
            score = min(score, 0.38)
            reasons.append("Cap: benign transactional phrasing + reputable low-risk URL.")

        if h.get("mixed_url_reputation", 0.0) > 0:
            score += 0.04
            reasons.append("Boost: mixed trusted/untrusted URLs in same message.")

        if h.get("suspicious_url_escalation", 0.0) > 0:
            score = max(score, 0.72)
            score += 0.06
            reasons.append("Escalate: clean-looking but structurally suspicious phishing URL pattern.")
            flags["suspicious_url_escalation"] = True

        if (
            h.get("trusted_domain_match", 0.0) > 0
            and h.get("brand_domain_mismatch", 0.0) == 0
            and h.get("suspicious_email_lex", 0.0) >= 2
            and h.get("urgency_hits", 0.0) >= 1
            and (
                h.get("high_intent_hits", 0.0) >= 1
                or (h.get("credential_hits", 0.0) + h.get("restriction_hits", 0.0) >= 2)
            )
        ):
            score = max(score, 0.74)
            reasons.append("Escalate: high-intent malicious email text despite official-looking URL.")

        if h.get("multi_url_conflict", 0.0) > 0 and h.get("strongest_url_malicious", 0.0) > 0:
            score = max(score, 0.80)
            reasons.append("Escalate: malicious URL dominates benign URLs in multi-link message.")
            flags["suspicious_url_escalation"] = True
    else:
        if h.get("malicious_email_no_url", 0.0) > 0:
            score = max(score, 0.66)
            reasons.append("Escalate: malicious email cues present even without URLs.")
        if h.get("no_url_benign_support", 0.0) > 0:
            score = min(score, 0.25)
            reasons.append("Strong dampen: no-URL benign/internal status-update language.")
            flags["no_url_benign_support"] = True
        elif h.get("benign_hits", 0.0) >= 2 and h.get("suspicious_email_lex", 0.0) <= 1:
            score = min(score, 0.40)
            reasons.append("Dampen: no-URL benign informational phrasing.")
            flags["no_url_benign_support"] = True

    if h.get("benign_email_bad_url_conflict", 0.0) > 0:
        score = max(score, 0.70)
        reasons.append("Escalate: benign-looking body but high-risk URL conflict.")
        flags["suspicious_url_escalation"] = True

    if h.get("ip_url_count", 0.0) > 0:
        score = max(score, 0.84)
        reasons.append("Escalate: IP-host URL present.")
        flags["suspicious_url_escalation"] = True

    if h.get("typosquat_count", 0.0) > 0:
        score = max(score, 0.86)
        reasons.append("Escalate: trusted-brand typosquat/lookalike detected.")
        flags["suspicious_url_escalation"] = True

    score = float(max(0.0, min(1.0, score)))
    label = "phishing" if score >= float(max(0.0, min(1.0, threshold))) else "legitimate"
    return score, label, reasons, flags


def flatten_feature_vector(features: Dict[str, float], keys: Sequence[str]) -> List[float]:
    """Convert feature dict to stable list order."""
    return [float(features.get(k, 0.0)) for k in keys]
