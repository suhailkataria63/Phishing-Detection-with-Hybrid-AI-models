import { SectionCard } from "@/components/shared/SectionCard";
import { ScoreBar } from "@/components/shared/ScoreBar";
import { JointResponse, UnifiedResult } from "@/lib/types";

type SignalBreakdownCardProps = {
  result: UnifiedResult;
};

export function SignalBreakdownCard({ result }: SignalBreakdownCardProps) {
  const raw = result.raw;

  if (result.mode === "joint") {
    const joint = raw as JointResponse;
    return (
      <SectionCard title="Signal Breakdown" subtitle="Channel-level risk contributions">
        <div className="space-y-4">
          <ScoreBar value={joint.email_score} label="Email channel score" compact />
          <ScoreBar value={joint.url_score} label="URL channel score (max)" compact />
          <ScoreBar value={joint.final_score} label="Final joint score" compact />
          <div className="grid grid-cols-2 gap-3 text-xs text-slate-300 md:grid-cols-3">
            <Stat label="URLs analyzed" value={String(joint.analyzed_url_count)} />
            <Stat label="Risky URLs" value={String(joint.risky_url_count)} />
            <Stat label="Extracted URLs" value={String(joint.extracted_urls?.length || 0)} />
          </div>
        </div>
      </SectionCard>
    );
  }

  return (
    <SectionCard title="Signal Breakdown" subtitle="Model confidence profile">
      <div className="space-y-4">
        <ScoreBar value={result.score} label="Primary model score" compact />
      </div>
    </SectionCard>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-white/10 bg-slate-950/70 p-3">
      <div className="text-[11px] uppercase tracking-wide text-slate-400">{label}</div>
      <div className="mt-1 text-sm font-semibold text-slate-100">{value}</div>
    </div>
  );
}
