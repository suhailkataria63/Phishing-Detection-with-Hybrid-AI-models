import { DetectMode, DetectorInputs, JointStrategy, OperatingMode } from "@/lib/types";
import { ModeSelector } from "@/components/dashboard/ModeSelector";

type DetectionFormProps = {
  mode: DetectMode;
  inputs: DetectorInputs;
  enableExplain: boolean;
  loading: boolean;
  operatingMode: OperatingMode;
  jointStrategy: JointStrategy;
  normalizedPreview: string | null;
  error: string | null;
  onModeChange: (next: DetectMode) => void;
  onInputChange: <K extends keyof DetectorInputs>(key: K, value: DetectorInputs[K]) => void;
  onOperatingModeChange: (mode: OperatingMode) => void;
  onJointStrategyChange: (strategy: JointStrategy) => void;
  onEnableExplainChange: (value: boolean) => void;
  onSubmit: () => void;
};

const OPERATING_OPTIONS: Array<{ key: OperatingMode; label: string; hint: string }> = [
  { key: "soc", label: "SOC", hint: "High recall" },
  { key: "balanced", label: "Balanced", hint: "Default" },
  { key: "high_confidence", label: "High confidence", hint: "High precision" },
];

export function DetectionForm({
  mode,
  inputs,
  enableExplain,
  loading,
  operatingMode,
  jointStrategy,
  normalizedPreview,
  error,
  onModeChange,
  onInputChange,
  onOperatingModeChange,
  onJointStrategyChange,
  onEnableExplainChange,
  onSubmit,
}: DetectionFormProps) {
  return (
    <div className="space-y-5">
      <ModeSelector mode={mode} onChange={onModeChange} />

      <div className="grid gap-3 md:grid-cols-2">
        <label className="space-y-2 rounded-xl border border-white/10 bg-slate-900/60 p-3">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Operating mode</span>
          <select
            value={operatingMode}
            onChange={(e) => onOperatingModeChange(e.target.value as OperatingMode)}
            className="w-full rounded-lg border border-white/10 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none focus:border-indigo-400/50"
          >
            {OPERATING_OPTIONS.map((option) => (
              <option key={option.key} value={option.key}>
                {option.label} - {option.hint}
              </option>
            ))}
          </select>
        </label>

        <label className="space-y-2 rounded-xl border border-white/10 bg-slate-900/60 p-3">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Joint strategy</span>
          <select
            value={jointStrategy}
            onChange={(e) => onJointStrategyChange(e.target.value as JointStrategy)}
            disabled={mode !== "joint"}
            className="w-full rounded-lg border border-white/10 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none focus:border-indigo-400/50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <option value="optimized">Optimized (rule-assisted)</option>
            <option value="baseline">Baseline</option>
          </select>
        </label>
      </div>

      {mode === "url" ? (
        <div className="space-y-2">
          <label className="text-sm font-medium text-slate-200">URL</label>
          <input
            value={inputs.url}
            onChange={(e) => onInputChange("url", e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                if (!loading) onSubmit();
              }
            }}
            placeholder="example.com/login or https://example.com/reset"
            className="w-full rounded-xl border border-white/10 bg-slate-950 px-4 py-3 text-sm text-slate-100 outline-none placeholder:text-slate-500 focus:border-indigo-400/50"
          />
          {normalizedPreview ? (
            <p className="text-xs text-slate-400">
              normalized URL: <span className="font-mono text-slate-200 break-all">{normalizedPreview}</span>
            </p>
          ) : null}
        </div>
      ) : (
        <>
          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-200">Email Subject</label>
            <input
              value={inputs.subject}
              onChange={(e) => onInputChange("subject", e.target.value)}
              placeholder="Action required: verify your account"
              className="w-full rounded-xl border border-white/10 bg-slate-950 px-4 py-3 text-sm text-slate-100 outline-none placeholder:text-slate-500 focus:border-indigo-400/50"
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-200">Email Body</label>
            <textarea
              value={inputs.body}
              onChange={(e) => onInputChange("body", e.target.value)}
              rows={8}
              placeholder="Paste full email body for better context..."
              className="w-full rounded-xl border border-white/10 bg-slate-950 px-4 py-3 text-sm text-slate-100 outline-none placeholder:text-slate-500 focus:border-indigo-400/50"
            />
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-slate-200">Sender (optional)</label>
            <input
              value={inputs.sender}
              onChange={(e) => onInputChange("sender", e.target.value)}
              placeholder="alerts@company.com"
              className="w-full rounded-xl border border-white/10 bg-slate-950 px-4 py-3 text-sm text-slate-100 outline-none placeholder:text-slate-500 focus:border-indigo-400/50"
            />
          </div>

          {mode === "joint" ? (
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-200">Manual URLs (optional)</label>
              <textarea
                value={inputs.jointUrlsRaw}
                onChange={(e) => onInputChange("jointUrlsRaw", e.target.value)}
                rows={3}
                placeholder="Add comma/newline-separated URLs if not present in body"
                className="w-full rounded-xl border border-white/10 bg-slate-950 px-4 py-3 text-sm text-slate-100 outline-none placeholder:text-slate-500 focus:border-indigo-400/50"
              />
            </div>
          ) : null}
        </>
      )}

      <label className="inline-flex items-center gap-3 text-sm text-slate-300">
        <input
          type="checkbox"
          checked={enableExplain}
          onChange={(e) => onEnableExplainChange(e.target.checked)}
          className="h-4 w-4 rounded border-white/20 bg-slate-900 accent-indigo-400"
        />
        Include explanation metadata
      </label>

      <button
        type="button"
        onClick={onSubmit}
        disabled={loading}
        className="w-full rounded-xl border border-indigo-400/30 bg-indigo-500/20 px-4 py-3 text-sm font-semibold text-indigo-100 transition hover:bg-indigo-500/30 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {loading ? "Running analysis..." : "Analyze"}
      </button>

      {error ? <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">{error}</div> : null}
    </div>
  );
}
