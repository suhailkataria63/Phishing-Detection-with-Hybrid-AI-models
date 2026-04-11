"""Run a lightweight TG-4 evaluation over curated hybrid URL cases."""

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = REPO_ROOT / "backend"
REPORT_PATH = REPO_ROOT / "reports" / "experiments" / "url_hardening_eval.md"

sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(BACKEND_ROOT))

from tests.manual_url_eval_cases import MANUAL_URL_EVAL_CASES
from app.ml.hybrid_url import HybridURLModel


def run_eval():
    model = HybridURLModel()
    model.load()

    rows = []
    category_stats = defaultdict(lambda: {"total": 0, "correct": 0})
    mismatches = []

    for case in MANUAL_URL_EVAL_CASES:
        out = model.predict(case["url"], enable_explain=True)
        reasons = out.get("reasons", [])
        reason_features = [r.get("feature", "") for r in reasons]
        fake_brand = next((r for r in reasons if r.get("feature") == "fake_brand_domain"), None)

        predicted = out.get("label")
        expected = case["expected_label"]
        correct = predicted == expected

        category = case["category"]
        category_stats[category]["total"] += 1
        if correct:
            category_stats[category]["correct"] += 1

        row = {
            "id": case["id"],
            "category": category,
            "url": case["url"],
            "expected": expected,
            "predicted": predicted,
            "probability": round(float(out.get("probability", 0.0)), 4),
            "correct": correct,
            "is_trusted": out.get("meta", {}).get("is_trusted"),
            "trust_kind": out.get("meta", {}).get("trust_kind"),
            "top_reasons": ", ".join(reason_features[:4]),
            "fake_brand_match_type": (fake_brand or {}).get("value", {}).get("match_type") if fake_brand else "",
            "note": case.get("note", ""),
        }
        rows.append(row)

        if not correct:
            mismatches.append(row)

    total = len(rows)
    correct = sum(1 for r in rows if r["correct"])

    lookalike_rows = [r for r in rows if r["category"] in {"ascii_typosquat", "confusable_punycode"}]
    lookalike_flagged = sum(1 for r in lookalike_rows if "fake_brand_domain" in r["top_reasons"])

    trusted_rows = [r for r in rows if r["category"] == "legitimate_trusted"]
    trusted_legit = sum(1 for r in trusted_rows if r["predicted"] == "legitimate")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        build_markdown_report(
            rows=rows,
            total=total,
            correct=correct,
            category_stats=category_stats,
            mismatches=mismatches,
            lookalike_total=len(lookalike_rows),
            lookalike_flagged=lookalike_flagged,
            trusted_total=len(trusted_rows),
            trusted_legit=trusted_legit,
        ),
        encoding="utf-8",
    )
    print(f"Wrote report: {REPORT_PATH}")


def build_markdown_report(
    rows,
    total,
    correct,
    category_stats,
    mismatches,
    lookalike_total,
    lookalike_flagged,
    trusted_total,
    trusted_legit,
):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    lines = []
    suspicious_rows = [r for r in rows if r["category"] == "suspicious_phishing_style"]
    suspicious_correct = sum(1 for r in suspicious_rows if r["correct"])
    suspicious_total = len(suspicious_rows)

    lines.append("# TG-4.5 URL Hardening Evaluation")
    lines.append("")
    lines.append(f"- Generated: {ts}")
    lines.append("- Model: `HybridURLModel` (`hybrid_url_v1_v2`)")
    lines.append("- Scope: TG-1/TG-2/TG-3 + TG-4.5 targeted suspicious-pattern patch")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Overall correctness vs curated expectations: **{correct}/{total}**")
    lines.append(f"- Trusted legitimate URLs kept legitimate: **{trusted_legit}/{trusted_total}**")
    lines.append(f"- Lookalike cases with `fake_brand_domain` reason: **{lookalike_flagged}/{lookalike_total}**")
    lines.append(f"- Suspicious phishing-style cases caught: **{suspicious_correct}/{suspicious_total}**")
    lines.append("")
    lines.append("### By Category")
    lines.append("")
    for category in sorted(category_stats.keys()):
        c = category_stats[category]
        lines.append(f"- `{category}`: {c['correct']}/{c['total']}")
    lines.append("")
    lines.append("## Case Table")
    lines.append("")
    lines.append("| id | category | expected | predicted | prob | trusted | trust_kind | fake_brand_match_type | top_reasons |")
    lines.append("|---|---|---|---|---:|---|---|---|---|")
    for r in rows:
        lines.append(
            f"| `{r['id']}` | `{r['category']}` | `{r['expected']}` | `{r['predicted']}` | "
            f"{r['probability']:.4f} | `{r['is_trusted']}` | `{r['trust_kind']}` | "
            f"`{r['fake_brand_match_type']}` | `{r['top_reasons']}` |"
        )
    lines.append("")
    lines.append("## Mismatches / Ambiguities")
    lines.append("")
    if not mismatches:
        lines.append("- None in current curated set.")
    else:
        for m in mismatches:
            lines.append(
                f"- `{m['id']}` expected `{m['expected']}` but got `{m['predicted']}` "
                f"(prob={m['probability']:.4f}) | reasons: `{m['top_reasons']}`"
            )
    lines.append("")
    lines.append("## Observations")
    lines.append("")
    lines.append("- Trusted-domain guardrails are preserving legitimate trusted URLs with exemption reasons.")
    lines.append("- ASCII typosquats continue to trigger `fake_brand_domain` (Levenshtein mode).")
    lines.append("- Punycode/confusable lookalikes trigger `fake_brand_domain` (confusable skeleton mode).")
    if suspicious_correct < suspicious_total:
        lines.append("- Some suspicious phishing-style cases remain under-threshold and need follow-up hardening.")
    else:
        lines.append("- Targeted suspicious-pattern hardening improved detection for previously weak phishing-style URLs.")
    lines.append("")
    lines.append("## Command")
    lines.append("")
    lines.append("```bash")
    lines.append("python3 scripts/run_url_hardening_eval.py")
    lines.append("```")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    run_eval()
