import { toPct } from "@/lib/format";

type ScoreBarProps = {
  value: number;
  label?: string;
  compact?: boolean;
};

function fillClass(value: number): string {
  const pct = toPct(value);
  if (pct >= 80) return "bg-red-400";
  if (pct >= 60) return "bg-orange-400";
  if (pct >= 40) return "bg-amber-400";
  return "bg-emerald-400";
}

export function ScoreBar({ value, label, compact = false }: ScoreBarProps) {
  const pct = toPct(value);
  const height = compact ? "h-2" : "h-3";

  return (
    <div className="space-y-2">
      {label ? (
        <div className="flex items-center justify-between text-xs text-slate-300">
          <span>{label}</span>
          <span className="font-semibold text-slate-100">{pct}%</span>
        </div>
      ) : null}
      <div className={`w-full overflow-hidden rounded-full border border-white/10 bg-slate-900/80 ${height}`}>
        <div className={`h-full transition-all ${fillClass(value)}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
