# TG-4.5 URL Hardening Evaluation

- Generated: 2026-03-16 14:38:00 UTC
- Model: `HybridURLModel` (`hybrid_url_v1_v2`)
- Scope: TG-1/TG-2/TG-3 + TG-4.5 targeted suspicious-pattern patch

## Summary

- Overall correctness vs curated expectations: **18/18**
- Trusted legitimate URLs kept legitimate: **6/6**
- Lookalike cases with `fake_brand_domain` reason: **7/7**
- Suspicious phishing-style cases caught: **5/5**

### By Category

- `ascii_typosquat`: 4/4
- `confusable_punycode`: 3/3
- `legitimate_trusted`: 6/6
- `suspicious_phishing_style`: 5/5

## Case Table

| id | category | expected | predicted | prob | trusted | trust_kind | fake_brand_match_type | top_reasons |
|---|---|---|---|---:|---|---|---|---|
| `legit_paypal_security` | `legitimate_trusted` | `legitimate` | `legitimate` | 0.1243 | `True` | `exact_trusted_brand_domain` | `` | `trusted_soft_cues_override, trusted_veto, trusted_exact_domain_exemption, trusted_domain_guard` |
| `legit_www_paypal` | `legitimate_trusted` | `legitimate` | `legitimate` | 0.1095 | `True` | `exact_trusted_brand_domain` | `` | `trusted_soft_cues_override, trusted_veto, trusted_exact_domain_exemption, trusted_domain_guard` |
| `legit_microsoftonline_login` | `legitimate_trusted` | `legitimate` | `legitimate` | 0.2500 | `True` | `trusted_subdomain_ecosystem` | `` | `trusted_soft_cues_override, trusted_veto, trusted_domain_guard, keyword_count` |
| `legit_docs_python_parse` | `legitimate_trusted` | `legitimate` | `legitimate` | 0.0073 | `True` | `trusted_subdomain_ecosystem` | `` | `trusted_soft_cues_override, trusted_docs_override, trusted_veto, trusted_docs_guard` |
| `legit_google_accounts` | `legitimate_trusted` | `legitimate` | `legitimate` | 0.0183 | `True` | `trusted_subdomain_ecosystem` | `` | `trusted_soft_cues_override, trusted_veto, trusted_domain_guard, keyword_count` |
| `legit_yahoo_login` | `legitimate_trusted` | `legitimate` | `legitimate` | 0.0570 | `True` | `exact_trusted_brand_domain` | `` | `trusted_soft_cues_override, trusted_veto, trusted_exact_domain_exemption, trusted_domain_guard` |
| `suspicious_xyz_lure` | `suspicious_phishing_style` | `phishing` | `phishing` | 0.9325 | `False` | `untrusted` | `` | `untrusted_lure_pattern, rule_override, tld_suspicious, keyword_count` |
| `suspicious_ip_login` | `suspicious_phishing_style` | `phishing` | `phishing` | 0.8800 | `False` | `untrusted` | `` | `ip_sensitive_path, has_ip_host, keyword_count` |
| `suspicious_ip_admin` | `suspicious_phishing_style` | `phishing` | `phishing` | 0.8800 | `False` | `untrusted` | `` | `ip_sensitive_path, has_ip_host` |
| `suspicious_redirect_param` | `suspicious_phishing_style` | `phishing` | `phishing` | 0.7800 | `False` | `untrusted` | `` | `embedded_redirect_target, has_http_in_path, entropy_url` |
| `suspicious_keyword_biz` | `suspicious_phishing_style` | `phishing` | `phishing` | 0.8638 | `False` | `untrusted` | `` | `untrusted_lure_pattern, keyword_count, entropy_url` |
| `ascii_typosquat_paypa1` | `ascii_typosquat` | `phishing` | `phishing` | 0.9500 | `False` | `untrusted` | `levenshtein` | `fake_brand_domain, keyword_count` |
| `ascii_typosquat_googIe` | `ascii_typosquat` | `phishing` | `phishing` | 0.9500 | `False` | `untrusted` | `levenshtein` | `fake_brand_domain, keyword_count` |
| `ascii_typosquat_paypaI` | `ascii_typosquat` | `phishing` | `phishing` | 0.9500 | `False` | `untrusted` | `levenshtein` | `fake_brand_domain, keyword_count` |
| `ascii_typosquat_micros0ftonline` | `ascii_typosquat` | `phishing` | `phishing` | 0.9500 | `False` | `untrusted` | `levenshtein` | `fake_brand_domain` |
| `idn_confusable_apple` | `confusable_punycode` | `phishing` | `phishing` | 0.9500 | `False` | `untrusted` | `confusable_skeleton` | `fake_brand_domain, entropy_url` |
| `idn_confusable_paypal` | `confusable_punycode` | `phishing` | `phishing` | 0.9500 | `False` | `untrusted` | `confusable_skeleton` | `fake_brand_domain, keyword_count, entropy_url` |
| `idn_confusable_google` | `confusable_punycode` | `phishing` | `phishing` | 0.9500 | `False` | `untrusted` | `confusable_skeleton` | `fake_brand_domain, keyword_count` |

## Mismatches / Ambiguities

- None in current curated set.

## Observations

- Trusted-domain guardrails are preserving legitimate trusted URLs with exemption reasons.
- ASCII typosquats continue to trigger `fake_brand_domain` (Levenshtein mode).
- Punycode/confusable lookalikes trigger `fake_brand_domain` (confusable skeleton mode).
- Targeted suspicious-pattern hardening improved detection for previously weak phishing-style URLs.

## Command

```bash
python3 scripts/run_url_hardening_eval.py
```
