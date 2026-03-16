"""Utilities for domain extraction, trust classification, and typosquat checks."""

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


def detect_typosquat_against_trusted(url_or_host: str, trusted_host_suffixes=TRUSTED_HOST_SUFFIXES):
    """
    Detect simple distance-1 typosquat against trusted registrable domains.

    Exact trusted registrable domains and trusted ecosystem hosts are explicitly excluded.
    Returns tuple: (is_typosquat, info_dict_or_none).
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

    if best is not None and best_d <= 1:
        return True, {
            "host": host,
            "registrable": reg,
            "closest_trusted": best,
            "distance": best_d,
            "trust_kind": trust_kind,
        }

    return False, None
