import { RiskLevel, VerdictLabel } from "@/lib/types";

type RiskBadgeProps = {
  label?: VerdictLabel;
  riskLevel?: RiskLevel;
  className?: string;
};

function styleFromLabel(label: VerdictLabel) {
  if (label === "phishing") {
    return "border-red-500/40 bg-red-500/10 text-red-200";
  }
  return "border-emerald-500/40 bg-emerald-500/10 text-emerald-200";
}

function styleFromRisk(riskLevel: RiskLevel) {
  if (riskLevel === "critical") return "border-red-500/40 bg-red-500/10 text-red-200";
  if (riskLevel === "high") return "border-orange-500/40 bg-orange-500/10 text-orange-200";
  if (riskLevel === "medium") return "border-amber-500/40 bg-amber-500/10 text-amber-200";
  return "border-emerald-500/40 bg-emerald-500/10 text-emerald-200";
}

export function RiskBadge({ label, riskLevel, className = "" }: RiskBadgeProps) {
  if (!label && !riskLevel) return null;
  const text = label ? label.toUpperCase() : riskLevel!.toUpperCase();
  const style = label ? styleFromLabel(label) : styleFromRisk(riskLevel!);

  return (
    <span
      className={`inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold tracking-wide ${style} ${className}`.trim()}
    >
      {text}
    </span>
  );
}
