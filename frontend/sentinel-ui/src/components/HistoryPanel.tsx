import { useEffect, useState } from "react";

interface HistoryRecord {
  trace_id: string;
  filename: string;
  doc_type: string;
  decision: string;
  faithfulness: number;
  risk: string;
  created_at: string;
}

const DECISION_COLORS: Record<string, string> = {
  APPROVED: "#15803d",
  REJECTED: "#b91c1c",
};

export function HistoryPanel() {
  const [records, setRecords] = useState<HistoryRecord[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/history", { method: "GET" })
      .then((r) => r.json())
      .then((data: HistoryRecord[]) => setRecords(data))
      .catch(() => setRecords([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <section style={{ marginTop: "24px" }}>
      <h2 style={{ color: "#e2e8f0", marginBottom: "16px" }}>Analysis History</h2>
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
              </tr>
            </thead>
            <tbody>
              {records.length === 0 ? (
                <tr>
                  <td colSpan={6} style={{ ...tdStyle, color: "#94a3b8", textAlign: "center", padding: "24px" }}>
                    No analyses recorded yet.
                  </td>
                </tr>
              ) : (
                records.map((r) => (
                  <tr key={r.trace_id} style={{ borderBottom: "1px solid #1e293b" }}>
                    <td style={tdStyle}>{r.filename}</td>
                    <td style={tdStyle}>{r.doc_type}</td>
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
