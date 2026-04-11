"""Transparent joint scoring logic for email + URL phishing signals."""

from __future__ import annotations

from typing import Dict, List, Sequence


def risk_level_from_score(score: float) -> str:
    if score >= 0.9:
        return "critical"
    if score >= 0.7:
        return "high"
    if score >= 0.4:
        return "medium"
    return "low"


def combine_email_url_scores(
    email_score: float,
    url_scores: Sequence[float],
    threshold: float = 0.5,
    all_urls_reputable: bool = False,
    any_url_hard_cue: bool = False,
    sender_url_mismatch_score: float = 0.0,
    email_hard_cue_count: int = 0,
) -> Dict[str, object]:
    """Combine email and URL signals using an explainable rule-based ensemble.

    Base formula:
    - final = 0.6 * email_score + 0.4 * max_url_score
    Escalation guardrails:
    - very high URL score should not be suppressed
    - very high email score without URLs should still escalate
    """
    safe_email = float(max(0.0, min(1.0, email_score)))
    safe_urls = [float(max(0.0, min(1.0, s))) for s in url_scores]

    max_url = max(safe_urls) if safe_urls else 0.0
    avg_url = (sum(safe_urls) / len(safe_urls)) if safe_urls else 0.0
    risky_url_count = sum(1 for s in safe_urls if s >= 0.5)

    email_weight = 0.6
    url_weight = 0.4
    final_score = (email_weight * safe_email) + (url_weight * max_url)
    reasons: List[str] = []

    if safe_urls and all_urls_reputable and not any_url_hard_cue:
        # Mild reputation-aware dampening:
        # if all URLs are reputable and there are no hard URL cues, cap the
        # URL channel's influence to avoid overreacting to soft lexical noise.
        # This is intentionally conservative (does not auto-force legitimate).
        max_url = min(max_url, 0.45)
        avg_url = min(avg_url, 0.45)
        email_weight = 0.65
        url_weight = 0.35
        final_score = (email_weight * safe_email) + (url_weight * max_url)
        reasons.append(
            "Reputation dampening applied: URLs are trusted/top-ranked with no hard URL cues, so URL-channel spikes were softened."
        )

        if max_url <= 0.10 and risky_url_count == 0:
            # Stronger benign guard for clearly low-risk reputable URLs.
            # This directly addresses common shipment/statement false positives
            # where text-only score runs hot.
            email_weight = 0.45
            url_weight = 0.55
            final_score = (email_weight * safe_email) + (url_weight * max_url)
            final_score = min(final_score, 0.45)
            reasons.append(
                "Low-risk reputable URL guard applied: with no hard URL cues and near-zero URL risk, final score was capped below phishing threshold."
            )

    if safe_urls and sender_url_mismatch_score > 0:
        mismatch_boost = min(0.18, 0.2 * float(sender_url_mismatch_score))
        if safe_email >= 0.45 or max_url >= 0.35 or email_hard_cue_count >= 1:
            final_score = min(0.99, final_score + mismatch_boost)
            reasons.append(
                "Sender/URL domain mismatch increased risk due to low domain-consistency confidence."
            )
        if sender_url_mismatch_score >= 0.75 and (safe_email >= 0.6 or max_url >= 0.4):
            final_score = max(final_score, 0.68)
            reasons.append(
                "Strong sender/URL mismatch with suspicious channel evidence triggered escalation."
            )

    if (not safe_urls) and email_hard_cue_count >= 2 and safe_email >= 0.45:
        final_score = max(final_score, 0.62)
        reasons.append(
            "Email-only hard cues indicate social-engineering intent; escalated despite absent URL evidence."
        )

    reasons.insert(
        0,
        f"Base score uses weighted blend: {email_weight:.2f} * email + {url_weight:.2f} * max_url.",
    )

    if safe_urls and max_url >= 0.9:
        final_score = max(final_score, 0.9)
        reasons.append("Escalated: at least one URL is extremely high risk (>= 0.9).")

    if not safe_urls and safe_email >= 0.9:
        final_score = max(final_score, 0.9)
        reasons.append("Escalated: high email-only risk with no URLs available.")

    if safe_urls and safe_email >= 0.75 and max_url >= 0.75:
        final_score = max(final_score, 0.92)
        reasons.append("Escalated: both email and URL channels are strongly suspicious.")

    if risky_url_count >= 2:
        final_score = min(0.97, final_score + 0.05)
        reasons.append("Escalated: multiple risky URLs detected in the same message.")

    final_score = float(max(0.0, min(1.0, final_score)))
    final_label = "phishing" if final_score >= threshold else "legitimate"
    risk_level = risk_level_from_score(final_score)

    return {
        "final_score": final_score,
        "final_label": final_label,
        "risk_level": risk_level,
        "email_score": safe_email,
        "url_score": max_url,
        "avg_url_score": avg_url,
        "risky_url_count": risky_url_count,
        "analyzed_url_count": len(safe_urls),
        "email_weight": email_weight,
        "url_weight": url_weight,
        "all_urls_reputable": all_urls_reputable,
        "any_url_hard_cue": any_url_hard_cue,
        "sender_url_mismatch_score": float(max(0.0, min(1.0, sender_url_mismatch_score))),
        "email_hard_cue_count": int(max(0, email_hard_cue_count)),
        "reasons": reasons,
    }
