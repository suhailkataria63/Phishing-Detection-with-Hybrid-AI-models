import { RiskBadge } from "@/components/shared/RiskBadge";
import { ScoreBar } from "@/components/shared/ScoreBar";
import { shortExplain, toPct } from "@/lib/format";
import { BatchAnalyzedRow, JointResponse } from "@/lib/types";

type CaseDetailDrawerProps = {
  row: BatchAnalyzedRow | null;
  onClose: () => void;
};

export function CaseDetailDrawer({ row, onClose }: CaseDetailDrawerProps) {
  if (!row) return null;

  const output = row.output;
  const reasons = (output.reasons || []).slice(0, 12);
  const joint = row.mode === "joint" ? (output as JointResponse) : null;

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm">
      <div className="absolute inset-y-0 right-0 h-full w-full max-w-2xl overflow-y-auto border-l border-white/10 bg-slate-950 p-5 shadow-2xl">
        <div className="mb-4 flex items-start justify-between gap-4">
          <div>
            <h3 className="text-lg font-semibold text-slate-100">Case Detail</h3>
            <p className="mt-1 text-xs text-slate-400">Row {row.rowIndex} · {row.caseId}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-white/15 bg-slate-900 px-3 py-2 text-xs text-slate-200"
          >
            Close
          </button>
        </div>

        <div className="space-y-4">
          <section className="rounded-xl border border-white/10 bg-slate-900/70 p-4">
            <div className="flex items-center justify-between">
              <RiskBadge label={row.label} />
              <div className="text-sm font-semibold text-slate-100">{toPct(row.score)}%</div>
            </div>
            <div className="mt-3">
              <ScoreBar value={row.score} compact />
            </div>
            <p className="mt-3 text-sm text-slate-300">{row.recommendation}</p>
          </section>

          <section className="rounded-xl border border-white/10 bg-slate-900/70 p-4">
            <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-400">Input context</h4>
            {row.input.subject ? <p className="mt-2 text-sm text-slate-200"><span className="font-semibold">Subject:</span> {row.input.subject}</p> : null}
            {row.input.sender ? <p className="mt-2 text-sm text-slate-200"><span className="font-semibold">Sender:</span> {row.input.sender}</p> : null}
            {row.input.body ? (
              <p className="mt-2 whitespace-pre-wrap text-sm text-slate-300">
                <span className="font-semibold text-slate-200">Body preview:</span>{" "}
                {row.input.body.slice(0, 600)}
                {row.input.body.length > 600 ? "..." : ""}
              </p>
            ) : null}
          </section>

          {row.extractedUrls.length > 0 ? (
            <section className="rounded-xl border border-white/10 bg-slate-900/70 p-4">
              <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-400">Extracted URLs</h4>
              <ul className="mt-2 space-y-2">
                {row.extractedUrls.slice(0, 12).map((url, idx) => (
                  <li key={`${url}-${idx}`} className="rounded-lg border border-white/10 bg-slate-950/70 p-2 text-xs font-mono text-slate-200 break-all">
                    {url}
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          {joint?.url_results?.length ? (
            <section className="rounded-xl border border-white/10 bg-slate-900/70 p-4">
              <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-400">Per-URL indicators</h4>
              <ul className="mt-2 space-y-2">
                {joint.url_results.map((urlResult, idx) => (
                  <li key={`${urlResult.url}-${idx}`} className="rounded-lg border border-white/10 bg-slate-950/70 p-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="text-xs font-mono text-slate-300 break-all">{urlResult.url}</span>
                      <RiskBadge label={urlResult.label} />
                    </div>
                    <div className="mt-2">
                      <ScoreBar value={urlResult.score} compact />
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          <section className="rounded-xl border border-white/10 bg-slate-900/70 p-4">
            <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-400">Reasoning summary</h4>
            {reasons.length === 0 ? (
              <p className="mt-2 text-sm text-slate-400">No explanation metadata returned.</p>
            ) : (
              <ul className="mt-2 space-y-2">
                {reasons.map((reason, idx) => (
                  <li key={`${reason.feature}-${idx}`} className="rounded-lg border border-white/10 bg-slate-950/70 p-3">
                    <div className="text-sm font-semibold text-slate-100">{reason.feature}</div>
                    <p className="mt-1 text-xs text-slate-300">{reason.note}</p>
                    <pre className="mt-2 whitespace-pre-wrap break-all rounded bg-slate-900 p-2 text-[11px] text-slate-400">
                      {shortExplain(reason.value)}
                    </pre>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
