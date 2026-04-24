"use client";

import { useMemo, useState } from "react";

import { BatchResultsTable } from "@/components/batch/BatchResultsTable";
import { BatchUploadPanel } from "@/components/batch/BatchUploadPanel";
import { CaseDetailDrawer } from "@/components/batch/CaseDetailDrawer";
import { DetectionForm } from "@/components/dashboard/DetectionForm";
import { ExplanationCard } from "@/components/dashboard/ExplanationCard";
import { RecommendationCard } from "@/components/dashboard/RecommendationCard";
import { SignalBreakdownCard } from "@/components/dashboard/SignalBreakdownCard";
import { SummaryCard } from "@/components/dashboard/SummaryCard";
import { SectionCard } from "@/components/shared/SectionCard";
import { detectEmail, detectJoint, detectUrl } from "@/lib/api";
import { parseCsvToRows, exportRowsToCsv } from "@/lib/csv";
import {
  clamp01,
  normalizeUrlInput,
  parseUrlList,
  recommendationFromScore,
  toUnifiedResult,
} from "@/lib/format";
import {
  BatchAnalyzedRow,
  BatchInputRow,
  DetectMode,
  DetectorInputs,
  JointResponse,
  JointStrategy,
  OperatingMode,
  UnifiedResult,
  WorkspaceMode,
} from "@/lib/types";

const DEFAULT_INPUTS: DetectorInputs = {
  url: "",
  subject: "",
  body: "",
  sender: "",
  jointUrlsRaw: "",
};

function extractUrlsFromText(text: string): string[] {
  const matches = text.match(/https?:\/\/[^\s)"'<>]+/gi) || [];
  return Array.from(new Set(matches));
}

function parseOptionalThreshold(raw: string): number | undefined {
  const trimmed = raw.trim();
  if (!trimmed) return undefined;
  const parsed = Number(trimmed);
  if (Number.isNaN(parsed)) return undefined;
  return clamp01(parsed);
}

function normalizeBatchInputForMode(mode: DetectMode, row: BatchInputRow): {
  subject: string;
  body: string;
  sender: string;
  urls: string[];
  urlSingle: string;
} {
  const manualUrls = parseUrlList(row.urlsRaw);
  const bodyUrls = extractUrlsFromText(row.body);
  const rowSingle = row.urlSingle ? [row.urlSingle.trim()] : [];

  const urls = Array.from(new Set([...rowSingle, ...manualUrls, ...bodyUrls].filter((value) => value.length > 0)));
  const urlSingle = urls[0] || "";

  if (mode === "url") {
    return { subject: "", body: "", sender: "", urls, urlSingle };
  }

  return {
    subject: row.subject,
    body: row.body,
    sender: row.sender,
    urls,
    urlSingle,
  };
}

export default function Home() {
  const API_BASE = process.env.NEXT_PUBLIC_API_BASE?.trim() || "http://localhost:8000";

  const [workspace, setWorkspace] = useState<WorkspaceMode>("detect");

  const [mode, setMode] = useState<DetectMode>("joint");
  const [inputs, setInputs] = useState<DetectorInputs>(DEFAULT_INPUTS);
  const [operatingMode, setOperatingMode] = useState<OperatingMode>("balanced");
  const [jointStrategy, setJointStrategy] = useState<JointStrategy>("optimized");
  const [enableExplain, setEnableExplain] = useState(true);
  const [normalizedPreview, setNormalizedPreview] = useState<string | null>(null);

  const [loading, setLoading] = useState(false);
  const [detectError, setDetectError] = useState<string | null>(null);
  const [result, setResult] = useState<UnifiedResult | null>(null);

  const [batchMode, setBatchMode] = useState<DetectMode>("joint");
  const [batchOperatingMode, setBatchOperatingMode] = useState<OperatingMode>("balanced");
  const [batchJointStrategy, setBatchJointStrategy] = useState<JointStrategy>("optimized");
  const [batchThreshold, setBatchThreshold] = useState("");
  const [batchRows, setBatchRows] = useState<BatchInputRow[]>([]);
  const [batchResults, setBatchResults] = useState<BatchAnalyzedRow[]>([]);
  const [batchLoading, setBatchLoading] = useState(false);
  const [batchError, setBatchError] = useState<string | null>(null);
  const [batchProgress, setBatchProgress] = useState<string>("");
  const [selectedBatchRow, setSelectedBatchRow] = useState<BatchAnalyzedRow | null>(null);

  const cfg = useMemo(() => ({ apiBase: API_BASE, enableExplain }), [API_BASE, enableExplain]);

  function updateInput<K extends keyof DetectorInputs>(key: K, value: DetectorInputs[K]) {
    setInputs((prev) => ({ ...prev, [key]: value }));
  }

  async function runDetection() {
    setDetectError(null);
    setResult(null);
    setNormalizedPreview(null);
    setLoading(true);

    try {
      if (mode === "url") {
        const normalized = normalizeUrlInput(inputs.url);
        if (normalized.error) {
          setDetectError(normalized.error);
          setLoading(false);
          return;
        }

        setNormalizedPreview(normalized.normalized);
        const response = await detectUrl(cfg, { url: normalized.normalized });
        setResult(toUnifiedResult("url", response));
      }

      if (mode === "email") {
        if (!inputs.subject.trim() && !inputs.body.trim()) {
          setDetectError("Provide at least subject or body for email analysis.");
          setLoading(false);
          return;
        }

        const response = await detectEmail(cfg, {
          subject: inputs.subject,
          body: inputs.body,
          sender: inputs.sender,
          operatingMode,
        });
        setResult(toUnifiedResult("email", response));
      }

      if (mode === "joint") {
        if (!inputs.subject.trim() && !inputs.body.trim() && !inputs.jointUrlsRaw.trim()) {
          setDetectError("Provide email content and/or URLs for joint analysis.");
          setLoading(false);
          return;
        }

        const manualUrls = parseUrlList(inputs.jointUrlsRaw);
        const response = await detectJoint(cfg, {
          subject: inputs.subject,
          body: inputs.body,
          sender: inputs.sender,
          urls: manualUrls,
          operatingMode,
          strategy: jointStrategy,
        });
        setResult(toUnifiedResult("joint", response));
      }
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "Analysis failed.";
      setDetectError(message);
    } finally {
      setLoading(false);
    }
  }

  async function handleBatchFile(file: File) {
    setBatchError(null);
    try {
      const text = await file.text();
      const rows = parseCsvToRows(text);
      if (rows.length === 0) {
        setBatchError("No rows detected. Ensure the CSV has a header and at least one data row.");
        return;
      }
      setBatchRows(rows);
      setBatchResults([]);
      setSelectedBatchRow(null);
    } catch {
      setBatchError("Unable to read CSV file.");
    }
  }

  async function analyzeBatch() {
    if (batchRows.length === 0) {
      setBatchError("Upload a CSV first.");
      return;
    }

    setBatchError(null);
    setBatchResults([]);
    setSelectedBatchRow(null);
    setBatchLoading(true);

    const thresholdOverride = parseOptionalThreshold(batchThreshold);
    const analyzed: BatchAnalyzedRow[] = [];

    try {
      for (let idx = 0; idx < batchRows.length; idx += 1) {
        const row = batchRows[idx];
        setBatchProgress(`Analyzing row ${idx + 1}/${batchRows.length}`);

        const normalized = normalizeBatchInputForMode(batchMode, row);

        if (batchMode === "url") {
          if (!normalized.urlSingle) continue;
          const normalizedUrl = normalizeUrlInput(normalized.urlSingle);
          if (normalizedUrl.error) continue;

          const output = await detectUrl(cfg, { url: normalizedUrl.normalized });
          const unified = toUnifiedResult("url", output);
          const rec = recommendationFromScore(unified.score, unified.riskLevel);

          analyzed.push({
            rowIndex: row.rowIndex,
            caseId: row.caseId,
            mode: "url",
            label: unified.label,
            score: unified.score,
            riskLevel: unified.riskLevel,
            recommendationCode: rec.code,
            recommendation: rec.title,
            explanationSummary: unified.reasons[0]?.note || "No explanation metadata",
            input: row,
            output,
            extractedUrls: [normalizedUrl.normalized],
          });

          continue;
        }

        if (batchMode === "email") {
          if (!normalized.subject.trim() && !normalized.body.trim()) continue;
          const output = await detectEmail(cfg, {
            subject: normalized.subject,
            body: normalized.body,
            sender: normalized.sender,
            operatingMode: batchOperatingMode,
            threshold: thresholdOverride,
          });
          const unified = toUnifiedResult("email", output);
          const rec = recommendationFromScore(unified.score, unified.riskLevel);

          analyzed.push({
            rowIndex: row.rowIndex,
            caseId: row.caseId,
            mode: "email",
            label: unified.label,
            score: unified.score,
            riskLevel: unified.riskLevel,
            recommendationCode: rec.code,
            recommendation: rec.title,
            explanationSummary: unified.reasons[0]?.note || "No explanation metadata",
            input: row,
            output,
            extractedUrls: normalized.urls,
          });

          continue;
        }

        if (!normalized.subject.trim() && !normalized.body.trim() && normalized.urls.length === 0) continue;

        const output = await detectJoint(cfg, {
          subject: normalized.subject,
          body: normalized.body,
          sender: normalized.sender,
          urls: normalized.urls,
          operatingMode: batchOperatingMode,
          strategy: batchJointStrategy,
          threshold: thresholdOverride,
        });
        const unified = toUnifiedResult("joint", output);
        const rec = recommendationFromScore(unified.score, unified.riskLevel);

        analyzed.push({
          rowIndex: row.rowIndex,
          caseId: row.caseId,
          mode: "joint",
          label: unified.label,
          score: unified.score,
          riskLevel: unified.riskLevel,
          recommendationCode: rec.code,
          recommendation: rec.title,
          explanationSummary: unified.reasons[0]?.note || "No explanation metadata",
          input: row,
          output,
          extractedUrls: (output as JointResponse).extracted_urls || normalized.urls,
        });
      }

      setBatchResults(analyzed);
      setBatchProgress(`Completed ${analyzed.length} analyzed rows.`);
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : "Batch run failed.";
      setBatchError(message);
    } finally {
      setBatchLoading(false);
    }
  }

  function exportBatchCsv() {
    const headers = [
      "row_index",
      "case_id",
      "mode",
      "label",
      "score",
      "risk_level",
      "recommendation",
      "explanation_summary",
    ];

    const rows = batchResults.map((row) => [
      String(row.rowIndex),
      row.caseId,
      row.mode,
      row.label,
      row.score.toFixed(4),
      row.riskLevel,
      row.recommendation,
      row.explanationSummary,
    ]);

    const csv = exportRowsToCsv(headers, rows);
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `batch_results_${Date.now()}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  const recommendation = result
    ? recommendationFromScore(result.score, result.riskLevel)
    : null;

  return (
    <main className="min-h-screen bg-security text-slate-100">
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <header className="mb-6 rounded-2xl border border-white/10 bg-slate-900/70 p-5 backdrop-blur">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-[0.18em] text-indigo-300/80">Phish Detector</p>
              <h1 className="mt-2 text-2xl font-semibold tracking-tight">Phishing Triage Console</h1>
              <p className="mt-2 text-sm text-slate-400">
                Unified analyst workspace for URL, email, and joint phishing investigations.
              </p>
            </div>
            <div className="rounded-lg border border-indigo-400/30 bg-indigo-500/10 px-3 py-2 text-xs text-indigo-200">
              API base: <span className="font-mono">{API_BASE}</span>
            </div>
          </div>

          <div className="mt-5 inline-flex rounded-xl border border-white/10 bg-slate-950/70 p-1">
            <button
              type="button"
              onClick={() => setWorkspace("detect")}
              className={`rounded-lg px-4 py-2 text-sm font-semibold transition ${
                workspace === "detect" ? "bg-indigo-500/20 text-indigo-100" : "text-slate-300 hover:bg-slate-900"
              }`}
            >
              Detection Workspace
            </button>
            <button
              type="button"
              onClick={() => setWorkspace("batch")}
              className={`rounded-lg px-4 py-2 text-sm font-semibold transition ${
                workspace === "batch" ? "bg-indigo-500/20 text-indigo-100" : "text-slate-300 hover:bg-slate-900"
              }`}
            >
              Batch Analysis
            </button>
          </div>
        </header>

        {workspace === "detect" ? (
          <div className="grid gap-6 lg:grid-cols-12">
            <div className="space-y-6 lg:col-span-5">
              <SectionCard
                title="Main Detection Workspace"
                subtitle="Configure analysis mode, threshold profile, and strategy"
              >
                <DetectionForm
                  mode={mode}
                  inputs={inputs}
                  enableExplain={enableExplain}
                  loading={loading}
                  operatingMode={operatingMode}
                  jointStrategy={jointStrategy}
                  normalizedPreview={normalizedPreview}
                  error={detectError}
                  onModeChange={setMode}
                  onInputChange={updateInput}
                  onOperatingModeChange={setOperatingMode}
                  onJointStrategyChange={setJointStrategy}
                  onEnableExplainChange={setEnableExplain}
                  onSubmit={runDetection}
                />
              </SectionCard>
            </div>

            <div className="space-y-6 lg:col-span-7">
              {!result ? (
                <SectionCard title="Awaiting Analysis" subtitle="Run a detection to view score and explanation details">
                  <div className="rounded-xl border border-dashed border-white/20 bg-slate-950/60 p-6 text-sm text-slate-400">
                    Use the left panel to submit URL, email, or joint evidence. This panel will show summary, score
                    breakdown, explanation signals, and analyst recommendation.
                  </div>
                </SectionCard>
              ) : (
                <>
                  <SummaryCard result={result} />
                  <RecommendationCard result={result} />
                  <SignalBreakdownCard result={result} />
                  <ExplanationCard result={result} />

                  {recommendation ? (
                    <SectionCard title="Operational Note" subtitle="Triage context">
                      <div className="text-sm text-slate-300">
                        Recommendation class: <span className="font-semibold text-slate-100">{recommendation.code}</span>
                      </div>
                    </SectionCard>
                  ) : null}
                </>
              )}
            </div>
          </div>
        ) : (
          <div className="space-y-6">
            <BatchUploadPanel
              mode={batchMode}
              operatingMode={batchOperatingMode}
              strategy={batchJointStrategy}
              threshold={batchThreshold}
              loading={batchLoading}
              rowCount={batchRows.length}
              onModeChange={setBatchMode}
              onOperatingModeChange={setBatchOperatingMode}
              onStrategyChange={setBatchJointStrategy}
              onThresholdChange={setBatchThreshold}
              onFileSelect={handleBatchFile}
              onRun={analyzeBatch}
            />

            {batchError ? (
              <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-200">{batchError}</div>
            ) : null}

            {batchProgress ? (
              <div className="rounded-xl border border-white/10 bg-slate-900/70 p-3 text-sm text-slate-300">{batchProgress}</div>
            ) : null}

            <BatchResultsTable rows={batchResults} onSelectRow={setSelectedBatchRow} onExport={exportBatchCsv} />
          </div>
        )}
      </div>

      <CaseDetailDrawer row={selectedBatchRow} onClose={() => setSelectedBatchRow(null)} />
    </main>
  );
}
