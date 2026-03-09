"use client";

import { useMemo, useState } from "react";

type Reason = {
  feature: string;
  value: any;
  note: string;
};

type PredictResponse = {
  label: "phishing" | "legitimate";
  probability: number;
  url_score: number;
  domain_score?: number | null;
  email_score?: number | null;
  reasons: Reason[];
  context?: Record<string, any> | null;
  meta?: Record<string, any>;
};

function clampPct(x: number) {
  const v = Math.max(0, Math.min(1, x));
  return Math.round(v * 100);
}

function normalizeUrlInput(raw: string) {
  const s = (raw || "").trim();
  if (!s) return { normalized: "", error: "Please enter a URL." };

  // If user didn't provide a scheme, assume https://
  const hasScheme = /^[a-zA-Z][a-zA-Z0-9+\-.]*:\/\//.test(s);
  const candidate = hasScheme ? s : `https://${s}`;

  try {
    const u = new URL(candidate);

    // Basic sanity: must have a hostname
    if (!u.hostname) {
      return { normalized: "", error: "Invalid URL (missing hostname)." };
    }

    // Normalize host casing
    u.hostname = u.hostname.toLowerCase();

    // Remove default ports
    if (u.port === "80" && u.protocol === "http:") u.port = "";
    if (u.port === "443" && u.protocol === "https:") u.port = "";

    // Ensure path exists
    if (!u.pathname) u.pathname = "/";

    return { normalized: u.toString(), error: null };
  } catch {
    return { normalized: "", error: "Invalid URL format." };
  }
}


export default function Home() {
  const API_BASE =
    process.env.NEXT_PUBLIC_API_BASE?.trim() || "http://localhost:8000";

  const [url, setUrl] = useState("");
  const [enableExplain, setEnableExplain] = useState(true);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [result, setResult] = useState<PredictResponse | null>(null);
  const [normalizedPreview, setNormalizedPreview] = useState<string | null>(null);

  const pct = useMemo(
    () => (result ? clampPct(result.probability) : 0),
    [result]
  );

  async function onAnalyze() {
    setErr(null);
    setResult(null);
    const { normalized, error } = normalizeUrlInput(url);
    if (error) {
        setErr(error);
        return;
    }
    setNormalizedPreview(normalized);


    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/predict`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url: normalized,
          enable_context: false,
          enable_explain: enableExplain,
        }),
      });

      if (!res.ok) {
        const txt = await res.text();
        throw new Error(`Backend error: ${res.status} ${txt}`);
      }

      const data = (await res.json()) as PredictResponse;
      setResult(data);
    } catch (e: any) {
      setErr(e?.message ?? "Something went wrong");
    } finally {
      setLoading(false);
    }
  }
  
  const isPhishing = result?.label === "phishing";
  const verdictPill = isPhishing
    ? "bg-red-500/15 text-red-300 border border-red-500/20"
    : "bg-emerald-500/15 text-emerald-300 border border-emerald-500/20";

  return (
    <main className="relative min-h-screen overflow-hidden bg-slate-950 text-white">
      {/* Background: blurred glow blobs (combined from both codes) */}
      <div className="absolute inset-0 -z-10">
        <div className="absolute top-[-18%] left-[-12%] h-[520px] w-[520px] rounded-full bg-indigo-500/30 blur-[140px]" />
        <div className="absolute bottom-[-18%] right-[-12%] h-[520px] w-[520px] rounded-full bg-cyan-500/25 blur-[140px]" />
        <div className="absolute top-[30%] right-[15%] h-[360px] w-[360px] rounded-full bg-fuchsia-500/10 blur-[120px]" />
      </div>

      {/* Subtle grid overlay (use Code 2's slightly stronger look) */}
      <div className="pointer-events-none absolute inset-0 -z-10 opacity-[0.08]">
        <div className="h-full w-full bg-[linear-gradient(to_right,rgba(255,255,255,0.5)_1px,transparent_1px),linear-gradient(to_bottom,rgba(255,255,255,0.5)_1px,transparent_1px)] bg-[size:60px_60px]" />
      </div>

      <div className="mx-auto max-w-3xl px-6 py-12">
        {/* Header (combined messaging) */}
        <div className="mb-6">
          <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-200">
            <span className="h-2 w-2 rounded-full bg-emerald-400" />
            Backend connected • FastAPI + Next.js
          </div>

          <h1 className="mt-4 text-3xl font-semibold tracking-tight">
            Phishing URL Detector
          </h1>

          <p className="mt-2 text-slate-300">
            Paste a URL and get a risk verdict with reasons.
          </p>
        </div>

        {/* Input Card */}
        <div className="rounded-2xl border border-white/10 bg-white/10 p-8 shadow-2xl backdrop-blur-xl">
          <label className="block text-sm font-medium text-slate-200">
            URL
          </label>

          {/* LIGHT GLASS INPUT (from Code 1, includes placeholder fix) */}
          <input
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://login.example/login"
            className="
              mt-2 w-full rounded-xl
              border border-white/20
              bg-white/80
              px-4 py-3
              text-slate-900
              placeholder:text-slate-500
              outline-none
              backdrop-blur-md
              focus:border-indigo-400
              focus:ring-2 focus:ring-indigo-400/40
            "
          />
          {normalizedPreview && (
            <div className="mt-2 text-xs text-slate-300">
              Analyzing:&nbsp;
              <span className="font-mono text-slate-100">
                {normalizedPreview}
              </span>
            </div>
          )}

          <div className="mt-4 flex items-center gap-3">
            <input
              id="explain"
              type="checkbox"
              checked={enableExplain}
              onChange={(e) => setEnableExplain(e.target.checked)}
              className="h-4 w-4 accent-indigo-500"
            />
            <label htmlFor="explain" className="text-sm text-slate-200">
              Show reasons
            </label>
          </div>

          <button
            onClick={onAnalyze}
            disabled={loading}
            className="
              mt-6 w-full rounded-xl
              bg-indigo-500
              py-3 font-semibold
              text-white
              shadow-lg shadow-indigo-500/30
              hover:bg-indigo-400
              disabled:opacity-60
              disabled:cursor-not-allowed
              transition
            "
          >
            {loading ? "Analyzing..." : "Analyze"}
          </button>

          {err && (
            <div className="mt-4 rounded-xl border border-red-500/20 bg-red-500/10 p-3 text-sm text-red-200">
              {err}
            </div>
          )}
        </div>

        {/* Result Card */}
        {result && (
          <div className="mt-6 rounded-2xl border border-white/10 bg-white/10 p-8 shadow-2xl backdrop-blur-xl">
            <div className="flex items-start justify-between gap-4">
              <div>
                <div
                  className={`inline-flex items-center rounded-full px-4 py-1 text-sm font-semibold ${verdictPill}`}
                >
                  {result.label.toUpperCase()}
                </div>
                <p className="mt-2 text-sm text-slate-300">
                  Probability score is a confidence estimate (0–100%).
                </p>
              </div>

              <div className="text-right">
                <div className="text-4xl font-semibold">{pct}%</div>
                <div className="text-xs text-slate-400">risk score</div>
              </div>
            </div>

            {/* Progress bar (use Code 2’s nicer container/border) */}
            <div className="mt-4 h-3 w-full rounded-full bg-slate-900/70 overflow-hidden border border-white/5">
              <div
                className="h-full bg-white/90"
                style={{ width: `${pct}%` }}
              />
            </div>

            {result.reasons?.length > 0 && (
              <>
                <h2 className="mt-6 text-lg font-semibold">Reasons</h2>
                <ul className="mt-3 space-y-3">
                  {result.reasons.slice(0, 7).map((r, idx) => (
                    <li
                      key={idx}
                      className="rounded-xl border border-white/10 bg-slate-900/40 p-4"
                    >
                      <div className="text-sm font-semibold text-slate-100">
                        {r.feature}
                      </div>
                      <div className="mt-1 text-sm text-slate-300">
                        {r.note}
                      </div>
                      <div className="mt-2 text-xs text-slate-400">
                        value:{" "}
                        <span className="font-mono text-slate-200">
                          {typeof r.value === "object"
                            ? JSON.stringify(r.value)
                            : String(r.value)}
                        </span>
                      </div>
                    </li>
                  ))}
                </ul>
              </>
            )}

            <div className="mt-6 text-xs text-slate-400">
              engine:{" "}
              <span className="text-slate-200">
                {result.meta?.engine ?? "unknown"}
              </span>
            </div>
          </div>
        )}

        {/* Footer note (from Code 2) */}
        <div className="mt-10 text-center text-xs text-slate-500">
          Tip: Try a suspicious URL like{" "}
          <span className="font-mono text-slate-300">
            http://secure-login.verify-account.update-now.xyz/login
          </span>
        </div>
      </div>
    </main>
  );
}
