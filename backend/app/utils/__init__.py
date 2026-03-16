"""Shared backend utilities for URL and domain handling."""

from .domain_utils import (
    TRUST_ECOSYSTEM,
    TRUST_EXACT,
    TRUST_UNTRUSTED,
    TRUSTED_HOST_SUFFIXES,
    classify_trusted_domain,
    detect_typosquat_against_trusted,
    extract_registrable_domain,
    extract_subdomain,
    host_matches_trusted,
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
]
