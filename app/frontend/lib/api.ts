import {
  EmailResponse,
  JointResponse,
  JointStrategy,
  OperatingMode,
  UrlResponse,
} from "@/lib/types";

export type DetectRequestConfig = {
  apiBase: string;
  enableExplain: boolean;
};

async function fetchJson<T>(url: string, payload: Record<string, unknown>): Promise<T> {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    let detail = "Request failed";
    try {
      const maybeJson = await response.json();
      detail = typeof maybeJson?.detail === "string" ? maybeJson.detail : JSON.stringify(maybeJson);
    } catch {
      detail = await response.text();
    }
    throw new Error(`Backend error (${response.status}): ${detail}`);
  }

  return (await response.json()) as T;
}

export async function detectUrl(
  cfg: DetectRequestConfig,
  payload: { url: string }
): Promise<UrlResponse> {
  return fetchJson<UrlResponse>(`${cfg.apiBase}/detect/url`, {
    url: payload.url,
    enable_context: false,
    enable_explain: cfg.enableExplain,
  });
}

export async function detectEmail(
  cfg: DetectRequestConfig,
  payload: {
    subject: string;
    body: string;
    sender: string;
    operatingMode: OperatingMode;
    threshold?: number;
  }
): Promise<EmailResponse> {
  return fetchJson<EmailResponse>(`${cfg.apiBase}/detect/email`, {
    subject: payload.subject,
    body: payload.body,
    sender: payload.sender,
    operating_mode: payload.operatingMode,
    threshold: payload.threshold,
    enable_explain: cfg.enableExplain,
  });
}

export async function detectJoint(
  cfg: DetectRequestConfig,
  payload: {
    subject: string;
    body: string;
    sender: string;
    urls: string[];
    operatingMode: OperatingMode;
    strategy: JointStrategy;
    threshold?: number;
  }
): Promise<JointResponse> {
  return fetchJson<JointResponse>(`${cfg.apiBase}/detect/joint`, {
    subject: payload.subject,
    body: payload.body,
    sender: payload.sender,
    urls: payload.urls,
    operating_mode: payload.operatingMode,
    joint_strategy: payload.strategy,
    threshold: payload.threshold,
    enable_explain: cfg.enableExplain,
  });
}
