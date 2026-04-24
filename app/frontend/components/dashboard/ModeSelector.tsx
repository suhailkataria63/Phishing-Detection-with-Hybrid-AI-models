import { DetectMode } from "@/lib/types";

const MODE_OPTIONS: Array<{ key: DetectMode; label: string; hint: string }> = [
  { key: "url", label: "URL Detection", hint: "Analyze standalone URLs" },
  { key: "email", label: "Email Detection", hint: "Analyze message intent" },
  { key: "joint", label: "Joint Detection", hint: "Fuse email + URL signals" },
];

type ModeSelectorProps = {
  mode: DetectMode;
  onChange: (next: DetectMode) => void;
};

export function ModeSelector({ mode, onChange }: ModeSelectorProps) {
  return (
    <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
      {MODE_OPTIONS.map((option) => {
        const active = option.key === mode;
        return (
          <button
            key={option.key}
            type="button"
            onClick={() => onChange(option.key)}
            className={`rounded-xl border px-4 py-3 text-left transition ${
              active
                ? "border-indigo-400/60 bg-indigo-500/15 text-indigo-100"
                : "border-white/10 bg-slate-900/60 text-slate-300 hover:border-white/20 hover:bg-slate-900"
            }`}
          >
            <div className="text-sm font-semibold">{option.label}</div>
            <div className="mt-1 text-xs text-slate-400">{option.hint}</div>
          </button>
        );
      })}
    </div>
  );
}
