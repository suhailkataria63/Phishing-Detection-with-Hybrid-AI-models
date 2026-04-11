"""Utilities for robust URL normalization and parsing."""

import re
from urllib.parse import ParseResult, unquote, urlparse, urlunparse

SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+\-.]*://")
IPV4_RE = re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}$")


def normalize_url(url: str) -> str:
    """
    Normalize URL input into a stable representation.

    Rules are intentionally aligned with the existing v1 URL model behavior:
    - if scheme is missing, assume https://
    - lowercase hostname/netloc
    - strip leading www.
    - strip default :80/:443
    - upgrade http -> https
    - ensure path is present
    - drop fragment
    """
    try:
        raw = unquote((url or "").strip())
        if not SCHEME_RE.match(raw):
            raw = "https://" + raw

        parsed = urlparse(raw)

        scheme = (parsed.scheme or "https").lower()
        netloc = (parsed.netloc or "").lower()

        # Handle odd inputs where host is parsed into path.
        if not netloc and parsed.path:
            reparsed = urlparse("https://" + parsed.path)
            parsed = reparsed
            scheme = (reparsed.scheme or "https").lower()
            netloc = (reparsed.netloc or "").lower()

        if netloc.endswith(":80"):
            netloc = netloc[:-3]
        if netloc.endswith(":443"):
            netloc = netloc[:-4]

        if netloc.startswith("www."):
            netloc = netloc[4:]

        if scheme == "http":
            scheme = "https"

        path = parsed.path if parsed.path else "/"
        return urlunparse((scheme, netloc, path, "", parsed.query or "", ""))
    except Exception:
        # Defensive fallback: always return a parseable URL string.
        return "https:///"


def safe_parse_url(url: str) -> ParseResult:
    """
    Parse URL-like input safely and always return a ParseResult.

    This helper is defensive and avoids bubbling parser/format exceptions.
    It also handles odd host-in-path cases by reparsing with https:// prefix.
    """
    try:
        raw = (url or "").strip()
        if not raw:
            raw = "https://"
        if not SCHEME_RE.match(raw):
            raw = "https://" + raw

        parsed = urlparse(raw)
        if not parsed.netloc and parsed.path:
            reparsed = urlparse("https://" + parsed.path)
            if reparsed.netloc:
                return reparsed
        return parsed
    except Exception:
        return urlparse("https://")


def extract_hostname(url: str) -> str:
    """
    Extract lowercase hostname from URL-like input.

    Returns an empty string when hostname cannot be determined.
    """
    try:
        return (safe_parse_url(url).hostname or "").lower()
    except Exception:
        return ""


def is_ip_host(host: str) -> bool:
    """
    Return True when host is a valid IPv4 address.

    Validation includes octet range checks (0..255).
    """
    if not host:
        return False
    candidate = host.strip().lower()
    if not IPV4_RE.match(candidate):
        return False
    try:
        return all(0 <= int(part) <= 255 for part in candidate.split("."))
    except ValueError:
        return False
