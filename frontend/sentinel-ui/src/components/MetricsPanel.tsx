import { useEffect, useState } from "react";

interface MetricsSummary {
  total: number;
  by_decision: Record<string, number>;
  avg_faithfulness: number;
  risk_distribution: { low: number; medium: number; high: number };
  daily_last_7_days: Record<string, number>;
}

const DECISION_COLORS: Record<string, string> = {
  APPROVED: "#15803d",
  REJECTED: "#b91c1c",
  ESCALATE: "#d97706",
  BLOCKED: "#7c3aed",
  PENDING: "#475569",
  UNKNOWN: "#334155",
};

const RISK_COLORS: Record<string, string> = {
  low: "#15803d",
  medium: "#d97706",
  high: "#b91c1c",
};

interface Props {
  apiBase: string;
}

export function MetricsPanel({ apiBase }: Props) {
  const [data, setData] = useState<MetricsSummary | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch(`${apiBase}/api/metrics/summary`)
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then(setData)
      .catch(() => setError("Could not load metrics."));
  }, [apiBase]);

  if (error) {
    return (
      <div role="alert" style={{ color: "#dc2626", padding: "16px" }}>
        {error}
      </div>
    );
  }

  if (!data) {
    return (
      <p aria-busy="true" style={{ color: "#94a3b8", padding: "16px" }}>
        Loading metrics…
      </p>
    );
  }

  const total = data.total || 1; // avoid divide-by-zero in bar widths

  return (
    <section
      aria-label="System metrics"
      style={{ padding: "24px", maxWidth: "720px" }}
    >
      <h2 style={{ color: "#e2e8f0", marginBottom: "24px" }}>System Metrics</h2>

      {/* Total count */}
      <div style={{ marginBottom: "24px" }}>
        <span
          style={{ fontSize: "2.5rem", fontWeight: 700, color: "#e2e8f0" }}
        >
          {data.total}
        </span>
        <span style={{ color: "#94a3b8", marginLeft: "8px", fontSize: "0.9rem" }}>
          total analyses
        </span>
      </div>

      {/* Decision breakdown */}
      <h3
        style={{
          color: "#94a3b8",
          fontSize: "0.78rem",
          textTransform: "uppercase",
          letterSpacing: "0.06em",
          marginBottom: "12px",
        }}
      >
        Decision Breakdown
      </h3>
      <dl style={{ marginBottom: "24px" }}>
        {Object.entries(data.by_decision).map(([decision, count]) => (
          <div
            key={decision}
            style={{ marginBottom: "8px", display: "flex", alignItems: "center", gap: "10px" }}
          >
            <dt
              style={{
                width: "100px",
                fontSize: "0.78rem",
                color: "#e2e8f0",
                fontWeight: 600,
                flexShrink: 0,
              }}
            >
              {decision}
            </dt>
            <dd style={{ flex: 1, margin: 0 }}>
              <div
                role="meter"
                aria-valuenow={count}
                aria-valuemin={0}
                aria-valuemax={data.total}
                aria-label={`${decision}: ${count} of ${data.total}`}
                style={{
                  width: `${Math.max(4, (count / total) * 100).toFixed(0)}%`,
                  background: DECISION_COLORS[decision] ?? "#475569",
                  height: "16px",
                  borderRadius: "4px",
                  minWidth: "4px",
                }}
              />
            </dd>
            <span style={{ width: "28px", textAlign: "right", color: "#94a3b8", fontSize: "0.82rem" }}>
              {count}
            </span>
          </div>
        ))}
      </dl>

      {/* Screen-reader table alternative */}
      <table
        aria-label="Decision breakdown"
        style={{
          position: "absolute",
          width: "1px",
          height: "1px",
          padding: 0,
          margin: "-1px",
          overflow: "hidden",
          clip: "rect(0,0,0,0)",
          whiteSpace: "nowrap",
          border: 0,
        }}
      >
        <caption>Decision breakdown</caption>
        <thead>
          <tr>
            <th scope="col">Decision</th>
            <th scope="col">Count</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(data.by_decision).map(([d, c]) => (
            <tr key={d}>
              <td>{d}</td>
              <td>{c}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Faithfulness */}
      <h3
        style={{
          color: "#94a3b8",
          fontSize: "0.78rem",
          textTransform: "uppercase",
          letterSpacing: "0.06em",
          marginBottom: "8px",
        }}
      >
        Average Faithfulness
      </h3>
      <p
        aria-label={`Average faithfulness: ${(data.avg_faithfulness * 100).toFixed(0)} percent`}
        style={{ marginBottom: "24px" }}
      >
        <strong style={{ fontSize: "1.8rem", color: "#e2e8f0" }}>
          {(data.avg_faithfulness * 100).toFixed(0)}%
        </strong>
      </p>

      {/* Risk distribution */}
      <h3
        style={{
          color: "#94a3b8",
          fontSize: "0.78rem",
          textTransform: "uppercase",
          letterSpacing: "0.06em",
          marginBottom: "12px",
        }}
      >
        Hallucination Risk Distribution
      </h3>
      <div style={{ display: "flex", gap: "12px", marginBottom: "24px" }}>
        {(["low", "medium", "high"] as const).map((level) => (
          <div
            key={level}
            style={{
              padding: "10px 18px",
              borderRadius: "8px",
              background: "#1e293b",
              border: `1px solid ${RISK_COLORS[level]}`,
              textAlign: "center",
              minWidth: "72px",
            }}
          >
            <div
              style={{
                fontSize: "1.4rem",
                fontWeight: 700,
                color: RISK_COLORS[level],
              }}
            >
              {data.risk_distribution[level]}
            </div>
            <div
              style={{
                fontSize: "0.72rem",
                color: "#94a3b8",
                textTransform: "capitalize",
                marginTop: "2px",
              }}
            >
              {level}
            </div>
          </div>
        ))}
      </div>

      {/* 7-day trend */}
      {Object.keys(data.daily_last_7_days).length > 0 && (
        <>
          <h3
            style={{
              color: "#94a3b8",
              fontSize: "0.78rem",
              textTransform: "uppercase",
              letterSpacing: "0.06em",
              marginBottom: "12px",
            }}
          >
            7-Day Trend
          </h3>
          <div
            aria-label="7-day analysis trend"
            style={{ display: "flex", alignItems: "flex-end", gap: "6px", height: "60px" }}
          >
            {Object.entries(data.daily_last_7_days).map(([day, count]) => {
              const maxCount = Math.max(...Object.values(data.daily_last_7_days), 1);
              const heightPct = (count / maxCount) * 100;
              return (
                <div
                  key={day}
                  title={`${day}: ${count}`}
                  aria-label={`${day}: ${count} analyses`}
                  style={{
                    flex: 1,
                    height: `${Math.max(8, heightPct)}%`,
                    background: "#2563eb",
                    borderRadius: "3px 3px 0 0",
                  }}
                />
              );
            })}
          </div>
        </>
      )}
    </section>
  );
}
