import { useState, useCallback } from "react";
import { DocumentUpload } from "./components/DocumentUpload";
import { WorkflowStream } from "./components/WorkflowStream";
import { StatusBadge } from "./components/StatusBadge";
import { HistoryPanel } from "./components/HistoryPanel";
import "./App.css";

interface LogEntry {
  node: string;
  message: string;
}

interface DonePayload {
  final_decision: string;
  doc_type: string;
  evaluation_score: number;
  hallucination_risk: string;
  trace_id?: string;
  clause_results?: { clause: string; status: string }[];
}

export default function App() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [result, setResult] = useState<DonePayload | null>(null);
  const [fileName, setFileName] = useState<string>("");
  const [error, setError] = useState<string>("");
  const [tenantId, setTenantId] = useState<string>("default");
  const [activeTab, setActiveTab] = useState<"analyze" | "history">("analyze");
  const [overrideApplied, setOverrideApplied] = useState<string | null>(null);

  const handleOverride = useCallback(async (traceId: string, decision: "APPROVED" | "REJECTED") => {
    try {
      await fetch(`/api/override/${traceId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decision }),
      });
      setOverrideApplied(decision);
    } catch {
      // override failed silently — display is best-effort
    }
  }, []);

  const handleFile = useCallback(async (file: File) => {
    setLogs([]);
    setResult(null);
    setError("");
    setOverrideApplied(null);
    setFileName(file.name);
    setStreaming(true);

    const formData = new FormData();
    formData.append("file", file);
    formData.append("tenant_id", tenantId);

    try {
      const res = await fetch("/api/analyze", {
        method: "POST",
        body: formData,
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
          } catch {
            // malformed SSE chunk — skip
          }
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
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
        </nav>
      </header>

      <main className="app-main">
        {activeTab === "history" ? (
          <HistoryPanel />
        ) : (
          <>
            <section className="upload-section">
              <h2>Upload Document</h2>
              <div style={{ marginBottom: "16px" }}>
                <label
                  htmlFor="tenant-select"
                  style={{ color: "#94a3b8", fontSize: "0.85rem", marginRight: "8px" }}
                >
                  Regulatory Profile:
                </label>
                <select
                  id="tenant-select"
                  value={tenantId}
                  onChange={(e) => setTenantId(e.target.value)}
                  disabled={streaming}
                  style={{
                    padding: "4px 10px",
                    borderRadius: "6px",
                    border: "1px solid #334155",
                    background: "#1e293b",
                    color: "#e2e8f0",
                    fontSize: "0.85rem",
                  }}
                >
                  <option value="default">Default</option>
                  <option value="EU">EU</option>
                  <option value="US">US</option>
                </select>
              </div>
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
                <h2>Analysis Result</h2>
                <div className="result-grid">
                  <div className="result-card">
                    <span className="result-label">Final Decision</span>
                    <StatusBadge decision={overrideApplied ?? result.final_decision} />
                  </div>
                  <div className="result-card">
                    <span className="result-label">Document Type</span>
                    <strong>{result.doc_type || "—"}</strong>
                  </div>
                  <div className="result-card">
                    <span className="result-label">Faithfulness Score</span>
                    <strong>{(result.evaluation_score * 100).toFixed(0)}%</strong>
                  </div>
                  <div className="result-card">
                    <span className="result-label">Hallucination Risk</span>
                    <strong style={{ textTransform: "capitalize" }}>
                      {result.hallucination_risk || "—"}
                    </strong>
                  </div>
                </div>

                {result.final_decision === "REJECTED" && result.trace_id && !overrideApplied && (
                  <div style={{ marginTop: "16px", display: "flex", gap: "8px", alignItems: "center" }}>
                    <span style={{ color: "#94a3b8", fontSize: "0.85rem" }}>
                      Compliance officer override:
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
                      Override → APPROVED
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
                        </tr>
                      </thead>
                      <tbody>
                        {result.clause_results.map((c, i) => (
                          <tr key={i} style={{ borderTop: "1px solid #1e293b" }}>
                            <td style={{ padding: "6px 8px", color: "#e2e8f0" }}>{c.clause}</td>
                            <td style={{ padding: "6px 8px" }}>
                              <span style={{
                                color: "#fff",
                                background: c.status === "PRESENT" ? "#15803d" : "#b91c1c",
                                padding: "2px 8px",
                                borderRadius: "4px",
                                fontWeight: 700,
                                fontSize: "0.72rem",
                              }}>
                                {c.status}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>
            )}
          </>
        )}
      </main>
    </div>
  );
}
