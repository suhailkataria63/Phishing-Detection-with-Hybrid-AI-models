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
    host_matches_trusted,
    normalize_unicode_domain,
    safe_decode_idn_host,
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
]
