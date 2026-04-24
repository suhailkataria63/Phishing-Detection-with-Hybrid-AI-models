import { SectionCard } from "@/components/shared/SectionCard";
import { recommendationFromScore } from "@/lib/format";
import { UnifiedResult } from "@/lib/types";

type RecommendationCardProps = {
  result: UnifiedResult;
};

export function RecommendationCard({ result }: RecommendationCardProps) {
  const recommendation = recommendationFromScore(result.score, result.riskLevel);

  return (
    <SectionCard title="Analyst Recommendation" subtitle="Operational action guidance">
      <div className="rounded-xl border border-white/10 bg-slate-950/70 p-4">
        <div className="text-sm font-semibold text-slate-100">{recommendation.title}</div>
        <p className="mt-2 text-sm text-slate-300 leading-relaxed">{recommendation.description}</p>
      </div>
    </SectionCard>
  );
}
