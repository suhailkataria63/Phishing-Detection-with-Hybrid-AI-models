export type DetectMode = "url" | "email" | "joint";
export type WorkspaceMode = "detect" | "batch";

export type OperatingMode = "soc" | "balanced" | "high_confidence";
export type JointStrategy = "baseline" | "optimized";

export type VerdictLabel = "phishing" | "legitimate";
export type RiskLevel = "low" | "medium" | "high" | "critical";

export type Reason = {
  feature: string;
  value: unknown;
  note: string;
};

export type UrlResponse = {
  label: VerdictLabel;
  probability: number;
  url_score: number;
  reasons: Reason[];
  meta?: Record<string, unknown>;
};

export type EmailResponse = {
  label: VerdictLabel;
  probability: number;
  email_score: number;
  risk_level: RiskLevel;
  suggested_action: string;
  reasons: Reason[];
  context?: Record<string, unknown>;
  meta?: Record<string, unknown>;
};

export type UrlAssessment = {
  url: string;
  label: VerdictLabel;
  score: number;
  reasons: Reason[];
};

export type JointResponse = {
  final_label: VerdictLabel;
  final_score: number;
  risk_level: RiskLevel;
  email_label: VerdictLabel;
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

export type UnifiedResult = {
  mode: DetectMode;
  label: VerdictLabel;
  score: number;
  riskLevel: RiskLevel;
  reasons: Reason[];
  strategy?: string;
  operatingMode?: string;
  resolvedThreshold?: number;
  raw: UrlResponse | EmailResponse | JointResponse;
};

export type DetectorInputs = {
  url: string;
  subject: string;
  body: string;
  sender: string;
  jointUrlsRaw: string;
};

export type BatchInputRow = {
  rowIndex: number;
  caseId: string;
  subject: string;
  body: string;
  sender: string;
  urlsRaw: string;
  urlSingle: string;
  expectedLabel?: string;
  raw: Record<string, string>;
};

export type RecommendationCode =
  | "likely_safe"
  | "review_carefully"
  | "investigate_immediately"
  | "high_risk_candidate";

export type BatchAnalyzedRow = {
  rowIndex: number;
  caseId: string;
  mode: DetectMode;
  label: VerdictLabel;
  score: number;
  riskLevel: RiskLevel;
  recommendationCode: RecommendationCode;
  recommendation: string;
  explanationSummary: string;
  input: BatchInputRow;
  output: UrlResponse | EmailResponse | JointResponse;
  extractedUrls: string[];
};
