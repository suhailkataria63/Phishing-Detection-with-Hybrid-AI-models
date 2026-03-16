from pathlib import Path
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.utils.domain_utils import extract_registrable_domain, extract_subdomain
from app.utils.url_utils import extract_hostname, is_ip_host


@pytest.mark.parametrize(
    ("raw_url", "expected_registrable", "expected_subdomain"),
    [
        ("https://paypal.com/security", "paypal.com", ""),
        ("https://docs.python.org/3/library/urllib.parse.html", "python.org", "docs"),
        ("https://login.microsoftonline.com/", "microsoftonline.com", "login"),
        ("https://accounts.google.com/", "google.com", "accounts"),
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
