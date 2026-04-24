import { SectionCard } from "@/components/shared/SectionCard";
import { RiskBadge } from "@/components/shared/RiskBadge";
import { ScoreBar } from "@/components/shared/ScoreBar";
import { toPct } from "@/lib/format";
import { UnifiedResult } from "@/lib/types";

type SummaryCardProps = {
  result: UnifiedResult;
};

export function SummaryCard({ result }: SummaryCardProps) {
  const scorePct = toPct(result.score);

  return (
    <SectionCard
      title="Detection Summary"
      subtitle="Primary decision, confidence, and operating context"
      rightSlot={<RiskBadge label={result.label} />}
    >
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <Metric label="Confidence" value={`${scorePct}%`} />
          <Metric label="Risk level" value={result.riskLevel.toUpperCase()} />
          <Metric label="Strategy" value={result.strategy || "n/a"} mono />
          <Metric label="Operating mode" value={result.operatingMode || "balanced"} mono />
        </div>

        <ScoreBar value={result.score} label="Risk score" />

        <div className="text-xs text-slate-400">
          Threshold: <span className="text-slate-200">{(result.resolvedThreshold ?? 0.5).toFixed(2)}</span>
        </div>
      </div>
    </SectionCard>
  );
}

function Metric({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="rounded-xl border border-white/10 bg-slate-950/70 p-3">
      <div className="text-[11px] uppercase tracking-wide text-slate-400">{label}</div>
      <div className={`mt-1 text-sm font-semibold text-slate-100 ${mono ? "font-mono" : ""}`}>{value}</div>
    </div>
  );
}
