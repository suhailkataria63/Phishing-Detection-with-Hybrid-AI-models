"use client";

import { useMemo, useState } from "react";

type DetectMode = "url" | "email" | "joint";

type Reason = {
  feature: string;
  value: unknown;
  note: string;
};

type UrlResponse = {
  label: "phishing" | "legitimate";
  probability: number;
  url_score: number;
  reasons: Reason[];
  meta?: Record<string, unknown>;
};

type EmailResponse = {
  label: "phishing" | "legitimate";
  probability: number;
  email_score: number;
  risk_level: "low" | "medium" | "high" | "critical";
  suggested_action: string;
  reasons: Reason[];
  context?: Record<string, unknown>;
  meta?: Record<string, unknown>;
};

type UrlAssessment = {
  url: string;
  label: "phishing" | "legitimate";
  score: number;
  reasons: Reason[];
};

type JointResponse = {
  final_label: "phishing" | "legitimate";
  final_score: number;
  risk_level: "low" | "medium" | "high" | "critical";
  email_label: "phishing" | "legitimate";
  email_score: number;
  url_score: number;
  analyzed_url_count: number;
  risky_url_count: number;
  extracted_urls: string[];
  url_results: UrlAssessment[];
  reasons: Reason[];
  context?: Record<string, unknown>;
  meta?: Record<string, unknown>;
};

function clampPct(x: number) {
  const v = Math.max(0, Math.min(1, x));
  return Math.round(v * 100);
}

function normalizeUrlInput(raw: string) {
  const s = (raw || "").trim();
  if (!s) return { normalized: "", error: "Please enter a URL." };

  const hasScheme = /^[a-zA-Z][a-zA-Z0-9+\-.]*:\/\//.test(s);
  const candidate = hasScheme ? s : `https://${s}`;

  try {
    const u = new URL(candidate);
    if (!u.hostname) {
      return { normalized: "", error: "Invalid URL (missing hostname)." };
    }
    u.hostname = u.hostname.toLowerCase();
    if (u.port === "80" && u.protocol === "http:") u.port = "";
    if (u.port === "443" && u.protocol === "https:") u.port = "";
    if (!u.pathname) u.pathname = "/";
    return { normalized: u.toString(), error: null };
  } catch {
    return { normalized: "", error: "Invalid URL format." };
  }
}

function parseUrlList(raw: string): string[] {
  return Array.from(
    new Set(
      (raw || "")
        .split(/[\n,\s]+/)
        .map((s) => s.trim())
        .filter((s) => s.length >= 6)
    )
  );
}

function riskChipClasses(label: "phishing" | "legitimate") {
  return label === "phishing"
    ? "bg-red-500/15 text-red-300 border border-red-500/20"
    : "bg-emerald-500/15 text-emerald-300 border border-emerald-500/20";
}

function riskLevelClasses(level: string) {
  if (level === "critical") return "text-red-300";
  if (level === "high") return "text-orange-300";
  if (level === "medium") return "text-amber-300";
  return "text-emerald-300";
}

function formatReasonValue(value: unknown): string {
  if (value === null || value === undefined) return String(value);
  if (typeof value === "object") {
    try {
      return JSON.stringify(value, null, 2);
    } catch {
      return String(value);
    }
  }
  return String(value);
}

export default function Home() {
  const API_BASE = process.env.NEXT_PUBLIC_API_BASE?.trim() || "http://localhost:8000";

  const [mode, setMode] = useState<DetectMode>("url");
  const [enableExplain, setEnableExplain] = useState(true);

  const [url, setUrl] = useState("");
  const [normalizedPreview, setNormalizedPreview] = useState<string | null>(null);

  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [sender, setSender] = useState("");
  const [jointUrlsRaw, setJointUrlsRaw] = useState("");

  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const [urlResult, setUrlResult] = useState<UrlResponse | null>(null);
  const [emailResult, setEmailResult] = useState<EmailResponse | null>(null);
  const [jointResult, setJointResult] = useState<JointResponse | null>(null);

  const activeScore = useMemo(() => {
    if (mode === "url" && urlResult) return urlResult.probability;
    if (mode === "email" && emailResult) return emailResult.probability;
    if (mode === "joint" && jointResult) return jointResult.final_score;
    return 0;
  }, [mode, urlResult, emailResult, jointResult]);

  const pct = clampPct(activeScore);

  async function onAnalyze() {
    setErr(null);
    setUrlResult(null);
    setEmailResult(null);
    setJointResult(null);

    setLoading(true);
    try {
      if (mode === "url") {
        const { normalized, error } = normalizeUrlInput(url);
        if (error) {
          setErr(error);
          setLoading(false);
          return;
        }
        setNormalizedPreview(normalized);

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
        const data = (await res.json()) as UrlResponse;
        setUrlResult(data);
      }

      if (mode === "email") {
        if (!subject.trim() && !body.trim()) {
          setErr("Please provide at least subject or body.");
          setLoading(false);
          return;
        }

        const res = await fetch(`${API_BASE}/detect/email`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            subject,
            body,
            sender,
            threshold: 0.5,
            enable_explain: enableExplain,
          }),
        });
        if (!res.ok) {
          const txt = await res.text();
          throw new Error(`Backend error: ${res.status} ${txt}`);
        }
        const data = (await res.json()) as EmailResponse;
        setEmailResult(data);
      }

      if (mode === "joint") {
        if (!subject.trim() && !body.trim() && !jointUrlsRaw.trim()) {
          setErr("Provide email content and/or URLs for joint analysis.");
          setLoading(false);
          return;
        }

        const manualUrls = parseUrlList(jointUrlsRaw);
        const res = await fetch(`${API_BASE}/detect/joint`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            subject,
            body,
            sender,
            urls: manualUrls,
            threshold: 0.5,
            enable_explain: enableExplain,
          }),
        });
        if (!res.ok) {
          const txt = await res.text();
          throw new Error(`Backend error: ${res.status} ${txt}`);
        }
        const data = (await res.json()) as JointResponse;
        setJointResult(data);
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Something went wrong";
      setErr(msg);
    } finally {
      setLoading(false);
    }
  }

  const primaryLabel =
    mode === "url"
      ? urlResult?.label
      : mode === "email"
      ? emailResult?.label
      : jointResult?.final_label;

  return (
    <main className="relative min-h-screen overflow-hidden bg-slate-950 text-white">
      <div className="absolute inset-0 -z-10">
        <div className="absolute top-[-18%] left-[-12%] h-[520px] w-[520px] rounded-full bg-indigo-500/30 blur-[140px]" />
        <div className="absolute bottom-[-18%] right-[-12%] h-[520px] w-[520px] rounded-full bg-cyan-500/25 blur-[140px]" />
        <div className="absolute top-[30%] right-[15%] h-[360px] w-[360px] rounded-full bg-fuchsia-500/10 blur-[120px]" />
      </div>

      <div className="pointer-events-none absolute inset-0 -z-10 opacity-[0.08]">
        <div className="h-full w-full bg-[linear-gradient(to_right,rgba(255,255,255,0.5)_1px,transparent_1px),linear-gradient(to_bottom,rgba(255,255,255,0.5)_1px,transparent_1px)] bg-[size:60px_60px]" />
      </div>

      <div className="mx-auto max-w-4xl px-6 py-12">
        <div className="mb-6">
          <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-200">
            <span className="h-2 w-2 rounded-full bg-emerald-400" />
            Backend connected • FastAPI + Next.js
          </div>

          <h1 className="mt-4 text-3xl font-semibold tracking-tight">Phishing Detection Console</h1>
          <p className="mt-2 text-slate-300">
            Analyze URL-only, email-only, or combined email + URL signals in one workflow.
          </p>
        </div>

        <div className="rounded-2xl border border-white/10 bg-white/10 p-8 shadow-2xl backdrop-blur-xl">
          <div className="mb-6 grid grid-cols-1 gap-2 sm:grid-cols-3">
            {([
              ["url", "URL Detection"],
              ["email", "Email Detection"],
              ["joint", "Joint Detection"],
            ] as const).map(([key, label]) => {
              const active = mode === key;
              return (
                <button
                  key={key}
                  onClick={() => setMode(key)}
                  className={`rounded-xl border px-4 py-2 text-sm font-semibold transition ${
                    active
                      ? "border-indigo-400 bg-indigo-500/20 text-indigo-100"
                      : "border-white/15 bg-white/5 text-slate-200 hover:bg-white/10"
                  }`}
                >
                  {label}
                </button>
              );
            })}
          </div>

          {mode === "url" && (
            <div>
              <label className="block text-sm font-medium text-slate-200">URL</label>
              <input
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    if (!loading) {
                      void onAnalyze();
                    }
                  }
                }}
                placeholder="https://login.example/login"
                className="mt-2 w-full rounded-xl border border-white/20 bg-white/80 px-4 py-3 text-slate-900 placeholder:text-slate-500 outline-none backdrop-blur-md focus:border-indigo-400 focus:ring-2 focus:ring-indigo-400/40"
              />
              {normalizedPreview && (
                <div className="mt-2 text-xs text-slate-300">
                  Analyzing: <span className="font-mono text-slate-100">{normalizedPreview}</span>
                </div>
              )}
            </div>
          )}

          {(mode === "email" || mode === "joint") && (
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-200">Email Subject</label>
                <input
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                  placeholder="Security alert: verify your account"
                  className="mt-2 w-full rounded-xl border border-white/20 bg-white/80 px-4 py-3 text-slate-900 placeholder:text-slate-500 outline-none backdrop-blur-md focus:border-indigo-400 focus:ring-2 focus:ring-indigo-400/40"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-200">Email Body</label>
                <textarea
                  value={body}
                  onChange={(e) => setBody(e.target.value)}
                  placeholder="Paste the email body here..."
                  rows={7}
                  className="mt-2 w-full rounded-xl border border-white/20 bg-white/80 px-4 py-3 text-slate-900 placeholder:text-slate-500 outline-none backdrop-blur-md focus:border-indigo-400 focus:ring-2 focus:ring-indigo-400/40"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-200">Sender (optional)</label>
                <input
                  value={sender}
                  onChange={(e) => setSender(e.target.value)}
                  placeholder="alerts@example.com"
                  className="mt-2 w-full rounded-xl border border-white/20 bg-white/80 px-4 py-3 text-slate-900 placeholder:text-slate-500 outline-none backdrop-blur-md focus:border-indigo-400 focus:ring-2 focus:ring-indigo-400/40"
                />
              </div>

              {mode === "joint" && (
                <div>
                  <label className="block text-sm font-medium text-slate-200">URLs (optional, comma/newline separated)</label>
                  <textarea
                    value={jointUrlsRaw}
                    onChange={(e) => setJointUrlsRaw(e.target.value)}
                    placeholder="https://example.com/reset\nhttp://bit.ly/..."
                    rows={3}
                    className="mt-2 w-full rounded-xl border border-white/20 bg-white/80 px-4 py-3 text-slate-900 placeholder:text-slate-500 outline-none backdrop-blur-md focus:border-indigo-400 focus:ring-2 focus:ring-indigo-400/40"
                  />
                </div>
              )}
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
            className="mt-6 w-full rounded-xl bg-indigo-500 py-3 font-semibold text-white shadow-lg shadow-indigo-500/30 transition hover:bg-indigo-400 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loading ? "Analyzing..." : "Analyze"}
          </button>

          {err && (
            <div className="mt-4 rounded-xl border border-red-500/20 bg-red-500/10 p-3 text-sm text-red-200">{err}</div>
          )}
        </div>

        {(urlResult || emailResult || jointResult) && (
          <div className="mt-6 rounded-2xl border border-white/10 bg-white/10 p-8 shadow-2xl backdrop-blur-xl">
            <div className="flex items-start justify-between gap-4">
              <div>
                {primaryLabel && (
                  <div className={`inline-flex items-center rounded-full px-4 py-1 text-sm font-semibold ${riskChipClasses(primaryLabel)}`}>
                    {primaryLabel.toUpperCase()}
                  </div>
                )}
                <p className="mt-2 text-sm text-slate-300">Probability score is a confidence estimate (0-100%).</p>
              </div>

              <div className="text-right">
                <div className="text-4xl font-semibold">{pct}%</div>
                <div className="text-xs text-slate-400">risk score</div>
              </div>
            </div>

            <div className="mt-4 h-3 w-full overflow-hidden rounded-full border border-white/5 bg-slate-900/70">
              <div className="h-full bg-white/90" style={{ width: `${pct}%` }} />
            </div>

            {emailResult && mode === "email" && (
              <div className="mt-5 grid gap-3 rounded-xl border border-white/10 bg-slate-900/40 p-4 text-sm">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="text-slate-300">Risk level</span>
                  <span className={`font-semibold uppercase ${riskLevelClasses(emailResult.risk_level)}`}>
                    {emailResult.risk_level}
                  </span>
                </div>
                <div className="text-slate-300">Suggested action</div>
                <div className="text-slate-100">{emailResult.suggested_action}</div>
              </div>
            )}

            {jointResult && mode === "joint" && (
              <div className="mt-5 space-y-4">
                <div className="grid gap-3 sm:grid-cols-3">
                  <div className="rounded-xl border border-white/10 bg-slate-900/40 p-4">
                    <div className="text-xs text-slate-400">Email Score</div>
                    <div className="mt-1 text-xl font-semibold">{clampPct(jointResult.email_score)}%</div>
                  </div>
                  <div className="rounded-xl border border-white/10 bg-slate-900/40 p-4">
                    <div className="text-xs text-slate-400">URL Score (max)</div>
                    <div className="mt-1 text-xl font-semibold">{clampPct(jointResult.url_score)}%</div>
                  </div>
                  <div className="rounded-xl border border-white/10 bg-slate-900/40 p-4">
                    <div className="text-xs text-slate-400">Risk Level</div>
                    <div className={`mt-1 text-xl font-semibold uppercase ${riskLevelClasses(jointResult.risk_level)}`}>
                      {jointResult.risk_level}
                    </div>
                  </div>
                </div>

                <div className="rounded-xl border border-white/10 bg-slate-900/40 p-4 text-sm text-slate-300">
                  URLs analyzed: <span className="font-semibold text-slate-100">{jointResult.analyzed_url_count}</span>
                  {" • "}
                  risky URLs: <span className="font-semibold text-slate-100">{jointResult.risky_url_count}</span>
                </div>

                {jointResult.extracted_urls?.length > 0 && (
                  <div>
                    <h3 className="text-sm font-semibold text-slate-200">Extracted URLs</h3>
                    <ul className="mt-2 space-y-2">
                      {jointResult.extracted_urls.slice(0, 8).map((u, idx) => (
                        <li key={`${u}-${idx}`} className="rounded-lg border border-white/10 bg-slate-900/40 p-3 text-xs font-mono text-slate-200">
                          {u}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {jointResult.url_results?.length > 0 && (
                  <div>
                    <h3 className="text-sm font-semibold text-slate-200">Per-URL Scores</h3>
                    <ul className="mt-2 space-y-2">
                      {jointResult.url_results.slice(0, 6).map((r, idx) => (
                        <li key={`${r.url}-${idx}`} className="rounded-xl border border-white/10 bg-slate-900/40 p-3">
                          <div className="flex items-center justify-between gap-3">
                            <span className="truncate text-xs font-mono text-slate-200">{r.url}</span>
                            <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${riskChipClasses(r.label)}`}>
                              {r.label.toUpperCase()} {clampPct(r.score)}%
                            </span>
                          </div>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}

            {(mode === "url" ? urlResult?.reasons : mode === "email" ? emailResult?.reasons : jointResult?.reasons)?.length ? (
              <>
                <h2 className="mt-6 text-lg font-semibold">Reasons</h2>
                <ul className="mt-3 space-y-3">
                  {(mode === "url" ? urlResult?.reasons : mode === "email" ? emailResult?.reasons : jointResult?.reasons)!
                    .slice(0, 8)
                    .map((r, idx) => (
                      <li key={`${r.feature}-${idx}`} className="rounded-xl border border-white/10 bg-slate-900/40 p-4">
                        <div className="text-sm font-semibold text-slate-100">{r.feature}</div>
                        <div className="mt-1 text-sm text-slate-300">{r.note}</div>
                        <div className="mt-2 text-xs text-slate-400">value:</div>
                        <pre className="mt-1 max-w-full overflow-x-auto whitespace-pre-wrap break-all rounded-md bg-slate-950/40 p-2 text-xs font-mono text-slate-200">
                          {formatReasonValue(r.value)}
                        </pre>
                      </li>
                    ))}
                </ul>
              </>
            ) : null}

            <div className="mt-6 text-xs text-slate-400">
              engine: <span className="text-slate-200">{mode === "url" ? urlResult?.meta?.engine : mode === "email" ? emailResult?.meta?.engine : jointResult?.meta?.engine ?? "unknown"}</span>
            </div>
          </div>
        )}

        <div className="mt-10 text-center text-xs text-slate-500">
          Tip: In joint mode, URLs are auto-extracted from email body and combined with email model evidence.
        </div>
      </div>
    </main>
  );
}
