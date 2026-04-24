import { useMemo, useState } from "react";

import { BatchAnalyzedRow } from "@/lib/types";
import { RiskBadge } from "@/components/shared/RiskBadge";
import { toPct } from "@/lib/format";

type BatchResultsTableProps = {
  rows: BatchAnalyzedRow[];
  onSelectRow: (row: BatchAnalyzedRow) => void;
  onExport: () => void;
};

type SortKey = "score" | "row";

export function BatchResultsTable({ rows, onSelectRow, onExport }: BatchResultsTableProps) {
  const [sortKey, setSortKey] = useState<SortKey>("score");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [verdictFilter, setVerdictFilter] = useState<"all" | "phishing" | "legitimate">("all");
  const [recommendationFilter, setRecommendationFilter] = useState<"all" | "likely_safe" | "review_carefully" | "investigate_immediately" | "high_risk_candidate">("all");

  const visible = useMemo(() => {
    const filtered = rows.filter((row) => {
      if (verdictFilter !== "all" && row.label !== verdictFilter) return false;
      if (recommendationFilter !== "all" && row.recommendationCode !== recommendationFilter) return false;
      return true;
    });

    const sorted = [...filtered].sort((a, b) => {
      const sign = sortDir === "asc" ? 1 : -1;
      if (sortKey === "row") return (a.rowIndex - b.rowIndex) * sign;
      return (a.score - b.score) * sign;
    });

    return sorted;
  }, [rows, verdictFilter, recommendationFilter, sortDir, sortKey]);

  return (
    <section className="rounded-2xl border border-white/10 bg-slate-900/70 p-5 shadow-[0_8px_30px_rgba(8,18,35,0.35)] backdrop-blur">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-base font-semibold text-slate-100">Batch Results</h2>
        <button
          type="button"
          onClick={onExport}
          disabled={rows.length === 0}
          className="rounded-xl border border-white/15 bg-slate-950/70 px-3 py-2 text-xs font-semibold text-slate-200 transition hover:border-white/30 disabled:opacity-40"
        >
          Export CSV
        </button>
      </div>

      <div className="mb-4 grid gap-3 md:grid-cols-4">
        <select
          value={sortKey}
          onChange={(e) => setSortKey(e.target.value as SortKey)}
          className="rounded-lg border border-white/10 bg-slate-950 px-3 py-2 text-xs text-slate-200"
        >
          <option value="score">Sort by score</option>
          <option value="row">Sort by row index</option>
        </select>

        <select
          value={sortDir}
          onChange={(e) => setSortDir(e.target.value as "asc" | "desc")}
          className="rounded-lg border border-white/10 bg-slate-950 px-3 py-2 text-xs text-slate-200"
        >
          <option value="desc">Descending</option>
          <option value="asc">Ascending</option>
        </select>

        <select
          value={verdictFilter}
          onChange={(e) => setVerdictFilter(e.target.value as "all" | "phishing" | "legitimate")}
          className="rounded-lg border border-white/10 bg-slate-950 px-3 py-2 text-xs text-slate-200"
        >
          <option value="all">All verdicts</option>
          <option value="phishing">Phishing</option>
          <option value="legitimate">Legitimate</option>
        </select>

        <select
          value={recommendationFilter}
          onChange={(e) =>
            setRecommendationFilter(
              e.target.value as "all" | "likely_safe" | "review_carefully" | "investigate_immediately" | "high_risk_candidate"
            )
          }
          className="rounded-lg border border-white/10 bg-slate-950 px-3 py-2 text-xs text-slate-200"
        >
          <option value="all">All recommendations</option>
          <option value="likely_safe">Likely safe</option>
          <option value="review_carefully">Review carefully</option>
          <option value="investigate_immediately">Investigate immediately</option>
          <option value="high_risk_candidate">High-risk candidate</option>
        </select>
      </div>

      <div className="overflow-x-auto rounded-xl border border-white/10">
        <table className="min-w-full divide-y divide-white/10 text-sm">
          <thead className="bg-slate-950/70 text-left text-xs uppercase tracking-wide text-slate-400">
            <tr>
              <th className="px-3 py-3">Row</th>
              <th className="px-3 py-3">Case</th>
              <th className="px-3 py-3">Verdict</th>
              <th className="px-3 py-3">Score</th>
              <th className="px-3 py-3">Recommendation</th>
              <th className="px-3 py-3">Reason summary</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/10 bg-slate-900/60 text-slate-200">
            {visible.map((row) => (
              <tr
                key={`${row.rowIndex}-${row.caseId}`}
                className="cursor-pointer hover:bg-slate-900"
                onClick={() => onSelectRow(row)}
              >
                <td className="px-3 py-3 text-xs text-slate-400">{row.rowIndex}</td>
                <td className="px-3 py-3 text-xs font-mono text-slate-300">{row.caseId}</td>
                <td className="px-3 py-3">
                  <RiskBadge label={row.label} />
                </td>
                <td className="px-3 py-3 font-semibold text-slate-100">{toPct(row.score)}%</td>
                <td className="px-3 py-3 text-xs text-slate-300">{row.recommendation}</td>
                <td className="max-w-[420px] truncate px-3 py-3 text-xs text-slate-400">{row.explanationSummary}</td>
              </tr>
            ))}
            {visible.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-3 py-6 text-center text-sm text-slate-400">
                  No rows match current filters.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </section>
  );
}
