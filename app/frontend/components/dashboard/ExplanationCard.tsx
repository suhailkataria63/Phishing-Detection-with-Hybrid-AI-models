import { SectionCard } from "@/components/shared/SectionCard";
import { shortExplain } from "@/lib/format";
import { JointResponse, Reason, UnifiedResult } from "@/lib/types";

type ExplanationItem = {
  title: string;
  detail: string;
  value?: string;
  category: "suspicious" | "benign" | "neutral";
};

type ExplanationCardProps = {
  result: UnifiedResult;
};

const JOINT_META_HINTS: Array<{
  key: string;
  title: string;
  positiveNote: string;
  negativeNote: string;
  categoryPositive: ExplanationItem["category"];
  categoryNegative: ExplanationItem["category"];
}> = [
  {
    key: "trusted_domain_match",
    title: "Trusted domain match",
    positiveNote: "Detected domain aligned with trusted ecosystem context.",
    negativeNote: "No strong trusted-domain alignment found.",
    categoryPositive: "benign",
    categoryNegative: "neutral",
  },
  {
    key: "brand_domain_mismatch",
    title: "Brand-domain mismatch",
    positiveNote: "Sender/brand context does not align with linked domain.",
    negativeNote: "No major brand-domain mismatch observed.",
    categoryPositive: "suspicious",
    categoryNegative: "benign",
  },
  {
    key: "no_url_benign_support",
    title: "Benign no-URL support",
    positiveNote: "No-URL benign language lowered risk.",
    negativeNote: "No benign no-URL suppression signal.",
    categoryPositive: "benign",
    categoryNegative: "neutral",
  },
  {
    key: "suspicious_url_escalation",
    title: "Suspicious URL escalation",
    positiveNote: "URL structure patterns escalated risk.",
    negativeNote: "No high-risk URL structural escalation detected.",
    categoryPositive: "suspicious",
    categoryNegative: "benign",
  },
];

function classifyReason(reason: Reason): ExplanationItem["category"] {
  const combined = `${reason.feature} ${reason.note}`.toLowerCase();
  if (/(match|aligned|benign|safe|trusted)/.test(combined)) return "benign";
  if (/(mismatch|phish|suspicious|fake|redirect|ip|lure|hard cue|typosquat)/.test(combined)) return "suspicious";
  return "neutral";
}

export function ExplanationCard({ result }: ExplanationCardProps) {
  const reasonItems: ExplanationItem[] = (result.reasons || []).slice(0, 12).map((reason) => ({
    title: reason.feature,
    detail: reason.note,
    value: shortExplain(reason.value),
    category: classifyReason(reason),
  }));

  if (result.mode === "joint") {
    const meta = ((result.raw as JointResponse).meta || {}) as Record<string, unknown>;
    JOINT_META_HINTS.forEach((hint) => {
      const value = Boolean(meta[hint.key]);
      reasonItems.push({
        title: hint.title,
        detail: value ? hint.positiveNote : hint.negativeNote,
        value: value ? "true" : "false",
        category: value ? hint.categoryPositive : hint.categoryNegative,
      });
    });

    if (typeof meta.strategy_version === "string") {
      reasonItems.push({
        title: "Strategy version",
        detail: "Joint strategy metadata for reproducibility.",
        value: String(meta.strategy_version),
        category: "neutral",
      });
    }
  }

  const suspicious = reasonItems.filter((item) => item.category === "suspicious");
  const benign = reasonItems.filter((item) => item.category === "benign");
  const neutral = reasonItems.filter((item) => item.category === "neutral");

  return (
    <SectionCard title="Explanation" subtitle="Why the system produced this verdict">
      <div className="space-y-4">
        <ExplanationSection title="Suspicious signals" items={suspicious} tone="suspicious" />
        <ExplanationSection title="Benign supports" items={benign} tone="benign" />
        <ExplanationSection title="Other signals" items={neutral} tone="neutral" />
      </div>
    </SectionCard>
  );
}

function ExplanationSection({
  title,
  items,
  tone,
}: {
  title: string;
  items: ExplanationItem[];
  tone: "suspicious" | "benign" | "neutral";
}) {
  if (items.length === 0) {
    return (
      <div className="rounded-xl border border-white/10 bg-slate-950/50 p-3 text-xs text-slate-400">
        <span className="font-semibold text-slate-200">{title}:</span> none reported.
      </div>
    );
  }

  const toneClass =
    tone === "suspicious"
      ? "border-red-500/20 bg-red-500/5"
      : tone === "benign"
      ? "border-emerald-500/20 bg-emerald-500/5"
      : "border-white/10 bg-slate-950/50";

  return (
    <div className={`rounded-xl border p-3 ${toneClass}`}>
      <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-300">{title}</h3>
      <ul className="mt-2 space-y-2">
        {items.map((item, index) => (
          <li key={`${item.title}-${index}`} className="rounded-lg border border-white/10 bg-slate-950/70 p-3">
            <div className="text-sm font-semibold text-slate-100 break-all">{item.title}</div>
            <p className="mt-1 text-xs text-slate-300 leading-relaxed">{item.detail}</p>
            {item.value ? (
              <pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-all rounded-md bg-slate-900/80 p-2 text-[11px] text-slate-300">
                {item.value}
              </pre>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  );
}
