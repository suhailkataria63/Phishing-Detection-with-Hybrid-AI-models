from pathlib import Path
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.utils.domain_utils import extract_registrable_domain, extract_subdomain
from app.utils.url_utils import extract_hostname, is_ip_host
from app.utils.domain_utils import (
    TRUST_ECOSYSTEM,
    TRUST_EXACT,
    TRUST_UNTRUSTED,
    classify_trusted_domain,
    detect_typosquat_against_trusted,
)


@pytest.mark.parametrize(
    ("raw_url", "expected_registrable", "expected_subdomain"),
    [
        ("https://paypal.com/security", "paypal.com", ""),
        ("https://www.paypal.com/", "paypal.com", "www"),
        ("https://docs.python.org/3/library/urllib.parse.html", "python.org", "docs"),
        ("https://login.microsoftonline.com/", "microsoftonline.com", "login"),
        ("https://accounts.google.com/", "google.com", "accounts"),
        ("https://yahoo.com/login", "yahoo.com", ""),
        ("paypal.com/login", "paypal.com", ""),
        ("docs.python.org/3/library", "python.org", "docs"),
        ("http://192.168.1.10/login", "1.10", "192.168"),
        ("http://10.0.0.5/admin", "0.5", "10.0"),
        ("https://example.com/path?a=1&b=2&redirect=http://evil.com", "example.com", ""),
    ],
)
def test_registrable_domain_and_subdomain_current_behavior(
    raw_url, expected_registrable, expected_subdomain
):
    assert extract_registrable_domain(raw_url) == expected_registrable
    assert extract_subdomain(raw_url) == expected_subdomain


@pytest.mark.parametrize(
    "bad_input",
    [
        "",
        "   ",
        "://bad",
        "http://",
        "not a url",
    ],
)
def test_domain_helpers_fail_safely_for_malformed_inputs(bad_input):
    registrable = extract_registrable_domain(bad_input)
    subdomain = extract_subdomain(bad_input)
    hostname = extract_hostname(bad_input)

    assert isinstance(registrable, str)
    assert isinstance(subdomain, str)
    assert isinstance(hostname, str)
    assert is_ip_host(hostname) in (True, False)


@pytest.mark.parametrize(
    ("raw_url", "expected_kind"),
    [
        ("https://paypal.com/security", TRUST_EXACT),
        ("https://www.paypal.com/", TRUST_ECOSYSTEM),
        ("https://login.microsoftonline.com/", TRUST_ECOSYSTEM),
        ("https://docs.python.org/3/library/urllib.parse.html", TRUST_ECOSYSTEM),
        ("https://yahoo.com/login", TRUST_EXACT),
        ("https://paypa1.com/security", TRUST_UNTRUSTED),
    ],
)
def test_trusted_domain_classification(raw_url, expected_kind):
    assert classify_trusted_domain(raw_url) == expected_kind


@pytest.mark.parametrize(
    "trusted_url",
    [
        "https://paypal.com/security",
        "https://www.paypal.com/",
        "https://login.microsoftonline.com/",
        "https://docs.python.org/3/library/urllib.parse.html",
        "https://yahoo.com/login",
    ],
)
def test_exact_or_ecosystem_trusted_domains_are_not_flagged_as_fake_brand(trusted_url):
    is_typosquat, info = detect_typosquat_against_trusted(trusted_url)
    assert is_typosquat is False
    assert info is None


def test_simple_typosquat_is_flagged():
    is_typosquat, info = detect_typosquat_against_trusted("https://paypa1.com/security")
    assert is_typosquat is True
    assert info is not None
    assert info["closest_trusted"] == "paypal.com"
