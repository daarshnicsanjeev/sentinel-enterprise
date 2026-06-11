import { useState, useCallback } from "react";
import { DocumentUpload } from "./components/DocumentUpload";
import { WorkflowStream } from "./components/WorkflowStream";
import { StatusBadge } from "./components/StatusBadge";
import { HistoryPanel } from "./components/HistoryPanel";
import { InsightsDashboard } from "./components/InsightsDashboard";
import { ConfidenceGauge } from "./components/ConfidenceGauge";
import { ClauseDiffViewer } from "./components/ClauseDiffViewer";
import { HelpPanel } from "./components/HelpPanel";
import { FeedbackWidget } from "./components/FeedbackWidget";
import { SourceViewer } from "./components/SourceViewer";
import { DemoNotice } from "./components/DemoNotice";
import { DemoFeedback } from "./components/DemoFeedback";
import { MetricsPanel } from "./components/MetricsPanel";
import { BatchUpload } from "./components/BatchUpload";
import "./App.css";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

/** When the final decision is ESCALATE, clause PRESENT claims can't be trusted. */
export const clauseDisplayLabel = (status: string, finalDecision: string): string =>
  finalDecision === "ESCALATE" && status === "PRESENT" ? "⚠ UNVERIFIED" : status;

/** Convert "CREDIT_AGREEMENT" → "Credit Agreement" for human display. */
const formatDocType = (raw: string) =>
  raw
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
    .join(" ");

interface LogEntry {
  node: string;
  message: string;
}

interface ClauseResult {
  clause: string;
  status: string;
  evidence?: string;
  citation_verified?: boolean;
  citation_offset?: number;
}

interface DonePayload {
  final_decision: string;
  doc_type: string;
  evaluation_score: number;
  hallucination_risk: string;
  routing_confidence?: number;
  trace_id?: string;
  clause_results?: ClauseResult[];
  clause_results_history?: ClauseResult[][];
  from_cache?: boolean;
  sanitized?: boolean;
}

export default function App() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [result, setResult] = useState<DonePayload | null>(null);
  const [fileName, setFileName] = useState<string>("");
  const [error, setError] = useState<string>("");
  const [activeTab, setActiveTab] = useState<"analyze" | "history" | "batch" | "metrics" | "insights" | "help">("analyze");
  const [overrideApplied, setOverrideApplied] = useState<string | null>(null);
  const [currentFile, setCurrentFile] = useState<File | null>(null);

  const handleOverride = useCallback(async (traceId: string, decision: "APPROVED" | "REJECTED") => {
    try {
      await fetch(`${API_BASE}/api/override/${traceId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decision }),
      });
      setOverrideApplied(decision);
    } catch {
      // override failed silently — display is best-effort
    }
  }, []);

  const handleFile = useCallback(async (file: File, forceRefresh = false) => {
    setLogs([]);
    setResult(null);
    setError("");
    setOverrideApplied(null);
    setFileName(file.name);
    setCurrentFile(file);
    setStreaming(true);

    const formData = new FormData();
    formData.append("file", file);
    if (forceRefresh) formData.append("force_refresh", "true");

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 300_000); // 5-min hard timeout

    try {
      const res = await fetch(`${API_BASE}/api/analyze`, {
        method: "POST",
        body: formData,
        signal: controller.signal,
      });

      if (!res.ok) {
        const text = await res.text();
        throw new Error(`Server error ${res.status}: ${text}`);
      }

      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() ?? "";

        for (const part of parts) {
          const line = part.replace(/^data:\s*/, "").trim();
          if (!line) continue;
          try {
            const payload = JSON.parse(line);
            if (payload.type === "log") {
              setLogs((prev) => [...prev, { node: payload.node, message: payload.message }]);
            } else if (payload.type === "done") {
              setResult(payload as DonePayload);
            }
          } catch (parseErr) {
            console.error("[Sentinel] Malformed SSE chunk — skipped:", line, parseErr);
          }
        }
      }
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") {
        setError("Analysis timed out after 5 minutes.");
      } else {
        setError(err instanceof Error ? err.message : "Unknown error");
      }
    } finally {
      clearTimeout(timeoutId);
      setStreaming(false);
    }
  }, []);

  const handleReanalyze = useCallback(async (traceId: string, filename: string) => {
    setLogs([]);
    setResult(null);
    setError("");
    setOverrideApplied(null);
    setCurrentFile(null);
    setFileName(`${filename} (re-analysis)`);
    setActiveTab("analyze");
    setStreaming(true);

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 300_000);

    try {
      const res = await fetch(`${API_BASE}/api/history/${traceId}/reanalyze`, {
        method: "POST",
        signal: controller.signal,
      });

      if (!res.ok) {
        const text = await res.text();
        throw new Error(`Server error ${res.status}: ${text}`);
      }

      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() ?? "";
        for (const part of parts) {
          const line = part.replace(/^data:\s*/, "").trim();
          if (!line) continue;
          try {
            const payload = JSON.parse(line);
            if (payload.type === "log") {
              setLogs((prev) => [...prev, { node: payload.node, message: payload.message }]);
            } else if (payload.type === "done") {
              setResult(payload as DonePayload);
            }
          } catch { /* skip malformed chunks */ }
        }
      }
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") {
        setError("Re-analysis timed out after 5 minutes.");
      } else {
        setError(err instanceof Error ? err.message : "Re-analysis failed.");
      }
    } finally {
      clearTimeout(timeoutId);
      setStreaming(false);
    }
  }, []);

  return (
    <div className="app">
      <header className="app-header">
        <div className="logo">⚡ Project Sentinel</div>
        <p className="subtitle">
          Enterprise Agentic Document Routing &amp; Compliance Engine
        </p>
        <nav style={{ display: "flex", gap: "8px", marginTop: "12px" }}>
          <button
            onClick={() => setActiveTab("analyze")}
            style={{
              padding: "6px 16px",
              borderRadius: "6px",
              border: "none",
              cursor: "pointer",
              background: activeTab === "analyze" ? "#2563eb" : "#1e293b",
              color: "#e2e8f0",
              fontWeight: activeTab === "analyze" ? 700 : 400,
            }}
          >
            Analyze Document
          </button>
          <button
            onClick={() => setActiveTab("history")}
            style={{
              padding: "6px 16px",
              borderRadius: "6px",
              border: "none",
              cursor: "pointer",
              background: activeTab === "history" ? "#2563eb" : "#1e293b",
              color: "#e2e8f0",
              fontWeight: activeTab === "history" ? 700 : 400,
            }}
          >
            Analysis History
          </button>
          <button
            onClick={() => setActiveTab("batch")}
            style={{
              padding: "6px 16px",
              borderRadius: "6px",
              border: "none",
              cursor: "pointer",
              background: activeTab === "batch" ? "#2563eb" : "#1e293b",
              color: "#e2e8f0",
              fontWeight: activeTab === "batch" ? 700 : 400,
            }}
          >
            Batch Upload
          </button>
          <button
            onClick={() => setActiveTab("metrics")}
            style={{
              padding: "6px 16px",
              borderRadius: "6px",
              border: "none",
              cursor: "pointer",
              background: activeTab === "metrics" ? "#2563eb" : "#1e293b",
              color: "#e2e8f0",
              fontWeight: activeTab === "metrics" ? 700 : 400,
            }}
          >
            Metrics
          </button>
          <button
            onClick={() => setActiveTab("insights")}
            style={{
              padding: "6px 16px",
              borderRadius: "6px",
              border: "none",
              cursor: "pointer",
              background: activeTab === "insights" ? "#7c3aed" : "#1e293b",
              color: "#e2e8f0",
              fontWeight: activeTab === "insights" ? 700 : 400,
            }}
          >
            ⚡ Insights
          </button>
          <button
            onClick={() => setActiveTab("help")}
            style={{
              padding: "6px 16px",
              borderRadius: "6px",
              border: "none",
              cursor: "pointer",
              background: activeTab === "help" ? "#2563eb" : "#1e293b",
              color: "#e2e8f0",
              fontWeight: activeTab === "help" ? 700 : 400,
            }}
          >
            Help &amp; Docs
          </button>
        </nav>
      </header>

      <DemoNotice />

      <main className="app-main">
        {activeTab === "history" ? (
          <HistoryPanel onReanalyze={handleReanalyze} />
        ) : activeTab === "insights" ? (
          <InsightsDashboard />
        ) : activeTab === "batch" ? (
          <BatchUpload apiBase={API_BASE} />
        ) : activeTab === "metrics" ? (
          <MetricsPanel apiBase={API_BASE} />
        ) : activeTab === "help" ? (
          <HelpPanel />
        ) : (
          <>
            <section className="upload-section">
              <h2>Upload Document</h2>
              <DocumentUpload onFile={handleFile} disabled={streaming} />
              {fileName && (
                <p className="file-label">
                  Analysing: <strong>{fileName}</strong>
                </p>
              )}
            </section>

            <section className="stream-section">
              <div className="stream-header">
                <h2>Agent Workflow Log</h2>
                {streaming && <span className="badge-streaming">LIVE</span>}
              </div>
              <WorkflowStream logs={logs} streaming={streaming} />
            </section>

            {error && (
              <div className="error-banner" role="alert">
                ⚠ {error}
              </div>
            )}

            {result && !streaming && (
              <section className="result-section" aria-live="polite">
                <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "16px" }}>
                  <h2 style={{ margin: 0 }}>Analysis Result</h2>
                  {result.from_cache ? (
                    <span
                      aria-label="Result served from cache"
                      style={{
                        background: "#1e3a5f",
                        color: "#93c5fd",
                        border: "1px solid #2563eb",
                        borderRadius: "6px",
                        padding: "3px 10px",
                        fontSize: "0.75rem",
                        fontWeight: 600,
                        letterSpacing: "0.04em",
                      }}
                    >
                      ⚡ Cached Result
                    </span>
                  ) : (
                    <span
                      aria-label="Fresh analysis result"
                      style={{
                        background: "#14532d",
                        color: "#86efac",
                        border: "1px solid #15803d",
                        borderRadius: "6px",
                        padding: "3px 10px",
                        fontSize: "0.75rem",
                        fontWeight: 600,
                        letterSpacing: "0.04em",
                      }}
                    >
                      ✓ Fresh Analysis
                    </span>
                  )}
                  {result.from_cache && currentFile && (
                    <button
                      onClick={() => handleFile(currentFile, true)}
                      aria-label="Clear cache and re-analyse this document from the beginning"
                      style={{
                        padding: "4px 14px",
                        borderRadius: "6px",
                        border: "1px solid #334155",
                        background: "#1e293b",
                        color: "#94a3b8",
                        fontSize: "0.78rem",
                        fontWeight: 600,
                        cursor: "pointer",
                      }}
                    >
                      ↺ Re-analyse (clear cache)
                    </button>
                  )}
                </div>
                <dl className="result-grid">
                  <div className="result-card">
                    <dt className="result-label">Final Decision</dt>
                    <dd><StatusBadge decision={overrideApplied ?? result.final_decision} /></dd>
                  </div>
                  <div className="result-card">
                    <dt className="result-label">Document Type</dt>
                    <dd><strong>{result.doc_type ? formatDocType(result.doc_type) : "—"}</strong></dd>
                  </div>
                  {result.routing_confidence != null && result.routing_confidence > 0 && (
                    <div className="result-card">
                      <dt className="result-label">Routing Confidence</dt>
                      <dd><ConfidenceGauge confidence={result.routing_confidence} hideLabel /></dd>
                    </div>
                  )}
                  {result.sanitized !== false && (
                    <>
                      <div className="result-card">
                        <dt className="result-label">Faithfulness Score</dt>
                        <dd><strong>{(result.evaluation_score * 100).toFixed(0)}%</strong></dd>
                      </div>
                      <div className="result-card">
                        <dt className="result-label">Hallucination Risk</dt>
                        <dd><strong style={{ textTransform: "capitalize" }}>
                          {result.hallucination_risk || "—"}
                        </strong></dd>
                      </div>
                    </>
                  )}
                </dl>

                {result.sanitized === false && (
                  <div
                    role="note"
                    aria-label="Document blocked by security guardrail"
                    style={{
                      marginTop: "16px",
                      padding: "12px 16px",
                      borderRadius: "8px",
                      background: "#f5f3ff",
                      border: "1px solid #7c3aed",
                      color: "#5b21b6",
                      fontSize: "0.85rem",
                    }}
                  >
                    <strong>Blocked by security guardrail.</strong> The document contained content that matched a prompt-injection or disallowed-input pattern. No compliance analysis was performed. Review the document and re-upload if you believe this is a false positive.
                  </div>
                )}

                {result.final_decision === "REJECTED" && result.sanitized !== false && result.trace_id && !overrideApplied && (
                  <div style={{ marginTop: "16px", display: "flex", gap: "8px", alignItems: "center" }}>
                    <span style={{ color: "#94a3b8", fontSize: "0.85rem" }}>
                      Compliance Officer Override:
                    </span>
                    <button
                      onClick={() => handleOverride(result.trace_id!, "APPROVED")}
                      style={{
                        padding: "6px 14px",
                        borderRadius: "6px",
                        border: "none",
                        background: "#15803d",
                        color: "#fff",
                        fontWeight: 700,
                        cursor: "pointer",
                        fontSize: "0.82rem",
                      }}
                    >
                      Override &amp; Approve
                    </button>
                  </div>
                )}

                {result.clause_results && result.clause_results.length > 0 && (
                  <div style={{ marginTop: "20px" }}>
                    <h3 style={{ color: "#94a3b8", fontSize: "0.85rem", marginBottom: "8px", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                      Clause Breakdown
                    </h3>
                    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.82rem" }}>
                      <thead>
                        <tr>
                          <th style={{ textAlign: "left", color: "#64748b", padding: "4px 8px" }}>Clause</th>
                          <th style={{ textAlign: "left", color: "#64748b", padding: "4px 8px" }}>Status</th>
                          <th style={{ textAlign: "left", color: "#64748b", padding: "4px 8px" }}>Cited Evidence</th>
                        </tr>
                      </thead>
                      <tbody>
                        {result.clause_results.map((c, i) => {
                          const label = clauseDisplayLabel(c.status, result.final_decision);
                          const unverified = label === "⚠ UNVERIFIED";
                          return (
                            <tr key={i} style={{ borderTop: "1px solid #1e293b" }}>
                              <td style={{ padding: "6px 8px", color: "#e2e8f0" }}>{c.clause}</td>
                              <td style={{ padding: "6px 8px" }}>
                                <span
                                  aria-label={unverified ? `${c.clause} unverified` : `${c.clause} ${c.status.toLowerCase()}`}
                                  style={{
                                    color: unverified ? "#92400e" : "#fff",
                                    background: unverified ? "#fef3c7" : c.status === "PRESENT" ? "#15803d" : "#b91c1c",
                                    border: unverified ? "1px solid #d97706" : "none",
                                    padding: "2px 8px",
                                    borderRadius: "4px",
                                    fontWeight: 700,
                                    fontSize: "0.72rem",
                                  }}
                                >
                                  {label}
                                </span>
                              </td>
                              <td style={{ padding: "6px 8px", color: "#94a3b8", maxWidth: "320px" }}>
                                {c.evidence ? (
                                  <>
                                    <span
                                      aria-label={
                                        c.citation_verified
                                          ? `Citation for ${c.clause} verified in source document`
                                          : `Citation for ${c.clause} could not be verified in source document`
                                      }
                                      title={
                                        c.citation_verified
                                          ? "This exact passage was found in the uploaded document"
                                          : "This passage could not be located in the uploaded document"
                                      }
                                      style={{
                                        color: c.citation_verified ? "#4ade80" : "#fbbf24",
                                        fontWeight: 700,
                                        fontSize: "0.72rem",
                                        marginRight: "6px",
                                        whiteSpace: "nowrap",
                                      }}
                                    >
                                      {c.citation_verified ? "✓ Verified in source" : "⚠ Not found in source"}
                                    </span>
                                    <span style={{ fontStyle: "italic", fontSize: "0.78rem" }}>
                                      “{c.evidence.length > 140 ? c.evidence.slice(0, 140) + "…" : c.evidence}”
                                    </span>
                                  </>
                                ) : (
                                  <span style={{ color: "#475569", fontSize: "0.78rem" }}>—</span>
                                )}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                    {result.trace_id && (
                      <SourceViewer
                        traceId={result.trace_id}
                        apiBase={API_BASE}
                        highlights={result.clause_results
                          .filter((c) => c.evidence && c.citation_verified)
                          .map((c) => c.evidence!) }
                      />
                    )}
                  </div>
                )}
                {result.clause_results_history && result.clause_results_history.length >= 2 && (
                  <ClauseDiffViewer history={result.clause_results_history} />
                )}

                {result.sanitized !== false && result.trace_id && (
                  <FeedbackWidget traceId={result.trace_id} apiBase={API_BASE} />
                )}
              </section>
            )}
          </>
        )}
        <DemoFeedback apiBase={API_BASE} />
      </main>
    </div>
  );
}
