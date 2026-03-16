"""Utilities for simple registrable-domain and subdomain extraction."""

from .url_utils import extract_hostname


def extract_registrable_domain(url_or_host: str) -> str:
    """
    Extract registrable domain using a small heuristic.

    Current heuristic matches existing project behavior:
    - take last two labels (e.g. docs.python.org -> python.org)
    - fallback to host for single-label hosts or IP literals
    """
    host = extract_hostname(url_or_host) or (url_or_host or "").strip().lower()
    parts = [label for label in host.split(".") if label]
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return host


def extract_subdomain(url_or_host: str) -> str:
    """
    Extract subdomain portion using the same two-label registrable heuristic.

    Examples:
    - docs.python.org -> docs
    - a.b.example.com -> a.b
    - example.com -> ""
    """
    host = extract_hostname(url_or_host) or (url_or_host or "").strip().lower()
    parts = [label for label in host.split(".") if label]
    if len(parts) <= 2:
        return ""
    return ".".join(parts[:-2])
