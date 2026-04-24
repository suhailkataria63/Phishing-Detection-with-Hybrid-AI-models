import { DetectMode, JointStrategy, OperatingMode } from "@/lib/types";

type BatchUploadPanelProps = {
  mode: DetectMode;
  operatingMode: OperatingMode;
  strategy: JointStrategy;
  threshold: string;
  loading: boolean;
  rowCount: number;
  onModeChange: (value: DetectMode) => void;
  onOperatingModeChange: (value: OperatingMode) => void;
  onStrategyChange: (value: JointStrategy) => void;
  onThresholdChange: (value: string) => void;
  onFileSelect: (file: File) => void;
  onRun: () => void;
};

export function BatchUploadPanel({
  mode,
  operatingMode,
  strategy,
  threshold,
  loading,
  rowCount,
  onModeChange,
  onOperatingModeChange,
  onStrategyChange,
  onThresholdChange,
  onFileSelect,
  onRun,
}: BatchUploadPanelProps) {
  return (
    <section className="rounded-2xl border border-white/10 bg-slate-900/70 p-5 shadow-[0_8px_30px_rgba(8,18,35,0.35)] backdrop-blur">
      <div className="mb-4 flex items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-semibold text-slate-100">Batch Analysis Workspace</h2>
          <p className="mt-1 text-xs text-slate-400">
            Upload CSV, choose mode/strategy, and process rows with analyst-friendly outputs.
          </p>
        </div>
        <div className="rounded-lg border border-white/10 bg-slate-950/70 px-3 py-2 text-xs text-slate-300">
          Rows loaded: <span className="font-semibold text-slate-100">{rowCount}</span>
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
        <label className="space-y-2 rounded-xl border border-white/10 bg-slate-950/70 p-3 text-xs text-slate-300">
          Mode
          <select
            value={mode}
            onChange={(e) => onModeChange(e.target.value as DetectMode)}
            className="w-full rounded-lg border border-white/10 bg-slate-900 px-2 py-2 text-sm text-slate-100 outline-none"
          >
            <option value="url">URL Detection</option>
            <option value="email">Email Detection</option>
            <option value="joint">Joint Detection</option>
          </select>
        </label>

        <label className="space-y-2 rounded-xl border border-white/10 bg-slate-950/70 p-3 text-xs text-slate-300">
          Operating mode
          <select
            value={operatingMode}
            onChange={(e) => onOperatingModeChange(e.target.value as OperatingMode)}
            className="w-full rounded-lg border border-white/10 bg-slate-900 px-2 py-2 text-sm text-slate-100 outline-none"
          >
            <option value="soc">SOC</option>
            <option value="balanced">Balanced</option>
            <option value="high_confidence">High confidence</option>
          </select>
        </label>

        <label className="space-y-2 rounded-xl border border-white/10 bg-slate-950/70 p-3 text-xs text-slate-300">
          Joint strategy
          <select
            value={strategy}
            onChange={(e) => onStrategyChange(e.target.value as JointStrategy)}
            disabled={mode !== "joint"}
            className="w-full rounded-lg border border-white/10 bg-slate-900 px-2 py-2 text-sm text-slate-100 outline-none disabled:opacity-50"
          >
            <option value="optimized">Optimized</option>
            <option value="baseline">Baseline</option>
          </select>
        </label>

        <label className="space-y-2 rounded-xl border border-white/10 bg-slate-950/70 p-3 text-xs text-slate-300">
          Threshold override
          <input
            value={threshold}
            onChange={(e) => onThresholdChange(e.target.value)}
            placeholder="(optional) e.g. 0.50"
            className="w-full rounded-lg border border-white/10 bg-slate-900 px-2 py-2 text-sm text-slate-100 outline-none"
          />
        </label>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <label className="inline-flex cursor-pointer items-center gap-2 rounded-xl border border-white/15 bg-slate-950/70 px-3 py-2 text-sm text-slate-200">
          <input
            type="file"
            accept=".csv"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) onFileSelect(file);
            }}
          />
          Upload CSV
        </label>

        <button
          type="button"
          onClick={onRun}
          disabled={loading || rowCount === 0}
          className="rounded-xl border border-indigo-400/30 bg-indigo-500/20 px-4 py-2 text-sm font-semibold text-indigo-100 transition hover:bg-indigo-500/30 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {loading ? "Running batch..." : "Run analysis"}
        </button>
      </div>

      <p className="mt-3 text-xs text-slate-500">
        CSV columns supported: `subject`, `body`, `sender`, `url`, `urls`, optional `case_id`, optional expected label columns.
      </p>
    </section>
  );
}
