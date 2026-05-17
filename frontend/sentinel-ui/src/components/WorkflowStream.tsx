import { useEffect, useRef } from "react";

interface LogEntry {
  node: string;
  message: string;
}

const NODE_COLORS: Record<string, string> = {
  guardrail: "#7c3aed",
  router: "#2563eb",
  compliance: "#d97706",
  increment_retry: "#b45309",
  evaluator: "#059669",
};

interface Props {
  logs: LogEntry[];
  streaming: boolean;
}

export function WorkflowStream({ logs, streaming }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  return (
    <div
      style={{
        background: "#0f172a",
        borderRadius: "12px",
        padding: "20px",
        minHeight: "200px",
        maxHeight: "420px",
        overflowY: "auto",
        fontFamily: "'Courier New', monospace",
        fontSize: "0.82rem",
        lineHeight: 1.7,
      }}
      aria-live="polite"
      aria-atomic="false"
      aria-label="Agent workflow log stream"
    >
      {logs.length === 0 && (
        <p style={{ color: "#475569", margin: 0 }}>
          {streaming ? "Initialising pipeline..." : "Upload a document to begin analysis."}
        </p>
      )}
      <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
        {logs.map((entry, i) => {
          const color = NODE_COLORS[entry.node] ?? "#94a3b8";
          return (
            <li key={i} style={{ display: "flex", gap: "8px", alignItems: "flex-start", marginBottom: "2px" }}>
              <span style={{
                color,
                flexShrink: 0,
                fontWeight: 700,
                fontSize: "0.7rem",
                border: `1px solid ${color}`,
                borderRadius: "4px",
                padding: "0 4px",
                lineHeight: "1.6",
                letterSpacing: "0.03em",
              }}>
                {entry.node.toUpperCase()}
              </span>
              <span style={{ color: "#e2e8f0" }}>{entry.message}</span>
            </li>
          );
        })}
      </ul>
      {streaming && (
        <div style={{ color: "#475569", display: "flex", gap: "6px", alignItems: "center", marginTop: "4px" }}>
          <span className="blink">█</span>
          <span>Processing…</span>
        </div>
      )}
      <div ref={bottomRef} />
    </div>
  );
}
