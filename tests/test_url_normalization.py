from pathlib import Path
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.utils.url_utils import extract_hostname, is_ip_host, normalize_url, safe_parse_url


@pytest.mark.parametrize(
    ("raw_url", "expected_normalized", "expected_hostname", "expected_is_ip"),
    [
        ("https://paypal.com/security", "https://paypal.com/security", "paypal.com", False),
        (
            "https://docs.python.org/3/library/urllib.parse.html",
            "https://docs.python.org/3/library/urllib.parse.html",
            "docs.python.org",
            False,
        ),
        (
            "https://login.microsoftonline.com/",
            "https://login.microsoftonline.com/",
            "login.microsoftonline.com",
            False,
        ),
        ("https://accounts.google.com/", "https://accounts.google.com/", "accounts.google.com", False),
        ("paypal.com/login", "https://paypal.com/login", "paypal.com", False),
        ("docs.python.org/3/library", "https://docs.python.org/3/library", "docs.python.org", False),
        ("http://192.168.1.10/login", "https://192.168.1.10/login", "192.168.1.10", True),
        ("http://10.0.0.5/admin", "https://10.0.0.5/admin", "10.0.0.5", True),
        (
            "https://example.com/path?a=1&b=2&redirect=http://evil.com",
            "https://example.com/path?a=1&b=2&redirect=http://evil.com",
            "example.com",
            False,
        ),
    ],
)
def test_normalize_extract_host_and_ip(raw_url, expected_normalized, expected_hostname, expected_is_ip):
    normalized = normalize_url(raw_url)
    hostname = extract_hostname(raw_url)

    assert normalized == expected_normalized
    assert hostname == expected_hostname
    assert is_ip_host(hostname) is expected_is_ip


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
def test_malformed_inputs_fail_safely(bad_input):
    normalized = normalize_url(bad_input)
    hostname = extract_hostname(bad_input)
    parsed = safe_parse_url(bad_input)

    assert isinstance(normalized, str)
    assert isinstance(hostname, str)
    assert hasattr(parsed, "scheme")
    assert hasattr(parsed, "netloc")
    assert hasattr(parsed, "path")


def test_ip_detection_validates_octet_range():
    assert is_ip_host("192.168.1.10") is True
    assert is_ip_host("10.0.0.5") is True
    assert is_ip_host("999.1.1.1") is False
