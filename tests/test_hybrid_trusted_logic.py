from pathlib import Path
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.ml.hybrid_url import HybridURLModel
from app.utils.domain_utils import TRUST_ECOSYSTEM, TRUST_EXACT, TRUST_UNTRUSTED


@pytest.fixture(scope="module")
def hybrid_model():
    model = HybridURLModel()
    model.load()
    return model


@pytest.mark.parametrize(
    ("url", "expected_trust_kind"),
    [
        ("https://paypal.com/security", TRUST_EXACT),
        ("https://www.paypal.com/", TRUST_EXACT),
        ("https://login.microsoftonline.com/", TRUST_ECOSYSTEM),
        ("https://docs.python.org/3/library/urllib.parse.html", TRUST_ECOSYSTEM),
        ("https://yahoo.com/login", TRUST_EXACT),
    ],
)
def test_trusted_regression_urls_not_marked_fake_brand(hybrid_model, url, expected_trust_kind):
    out = hybrid_model.predict(url, enable_explain=True)

    reason_features = [r.get("feature") for r in out.get("reasons", [])]

    assert out["label"] == "legitimate"
    assert out["meta"]["is_trusted"] is True
    assert out["meta"]["trust_kind"] == expected_trust_kind
    assert "fake_brand_domain" not in reason_features
    if expected_trust_kind == TRUST_EXACT:
        assert "trusted_exact_domain_exemption" in reason_features


def test_typosquat_paypa1_is_untrusted_and_flagged_fake_brand(hybrid_model):
    out = hybrid_model.predict("https://paypa1.com/security", enable_explain=True)
    reason_features = [r.get("feature") for r in out.get("reasons", [])]

    assert out["meta"]["is_trusted"] is False
    assert out["meta"]["trust_kind"] == TRUST_UNTRUSTED
    assert "fake_brand_domain" in reason_features


def test_confusable_punycode_lookalike_is_untrusted_and_flagged(hybrid_model):
    out = hybrid_model.predict("https://xn--80ak6aa92e.com/security", enable_explain=True)
    fake_brand_reason = next(r for r in out["reasons"] if r.get("feature") == "fake_brand_domain")

    assert out["meta"]["is_trusted"] is False
    assert out["meta"]["trust_kind"] == TRUST_UNTRUSTED
    assert out["label"] == "phishing"
    assert fake_brand_reason["value"]["match_type"] == "confusable_skeleton"
    assert "confusable/homoglyph" in fake_brand_reason["note"].lower()
