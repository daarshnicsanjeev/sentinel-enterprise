import { useEffect, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

const formatDocType = (raw: string) =>
  raw
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
    .join(" ");

interface HistoryRecord {
  trace_id: string;
  filename: string;
  doc_type: string;
  decision: string;
  faithfulness: number;
  risk: string;
  created_at: string;
  feedback_rating: "positive" | "negative" | null;
}

const DECISION_COLORS: Record<string, string> = {
  APPROVED: "#15803d",
  REJECTED: "#b91c1c",
  ESCALATE: "#d97706",
};

function downloadReport(trace_id: string, filename: string) {
  const a = document.createElement("a");
  a.href = `${API_BASE}/api/history/${trace_id}/report`;
  a.download = `sentinel_report_${trace_id.slice(0, 8)}.pdf`;
  a.rel = "noopener noreferrer";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

interface Props {
  onReanalyze?: (traceId: string, filename: string) => void;
}

export function HistoryPanel({ onReanalyze }: Props) {
  const [records, setRecords] = useState<HistoryRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string>("");

  useEffect(() => {
    const controller = new AbortController();
    fetch(`${API_BASE}/api/history`, { method: "GET", signal: controller.signal })
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((data: unknown) => {
        setRecords(Array.isArray(data) ? (data as HistoryRecord[]) : []);
      })
      .catch((err: unknown) => {
        if ((err as Error).name === "AbortError") return;
        console.error("Failed to load history:", err);
        setFetchError("Failed to load history. Please try again.");
        setRecords([]);
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, []);

  return (
    <section style={{ marginTop: "24px" }}>
      <h2 style={{ color: "#e2e8f0", marginBottom: "16px" }}>Analysis History</h2>
      {fetchError && (
        <p role="alert" style={{ color: "#f87171", marginBottom: "8px" }}>{fetchError}</p>
      )}
      {loading ? (
        <p style={{ color: "#94a3b8" }}>Loading history…</p>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table
            style={{
              width: "100%",
              borderCollapse: "collapse",
              fontSize: "0.85rem",
              color: "#e2e8f0",
            }}
          >
            <thead>
              <tr style={{ borderBottom: "1px solid #334155" }}>
                <th style={thStyle}>Filename</th>
                <th style={thStyle}>Doc Type</th>
                <th style={thStyle}>Decision</th>
                <th style={thStyle}>Faithfulness</th>
                <th style={thStyle}>Risk</th>
                <th style={thStyle}>Date</th>
                <th style={thStyle}>Feedback</th>
                <th style={thStyle}>Report</th>
                <th style={thStyle}>Fresh</th>
              </tr>
            </thead>
            <tbody>
              {records.length === 0 ? (
                <tr>
                  <td colSpan={9} style={{ ...tdStyle, color: "#94a3b8", textAlign: "center", padding: "24px" }}>
                    No analyses recorded yet.
                  </td>
                </tr>
              ) : (
                records.map((r) => (
                  <tr key={r.trace_id} style={{ borderBottom: "1px solid #1e293b" }}>
                    <td style={tdStyle}>{r.filename}</td>
                    <td style={tdStyle}>{r.doc_type ? formatDocType(r.doc_type) : "—"}</td>
                    <td style={tdStyle}>
                      <span
                        style={{
                          color: "#fff",
                          background: DECISION_COLORS[r.decision] ?? "#475569",
                          padding: "2px 8px",
                          borderRadius: "4px",
                          fontWeight: 700,
                          fontSize: "0.75rem",
                        }}
                      >
                        {r.decision}
                      </span>
                    </td>
                    <td style={tdStyle}>{(r.faithfulness * 100).toFixed(0)}%</td>
                    <td style={{ ...tdStyle, textTransform: "capitalize" }}>{r.risk}</td>
                    <td style={tdStyle}>{new Date(r.created_at).toLocaleString()}</td>
                    <td style={{ ...tdStyle, textAlign: "center", fontSize: "1rem" }}>
                      {r.feedback_rating === "positive" ? "👍"
                        : r.feedback_rating === "negative" ? "👎"
                        : "—"}
                    </td>
                    <td style={tdStyle}>
                      <button
                        onClick={() => downloadReport(r.trace_id, r.filename)}
                        style={{
                          background: "none",
                          border: "1px solid #334155",
                          borderRadius: "4px",
                          color: "#38bdf8",
                          cursor: "pointer",
                          fontSize: "0.75rem",
                          padding: "3px 8px",
                        }}
                        title="Download compliance report PDF"
                      >
                        ↓ PDF
                      </button>
                    </td>
                    <td style={tdStyle}>
                      {onReanalyze && (
                        <button
                          onClick={() => onReanalyze(r.trace_id, r.filename)}
                          style={{
                            background: "none",
                            border: "1px solid #334155",
                            borderRadius: "4px",
                            color: "#94a3b8",
                            cursor: "pointer",
                            fontSize: "0.75rem",
                            padding: "3px 8px",
                          }}
                          title="Re-run fresh analysis on this document"
                        >
                          ↺ Fresh
                        </button>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

const thStyle: React.CSSProperties = {
  textAlign: "left",
  padding: "8px 12px",
  color: "#94a3b8",
  fontWeight: 600,
  fontSize: "0.75rem",
  textTransform: "uppercase",
  letterSpacing: "0.05em",
};

const tdStyle: React.CSSProperties = {
  padding: "8px 12px",
  verticalAlign: "middle",
};
