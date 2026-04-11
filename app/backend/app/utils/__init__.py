"""Shared backend utilities for URL and domain handling."""

from .domain_utils import (
    CONFUSABLE_CHAR_MAP,
    TRUST_ECOSYSTEM,
    TRUST_EXACT,
    TRUST_UNTRUSTED,
    TRUSTED_HOST_SUFFIXES,
    classify_trusted_domain,
    confusable_domain_skeleton,
    detect_typosquat_against_trusted,
    extract_registrable_domain,
    extract_subdomain,
    find_confusable_match_against_trusted,
    get_top_rank,
    host_matches_trusted,
    is_top_ranked_domain,
    normalize_unicode_domain,
    safe_decode_idn_host,
)
from .email_utils import (
    build_email_text,
    dedupe_preserve_order,
    extract_sender_domain,
    extract_urls_from_text,
)
from .joint_scoring import combine_email_url_scores, risk_level_from_score
from .joint_optimization import (
    apply_rule_assisted_joint_score,
    extract_joint_heuristic_features,
    flatten_feature_vector,
)
from .url_utils import extract_hostname, is_ip_host, normalize_url, safe_parse_url

__all__ = [
    "normalize_url",
    "safe_parse_url",
    "extract_hostname",
    "is_ip_host",
    "extract_registrable_domain",
    "extract_subdomain",
    "TRUST_EXACT",
    "TRUST_ECOSYSTEM",
    "TRUST_UNTRUSTED",
    "TRUSTED_HOST_SUFFIXES",
    "classify_trusted_domain",
    "host_matches_trusted",
    "detect_typosquat_against_trusted",
    "normalize_unicode_domain",
    "safe_decode_idn_host",
    "confusable_domain_skeleton",
    "find_confusable_match_against_trusted",
    "CONFUSABLE_CHAR_MAP",
    "get_top_rank",
    "is_top_ranked_domain",
    "build_email_text",
    "extract_urls_from_text",
    "extract_sender_domain",
    "dedupe_preserve_order",
    "combine_email_url_scores",
    "risk_level_from_score",
    "extract_joint_heuristic_features",
    "apply_rule_assisted_joint_score",
    "flatten_feature_vector",
]
