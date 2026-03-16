"""Curated manual evaluation cases for TG-4 URL hardening checks."""

MANUAL_URL_EVAL_CASES = [
    # Legitimate trusted URLs (false-positive guardrails)
    {
        "id": "legit_paypal_security",
        "category": "legitimate_trusted",
        "url": "https://paypal.com/security",
        "expected_label": "legitimate",
        "note": "Exact trusted brand domain with security keyword.",
    },
    {
        "id": "legit_www_paypal",
        "category": "legitimate_trusted",
        "url": "https://www.paypal.com/",
        "expected_label": "legitimate",
        "note": "Trusted domain with common www prefix.",
    },
    {
        "id": "legit_microsoftonline_login",
        "category": "legitimate_trusted",
        "url": "https://login.microsoftonline.com/",
        "expected_label": "legitimate",
        "note": "Trusted ecosystem subdomain.",
    },
    {
        "id": "legit_docs_python_parse",
        "category": "legitimate_trusted",
        "url": "https://docs.python.org/3/library/urllib.parse.html",
        "expected_label": "legitimate",
        "note": "Trusted docs URL with long path and punctuation.",
    },
    {
        "id": "legit_google_accounts",
        "category": "legitimate_trusted",
        "url": "https://accounts.google.com/",
        "expected_label": "legitimate",
        "note": "Trusted account/login flow.",
    },
    {
        "id": "legit_yahoo_login",
        "category": "legitimate_trusted",
        "url": "https://yahoo.com/login",
        "expected_label": "legitimate",
        "note": "Exact trusted brand domain with login path.",
    },
    # Suspicious phishing-style URLs
    {
        "id": "suspicious_xyz_lure",
        "category": "suspicious_phishing_style",
        "url": "http://secure-login.verify-account.update-now.xyz/login",
        "expected_label": "phishing",
        "note": "Keyword-heavy lure with suspicious TLD and deep subdomain chain.",
    },
    {
        "id": "suspicious_ip_login",
        "category": "suspicious_phishing_style",
        "url": "http://192.168.1.10/login",
        "expected_label": "phishing",
        "note": "Raw IP host with login path.",
    },
    {
        "id": "suspicious_ip_admin",
        "category": "suspicious_phishing_style",
        "url": "http://10.0.0.5/admin",
        "expected_label": "phishing",
        "note": "Internal-style IP host and sensitive admin path.",
    },
    {
        "id": "suspicious_redirect_param",
        "category": "suspicious_phishing_style",
        "url": "https://example.com/path?a=1&b=2&redirect=http://evil.com",
        "expected_label": "phishing",
        "note": "Contains embedded http redirect parameter.",
    },
    {
        "id": "suspicious_keyword_biz",
        "category": "suspicious_phishing_style",
        "url": "https://free-gift-card-verify-now.biz/login",
        "expected_label": "phishing",
        "note": "Promotional lure + risky lexical pattern.",
    },
    # ASCII typosquats
    {
        "id": "ascii_typosquat_paypa1",
        "category": "ascii_typosquat",
        "url": "https://paypa1.com/security",
        "expected_label": "phishing",
        "note": "Digit substitution typo against paypal.com.",
    },
    {
        "id": "ascii_typosquat_googIe",
        "category": "ascii_typosquat",
        "url": "https://googIe.com/login",
        "expected_label": "phishing",
        "note": "Visual l/I swap that normalizes to a near-match typo.",
    },
    {
        "id": "ascii_typosquat_paypaI",
        "category": "ascii_typosquat",
        "url": "https://paypaI.com/login",
        "expected_label": "phishing",
        "note": "Visual l/I swap that normalizes to a near-match typo.",
    },
    {
        "id": "ascii_typosquat_micros0ftonline",
        "category": "ascii_typosquat",
        "url": "https://micros0ftonline.com/auth",
        "expected_label": "phishing",
        "note": "0/o brand impersonation.",
    },
    # Confusable / punycode lookalikes
    {
        "id": "idn_confusable_apple",
        "category": "confusable_punycode",
        "url": "https://xn--80ak6aa92e.com/security",
        "expected_label": "phishing",
        "note": "Punycode confusable that skeleton-maps to apple.com.",
    },
    {
        "id": "idn_confusable_paypal",
        "category": "confusable_punycode",
        "url": "https://xn--l-7sba6dbr.com/login",
        "expected_label": "phishing",
        "note": "Punycode confusable that skeleton-maps to paypal.com.",
    },
    {
        "id": "idn_confusable_google",
        "category": "confusable_punycode",
        "url": "https://xn--ggle-0nda.com/signin",
        "expected_label": "phishing",
        "note": "Punycode confusable that skeleton-maps to google.com.",
    },
]
