"""Utilities for domain extraction, trust classification, and lookalike detection."""

import unicodedata

from .url_utils import extract_hostname, is_ip_host

TRUST_EXACT = "exact_trusted_brand_domain"
TRUST_ECOSYSTEM = "trusted_subdomain_ecosystem"
TRUST_UNTRUSTED = "untrusted"

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
    "icloud.com",
)

# Lightweight confusable map. Intentionally small/high-signal for TG-3.
CONFUSABLE_CHAR_MAP = {
    # Cyrillic
    "а": "a",
    "е": "e",
    "о": "o",
    "р": "p",
    "с": "c",
    "у": "y",
    "х": "x",
    "і": "i",
    "ј": "j",
    "ӏ": "l",
    # Greek
    "ο": "o",
    "ρ": "p",
    "ν": "v",
    "χ": "x",
}


def _coerce_host(url_or_host: str) -> str:
    """Best-effort conversion of URL-or-host input into a lowercase host string."""
    return extract_hostname(url_or_host) or (url_or_host or "").strip().lower()


def extract_registrable_domain(url_or_host: str) -> str:
    """
    Extract registrable domain using a small heuristic.

    Current heuristic matches existing project behavior:
    - take last two labels (e.g. docs.python.org -> python.org)
    - fallback to host for single-label hosts or IP literals
    """
    host = _coerce_host(url_or_host)
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
    host = _coerce_host(url_or_host)
    parts = [label for label in host.split(".") if label]
    if len(parts) <= 2:
        return ""
    return ".".join(parts[:-2])


def normalize_unicode_domain(url_or_host: str) -> str:
    """
    Apply unicode normalization for safer confusable comparison.

    NFKC + casefold is used to reduce representation variance.
    """
    host = _coerce_host(url_or_host)
    if not host:
        return ""
    return unicodedata.normalize("NFKC", host).casefold()


def safe_decode_idn_host(url_or_host: str) -> str:
    """
    Safely decode IDN/punycode labels when possible.

    Invalid labels are preserved as-is to avoid exceptions.
    """
    host = _coerce_host(url_or_host)
    if not host:
        return ""

    decoded = []
    for label in host.split("."):
        if not label:
            continue
        if label.startswith("xn--"):
            try:
                decoded.append(label.encode("ascii").decode("idna"))
                continue
            except Exception:
                pass
        decoded.append(label)
    return ".".join(decoded)


def confusable_domain_skeleton(url_or_host: str) -> str:
    """
    Build a lightweight confusable/skeleton domain representation.

    Steps:
    - safe IDN decode
    - unicode NFKC + casefold
    - map selected confusable characters to ASCII lookalikes
    """
    normalized = normalize_unicode_domain(safe_decode_idn_host(url_or_host))
    if not normalized:
        return ""

    chars = []
    for ch in normalized:
        chars.append(CONFUSABLE_CHAR_MAP.get(ch, ch))
    return "".join(chars)


def _levenshtein(a: str, b: str) -> int:
    """Compute Levenshtein distance between two strings."""
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


def _trusted_registrable_set(trusted_host_suffixes=TRUSTED_HOST_SUFFIXES) -> set:
    """Return normalized registrable domains derived from trusted host suffixes."""
    return {extract_registrable_domain(s) for s in trusted_host_suffixes}


def classify_trusted_domain(url_or_host: str, trusted_host_suffixes=TRUSTED_HOST_SUFFIXES) -> str:
    """
    Classify host into one of:
    - TRUST_EXACT: exact trusted registrable brand domain (e.g. paypal.com)
    - TRUST_ECOSYSTEM: trusted subdomain/ecosystem host (e.g. docs.python.org)
    - TRUST_UNTRUSTED: not trusted
    """
    host = _coerce_host(url_or_host)
    if not host:
        return TRUST_UNTRUSTED

    reg = extract_registrable_domain(host)
    trusted_regs = _trusted_registrable_set(trusted_host_suffixes)
    if reg in trusted_regs:
        return TRUST_EXACT if host == reg else TRUST_ECOSYSTEM

    # Fallback for exact suffix allowlist checks if needed.
    if any(host == s or host.endswith("." + s) for s in trusted_host_suffixes):
        return TRUST_ECOSYSTEM

    return TRUST_UNTRUSTED


def host_matches_trusted(url_or_host: str, trusted_host_suffixes=TRUSTED_HOST_SUFFIXES) -> bool:
    """Return True when host is either exact trusted domain or trusted ecosystem subdomain."""
    return classify_trusted_domain(url_or_host, trusted_host_suffixes) != TRUST_UNTRUSTED


def find_confusable_match_against_trusted(url_or_host: str, trusted_host_suffixes=TRUSTED_HOST_SUFFIXES):
    """
    Compare candidate domain skeleton against trusted registrable skeletons.

    Returns tuple: (is_confusable_match, info_dict_or_none)
    """
    host = _coerce_host(url_or_host)
    if not host or is_ip_host(host):
        return False, None

    reg = extract_registrable_domain(host)
    reg_skeleton = confusable_domain_skeleton(reg)
    if not reg_skeleton:
        return False, None

    trusted_regs = _trusted_registrable_set(trusted_host_suffixes)
    for trusted_reg in trusted_regs:
        trusted_skeleton = confusable_domain_skeleton(trusted_reg)
        if reg_skeleton == trusted_skeleton and reg != trusted_reg:
            return True, {
                "host": host,
                "registrable": reg,
                "closest_trusted": trusted_reg,
                "match_type": "confusable_skeleton",
                "candidate_skeleton": reg_skeleton,
                "trusted_skeleton": trusted_skeleton,
            }
    return False, None


def detect_typosquat_against_trusted(url_or_host: str, trusted_host_suffixes=TRUSTED_HOST_SUFFIXES):
    """
    Detect trusted-brand lookalikes via:
    - ASCII distance-1 typosquat check
    - confusable/homoglyph skeleton comparison

    Exact trusted registrable domains and trusted ecosystem hosts are explicitly excluded.
    Returns tuple: (is_typosquat_or_lookalike, info_dict_or_none).
    """
    host = _coerce_host(url_or_host)
    if not host or is_ip_host(host):
        return False, None

    trust_kind = classify_trusted_domain(host, trusted_host_suffixes)
    if trust_kind != TRUST_UNTRUSTED:
        return False, None

    reg = extract_registrable_domain(host)
    trusted_regs = _trusted_registrable_set(trusted_host_suffixes)

    # Safety guard: never flag exact trusted registrable domains.
    if reg in trusted_regs:
        return False, None

    best = None
    best_d = 10**9
    for trusted_reg in trusted_regs:
        d = _levenshtein(reg, trusted_reg)
        if d < best_d:
            best_d = d
            best = trusted_reg

    # ASCII typosquat signal.
    if best is not None and best_d <= 1:
        return True, {
            "host": host,
            "registrable": reg,
            "closest_trusted": best,
            "distance": best_d,
            "match_type": "levenshtein",
            "trust_kind": trust_kind,
        }

    # Confusable/homoglyph signal.
    confusable_hit, confusable_info = find_confusable_match_against_trusted(
        host, trusted_host_suffixes
    )
    if confusable_hit:
        info = dict(confusable_info or {})
        info["trust_kind"] = trust_kind
        return True, info

    return False, None
