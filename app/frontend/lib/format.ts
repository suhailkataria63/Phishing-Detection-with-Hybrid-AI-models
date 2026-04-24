import { DetectMode, RecommendationCode, RiskLevel, UnifiedResult, VerdictLabel } from "@/lib/types";

const URL_SCHEME_RE = /^[a-zA-Z][a-zA-Z0-9+\-.]*:\/\//;

export function clamp01(value: number): number {
  if (!Number.isFinite(value)) return 0;
  if (value < 0) return 0;
  if (value > 1) return 1;
  return value;
}

export function toPct(value: number): number {
  return Math.round(clamp01(value) * 100);
}

export function formatModeLabel(mode: DetectMode): string {
  if (mode === "url") return "URL Detection";
  if (mode === "email") return "Email Detection";
  return "Joint Detection";
}

export function parseUrlList(raw: string): string[] {
  return Array.from(
    new Set(
      (raw || "")
        .split(/[\n,\s]+/)
        .map((token) => token.trim())
        .filter((token) => token.length >= 6)
    )
  );
}

export function normalizeUrlInput(raw: string): { normalized: string; error: string | null } {
  const value = (raw || "").trim();
  if (!value) {
    return { normalized: "", error: "Please enter a URL." };
  }

  const candidate = URL_SCHEME_RE.test(value) ? value : `https://${value}`;

  try {
    const parsed = new URL(candidate);
    if (!parsed.hostname) {
      return { normalized: "", error: "Invalid URL (missing hostname)." };
    }

    parsed.hostname = parsed.hostname.toLowerCase();
    if (parsed.port === "80" && parsed.protocol === "http:") parsed.port = "";
    if (parsed.port === "443" && parsed.protocol === "https:") parsed.port = "";
    if (!parsed.pathname) parsed.pathname = "/";

    return { normalized: parsed.toString(), error: null };
  } catch {
    return { normalized: "", error: "Invalid URL format." };
  }
}

export function recommendationFromScore(score: number, riskLevel: RiskLevel): {
  code: RecommendationCode;
  title: string;
  description: string;
} {
  const pct = toPct(score);

  if (riskLevel === "critical" || pct >= 85) {
    return {
      code: "high_risk_candidate",
      title: "High-risk phishing candidate",
      description: "Escalate immediately, isolate user action, and block related indicators.",
    };
  }

  if (riskLevel === "high" || pct >= 65) {
    return {
      code: "investigate_immediately",
      title: "Investigate immediately",
      description: "Treat as suspicious, validate sender and destination domains before any response.",
    };
  }

  if (riskLevel === "medium" || pct >= 40) {
    return {
      code: "review_carefully",
      title: "Review carefully",
      description: "Needs analyst review. Cross-check business context, links, and intent.",
    };
  }

  return {
    code: "likely_safe",
    title: "Likely safe",
    description: "Low-risk signal profile. Keep normal monitoring and sampling checks.",
  };
}

export function signalStatusLabel(value: boolean): string {
  return value ? "Detected" : "Not detected";
}

export function shortExplain(value: unknown): string {
  if (value === null || value === undefined) return String(value);
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

export function toUnifiedResult(
  mode: DetectMode,
  response: UnifiedResult["raw"]
): UnifiedResult {
  if (mode === "url") {
    const urlResp = response as UnifiedResult["raw"] & { probability: number; label: VerdictLabel; reasons: unknown[]; meta?: Record<string, unknown> };
    return {
      mode,
      label: urlResp.label,
      score: clamp01(urlResp.probability),
      riskLevel: clamp01(urlResp.probability) >= 0.8 ? "critical" : clamp01(urlResp.probability) >= 0.6 ? "high" : clamp01(urlResp.probability) >= 0.4 ? "medium" : "low",
      reasons: (urlResp.reasons as UnifiedResult["reasons"]) || [],
      strategy: String(urlResp.meta?.engine || "url_model"),
      operatingMode: String(urlResp.meta?.operating_mode || "balanced"),
      resolvedThreshold: Number(urlResp.meta?.resolved_threshold ?? 0.5),
      raw: response,
    };
  }

  if (mode === "email") {
    const emailResp = response as UnifiedResult["raw"] & {
      label: VerdictLabel;
      probability: number;
      risk_level: RiskLevel;
      reasons: UnifiedResult["reasons"];
      meta?: Record<string, unknown>;
    };
    return {
      mode,
      label: emailResp.label,
      score: clamp01(emailResp.probability),
      riskLevel: emailResp.risk_level,
      reasons: emailResp.reasons || [],
      strategy: String(emailResp.meta?.engine || "email_model"),
      operatingMode: String(emailResp.meta?.operating_mode || "balanced"),
      resolvedThreshold: Number(emailResp.meta?.resolved_threshold ?? 0.5),
      raw: response,
    };
  }

  const jointResp = response as UnifiedResult["raw"] & {
    final_label: VerdictLabel;
    final_score: number;
    risk_level: RiskLevel;
    reasons: UnifiedResult["reasons"];
    meta?: Record<string, unknown>;
  };
  return {
    mode,
    label: jointResp.final_label,
    score: clamp01(jointResp.final_score),
    riskLevel: jointResp.risk_level,
    reasons: jointResp.reasons || [],
    strategy: String(jointResp.meta?.joint_strategy || "optimized"),
    operatingMode: String(jointResp.meta?.operating_mode || "balanced"),
    resolvedThreshold: Number(jointResp.meta?.resolved_threshold ?? 0.5),
    raw: response,
  };
}
