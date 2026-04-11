"""Utilities for email text normalization and URL extraction."""

from __future__ import annotations

import re
from typing import Iterable, List


# Broad URL pattern for body extraction. Keeps punctuation trimming separate.
URL_RE = re.compile(r"(https?://[^\s<>'\"`]+|www\.[^\s<>'\"`]+)", re.IGNORECASE)
EMAIL_DOMAIN_RE = re.compile(
    r"[A-Z0-9._%+\-]+@([A-Z0-9.\-]+\.[A-Z]{2,})",
    re.IGNORECASE,
)


def build_email_text(subject: str, body: str) -> str:
    """Build canonical model text as `subject + [SEP] + body`."""
    subject_clean = (subject or "").strip()
    body_clean = (body or "").strip()
    return f"{subject_clean} [SEP] {body_clean}".strip()


def _clean_url_candidate(raw: str) -> str:
    s = (raw or "").strip()
    s = s.rstrip(".,;:!?)]}>\"'")
    s = s.lstrip("(<[{\"'")
    if s.lower().startswith("www."):
        s = f"https://{s}"
    return s


def dedupe_preserve_order(values: Iterable[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for v in values:
        key = (v or "").strip()
        if not key:
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def extract_urls_from_text(text: str) -> List[str]:
    """Extract and normalize URL-like substrings from free text."""
    if not text:
        return []
    raw_matches = URL_RE.findall(text)
    cleaned = [_clean_url_candidate(m) for m in raw_matches]
    cleaned = [c for c in cleaned if len(c) >= 8]
    return dedupe_preserve_order(cleaned)


def extract_sender_domain(sender: str) -> str:
    """Extract sender domain from common `From` strings.

    Examples:
    - `security@paypal.com` -> `paypal.com`
    - `PayPal Security <security@paypal.com>` -> `paypal.com`
    - `Amazon India` -> `` (no domain present)
    """
    text = (sender or "").strip()
    if not text:
        return ""
    m = EMAIL_DOMAIN_RE.search(text)
    if not m:
        return ""
    return (m.group(1) or "").strip().lower()
