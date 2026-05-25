import { useEffect, useRef, useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

// ── Types ────────────────────────────────────────────────────────────────────

interface FeedbackStats {
  total: number;
  positive: number;
  negative: number;
  negative_rate_pct: number;
  direction?: {
    wrong_approvals: number;    // 👎 on APPROVED — potential missing rule
    wrong_rejections: number;   // 👎 on REJECTED — potential comprehension failure
    confirmed_approvals: number; // 👍 on APPROVED — system correct
    over_strict: number;        // 👍 on REJECTED — system may be too strict
  };
}

interface FeedbackEntry {
  trace_id: string;
  rating: "positive" | "negative";
  comment: string;
  created_at: string;
  filename: string | null;
  decision: string | null;
  doc_type: string | null;
}

interface Recommendation {
  rec_id: string;
  doc_type: string;
  rec_type: "missing_rule" | "comprehension_failure";
  proposed: string;
  evidence_count: number;
  confidence: "high" | "medium" | "low";
  rationale: string;
  status: "pending" | "approved" | "rejected" | "undone";
  created_at: string;
  resolved_at: string | null;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

const CONFIDENCE_COLORS: Record<string, string> = {
  high: "#15803d",
  medium: "#d97706",
  low: "#64748b",
};

function formatDocType(raw: string) {
  return raw.split("_").map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()).join(" ");
}

function proposedLabel(rec: Recommendation): string {
  try {
    const obj = JSON.parse(rec.proposed);
    if (typeof obj === "object" && obj !== null) {
      if (obj.clause && obj.failed_phrase) return `"${obj.failed_phrase}" → ${obj.clause}`;
      if (obj.name) return obj.name;
    }
  } catch {/* plain string */}
  return rec.proposed;
}

const chip = (label: string, color: string) => (
  <span style={{
    background: color + "22", color, border: `1px solid ${color}`,
    borderRadius: "4px", padding: "1px 7px", fontSize: "0.72rem", fontWeight: 700,
    letterSpacing: "0.04em",
  }}>{label}</span>
);

// ── Sub-components ───────────────────────────────────────────────────────────

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div style={{ background: "#1e293b", borderRadius: "10px", padding: "16px 20px", flex: 1, minWidth: "120px" }}>
      <div style={{ fontSize: "0.72rem", textTransform: "uppercase", letterSpacing: "0.06em", color: "#64748b", marginBottom: "6px", fontWeight: 600 }}>{label}</div>
      <div style={{ fontSize: "1.5rem", fontWeight: 700, color: "#f1f5f9" }}>{value}</div>
      {sub && <div style={{ fontSize: "0.75rem", color: "#64748b", marginTop: "2px" }}>{sub}</div>}
    </div>
  );
}

function RecCard({ rec, onAction }: { rec: Recommendation; onAction: () => void }) {
  const [loading, setLoading] = useState<string | null>(null);
  const [msg, setMsg] = useState("");

  const call = async (action: "approve" | "reject" | "undo") => {
    // Require confirmation before any destructive / irreversible action
    const confirmMessages: Record<typeof action, string> = {
      approve:
        rec.rec_type === "missing_rule"
          ? `Add "${proposedLabel(rec)}" as a required clause for ${formatDocType(rec.doc_type)}? All future analyses will check for this clause.`
          : `Apply this comprehension correction for ${formatDocType(rec.doc_type)}? The phrase will be injected into the compliance prompt.`,
      reject: `Reject this recommendation? It won't be suggested again for ${formatDocType(rec.doc_type)}.`,
      undo:
        rec.status === "approved"
          ? rec.rec_type === "missing_rule"
            ? `Remove "${proposedLabel(rec)}" from required clauses? This will revert the regulatory database change.`
            : `Remove this comprehension correction from the compliance prompt?`
          : `Re-open this rejected recommendation and move it back to Pending?`,
    };
    if (!window.confirm(confirmMessages[action])) return;

    setLoading(action);
    setMsg("");
    try {
      const res = await fetch(`${API_BASE}/api/admin/insights/${rec.rec_id}/${action}`, { method: "POST" });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        // 409 = duplicate clause already in DB — surface the server message directly
        setMsg(res.status === 409
          ? `⚠ ${err.detail || "Duplicate: this clause already exists in the regulatory database."}`
          : err.detail || `Error ${res.status}`
        );
      } else {
        const data = await res.json();
        if (data.action === "reopened") setMsg("↩ Re-opened — recommendation moved back to Pending.");
        else if (action === "approve") setMsg(
          rec.rec_type === "missing_rule"
            ? "✓ Clause added to regulatory_db.json — live for all future analyses."
            : "✓ Phrase added to compliance prompt — active immediately."
        );
        else if (action === "reject") setMsg("✗ Rejected — won't be suggested again.");
        else if (action === "undo") setMsg(
          rec.rec_type === "missing_rule"
            ? "↩ Clause removed from regulatory_db.json — change reversed."
            : "↩ Phrase removed from compliance prompt — change reversed."
        );
        onAction();
      }
    } catch {
      setMsg("Network error.");
    } finally {
      setLoading(null);
    }
  };

  const btnStyle = (bg: string, fg = "#fff"): React.CSSProperties => ({
    background: bg, border: "none", borderRadius: "6px", color: fg,
    padding: "5px 14px", fontWeight: 700, fontSize: "0.78rem", cursor: "pointer",
  });

  return (
    <div style={{ background: "#1e293b", borderRadius: "10px", padding: "16px 20px", marginBottom: "12px" }}>
      <div style={{ display: "flex", alignItems: "flex-start", gap: "12px", flexWrap: "wrap" }}>
        <div style={{ flex: 1 }}>
          <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", marginBottom: "6px", alignItems: "center" }}>
            <span style={{ fontWeight: 700, color: "#f1f5f9", fontSize: "0.9rem" }}>
              {formatDocType(rec.doc_type)}
            </span>
            {chip(rec.rec_type === "missing_rule" ? "Missing Rule" : "Comprehension", rec.rec_type === "missing_rule" ? "#2563eb" : "#7c3aed")}
            {chip(rec.confidence.charAt(0).toUpperCase() + rec.confidence.slice(1), CONFIDENCE_COLORS[rec.confidence])}
            <span style={{ color: "#64748b", fontSize: "0.75rem" }}>evidence: {rec.evidence_count}</span>
          </div>
          <div style={{ color: "#e2e8f0", fontSize: "0.85rem", marginBottom: "4px" }}>
            <strong>Proposed:</strong> {proposedLabel(rec)}
          </div>
          <div style={{ color: "#94a3b8", fontSize: "0.78rem" }}>{rec.rationale}</div>
        </div>
        <div style={{ display: "flex", gap: "8px", flexShrink: 0, alignItems: "center", flexWrap: "wrap" }}>
          {rec.status === "pending" && (
            <>
              <button onClick={() => call("approve")} disabled={!!loading} style={btnStyle("#15803d")}>
                {loading === "approve" ? "Applying…" : "✓ Approve"}
              </button>
              <button onClick={() => call("reject")} disabled={!!loading} style={btnStyle("#b91c1c")}>
                {loading === "reject" ? "Rejecting…" : "✗ Reject"}
              </button>
            </>
          )}
          {(rec.status === "approved" || rec.status === "rejected") && (
            <button onClick={() => call("undo")} disabled={!!loading}
              style={btnStyle("none", "#94a3b8") as React.CSSProperties}
              onMouseEnter={e => (e.currentTarget.style.color = "#e2e8f0")}
              onMouseLeave={e => (e.currentTarget.style.color = "#94a3b8")}
            >
              {loading === "undo" ? "Undoing…" : "↩ Undo"}
            </button>
          )}
        </div>
      </div>
      {msg && (
        <div style={{ marginTop: "8px", fontSize: "0.78rem", color: msg.startsWith("✓") ? "#4ade80" : msg.startsWith("↩") ? "#93c5fd" : "#f87171" }}>
          {msg}
        </div>
      )}
    </div>
  );
}

// ── Main Component ───────────────────────────────────────────────────────────

export function InsightsDashboard() {
  const [stats, setStats] = useState<FeedbackStats | null>(null);
  const [feedbackRows, setFeedbackRows] = useState<FeedbackEntry[]>([]);
  const [recs, setRecs] = useState<Recommendation[]>([]);
  const [reviewLog, setReviewLog] = useState<string[]>([]);
  const [reviewRunning, setReviewRunning] = useState(false);
  const [minEvidence, setMinEvidence] = useState(1);
  const [ignoringId, setIgnoringId] = useState<string | null>(null);
  const logRef = useRef<HTMLUListElement>(null);

  const loadData = async () => {
    try {
      const [metricsRes, fbRes, recsRes] = await Promise.all([
        fetch(`${API_BASE}/api/metrics/summary`),
        fetch(`${API_BASE}/api/feedback/summary`),
        fetch(`${API_BASE}/api/admin/insights/recommendations?status=all`),
      ]);
      if (metricsRes.ok) {
        const m = await metricsRes.json();
        setStats(m.feedback ?? null);
      }
      if (fbRes.ok) setFeedbackRows(await fbRes.json());
      if (recsRes.ok) setRecs(await recsRes.json());
    } catch { /* silent */ }
  };

  useEffect(() => { loadData(); }, []);

  // Scroll log to bottom on new entries
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [reviewLog]);

  const runReview = async () => {
    setReviewRunning(true);
    setReviewLog([]);
    try {
      const res = await fetch(
        `${API_BASE}/api/admin/insights/run-review?min_evidence=${minEvidence}`,
        { method: "POST" }
      );
      if (!res.ok || !res.body) {
        setReviewLog(["Error starting review agent."]);
        return;
      }
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let buf = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const parts = buf.split("\n\n");
        buf = parts.pop() ?? "";
        for (const part of parts) {
          const line = part.replace(/^data:\s*/, "").trim();
          if (!line) continue;
          try {
            const p = JSON.parse(line);
            setReviewLog((prev) => [...prev, p.message ?? line]);
            if (p.type === "done") await loadData(); // refresh recs
          } catch { setReviewLog((prev) => [...prev, line]); }
        }
      }
    } catch (e) {
      setReviewLog((prev) => [...prev, `Network error: ${(e as Error).message}`]);
    } finally {
      setReviewRunning(false);
    }
  };

  const ignoreFeedback = async (trace_id: string) => {
    if (!window.confirm("Ignore this feedback entry? It will be removed from the feedback log and won't be used by the Review Agent.")) return;
    setIgnoringId(trace_id);
    try {
      const res = await fetch(`${API_BASE}/api/feedback/${trace_id}/ignore`, { method: "POST" });
      if (res.ok) {
        // Remove from local state immediately
        setFeedbackRows((prev) => prev.filter((r) => r.trace_id !== trace_id));
        // Refresh stats since the count changed
        const metricsRes = await fetch(`${API_BASE}/api/metrics/summary`);
        if (metricsRes.ok) {
          const m = await metricsRes.json();
          setStats(m.feedback ?? null);
        }
      }
    } catch { /* silent */ } finally {
      setIgnoringId(null);
    }
  };

  const pending  = recs.filter((r) => r.status === "pending");
  const approved = recs.filter((r) => r.status === "approved");
  const rejected = recs.filter((r) => r.status === "rejected");
  const undone   = recs.filter((r) => r.status === "undone");

  const sectionHd: React.CSSProperties = {
    color: "#94a3b8", fontSize: "0.75rem", fontWeight: 600,
    textTransform: "uppercase", letterSpacing: "0.06em",
    margin: "24px 0 12px",
  };

  return (
    <section style={{ marginTop: "24px" }} aria-label="Insights Dashboard">
      <h2 style={{ color: "#e2e8f0", marginBottom: "20px" }}>AI Insights &amp; Feedback Loop</h2>

      {/* ── Section A: Stats ── */}
      <div style={{ display: "flex", gap: "12px", flexWrap: "wrap", marginBottom: "12px" }}>
        <StatCard label="Total Feedback" value={stats?.total ?? "—"} />
        <StatCard label="👍 Positive" value={stats?.positive ?? "—"} />
        <StatCard label="👎 Negative" value={stats?.negative ?? "—"} />
        <StatCard label="Negative Rate" value={stats ? `${stats.negative_rate_pct}%` : "—"} />
      </div>

      {/* ── Section A2: Direction breakdown ── */}
      {stats && (
        <div style={{ marginBottom: "28px" }}>
          <div style={{ fontSize: "0.72rem", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", color: "#64748b", marginBottom: "8px" }}>
            Feedback Direction
          </div>
          <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
            <div style={{ background: "#1e293b", borderRadius: "10px", padding: "12px 16px", flex: 1, minWidth: "160px", borderLeft: "3px solid #b91c1c" }}>
              <div style={{ fontSize: "0.68rem", textTransform: "uppercase", color: "#94a3b8", marginBottom: "4px", fontWeight: 600 }}>👎 Wrong Approvals</div>
              <div style={{ fontSize: "1.4rem", fontWeight: 700, color: "#f87171" }}>{stats.direction?.wrong_approvals ?? 0}</div>
              <div style={{ fontSize: "0.7rem", color: "#64748b", marginTop: "2px" }}>→ may need new rules</div>
            </div>
            <div style={{ background: "#1e293b", borderRadius: "10px", padding: "12px 16px", flex: 1, minWidth: "160px", borderLeft: "3px solid #d97706" }}>
              <div style={{ fontSize: "0.68rem", textTransform: "uppercase", color: "#94a3b8", marginBottom: "4px", fontWeight: 600 }}>👎 Wrong Rejections</div>
              <div style={{ fontSize: "1.4rem", fontWeight: 700, color: "#fbbf24" }}>{stats.direction?.wrong_rejections ?? 0}</div>
              <div style={{ fontSize: "0.7rem", color: "#64748b", marginTop: "2px" }}>→ comprehension failures</div>
            </div>
            <div style={{ background: "#1e293b", borderRadius: "10px", padding: "12px 16px", flex: 1, minWidth: "160px", borderLeft: "3px solid #d97706" }}>
              <div style={{ fontSize: "0.68rem", textTransform: "uppercase", color: "#94a3b8", marginBottom: "4px", fontWeight: 600 }}>👍 Over-Strict</div>
              <div style={{ fontSize: "1.4rem", fontWeight: 700, color: "#fbbf24" }}>{stats.direction?.over_strict ?? 0}</div>
              <div style={{ fontSize: "0.7rem", color: "#64748b", marginTop: "2px" }}>👍 on rejected — too strict</div>
            </div>
            <div style={{ background: "#1e293b", borderRadius: "10px", padding: "12px 16px", flex: 1, minWidth: "160px", borderLeft: "3px solid #15803d" }}>
              <div style={{ fontSize: "0.68rem", textTransform: "uppercase", color: "#94a3b8", marginBottom: "4px", fontWeight: 600 }}>👍 Confirmed Correct</div>
              <div style={{ fontSize: "1.4rem", fontWeight: 700, color: "#4ade80" }}>{stats.direction?.confirmed_approvals ?? 0}</div>
              <div style={{ fontSize: "0.7rem", color: "#64748b", marginTop: "2px" }}>👍 on approved — working</div>
            </div>
          </div>
        </div>
      )}

      {/* ── Section B: Feedback Detail Table ── */}
      <h3 style={sectionHd}>Feedback Details</h3>
      {feedbackRows.length === 0 ? (
        <p style={{ color: "#64748b", fontSize: "0.85rem" }}>No feedback yet — submit a 👎 on any analysis to seed the loop.</p>
      ) : (
        <div style={{ overflowX: "auto", marginBottom: "28px" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.82rem", color: "#e2e8f0" }}>
            <thead>
              <tr style={{ borderBottom: "1px solid #334155" }}>
                {["Rating", "Filename", "Decision", "Comment", "Date", ""].map((h) => (
                  <th key={h} scope="col" style={{ textAlign: "left", padding: "6px 10px", color: "#64748b", fontWeight: 600, fontSize: "0.72rem", textTransform: "uppercase", letterSpacing: "0.05em" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {feedbackRows.map((f, i) => (
                <tr key={i} style={{ borderBottom: "1px solid #1e293b" }}>
                  <td style={{ padding: "6px 10px", fontSize: "1rem" }}>{f.rating === "positive" ? "👍" : "👎"}</td>
                  <td style={{ padding: "6px 10px" }}>{f.filename ?? "—"}</td>
                  <td style={{ padding: "6px 10px" }}>{f.decision ?? "—"}</td>
                  <td style={{ padding: "6px 10px", color: "#94a3b8" }}>{f.comment || <em>no comment</em>}</td>
                  <td style={{ padding: "6px 10px", color: "#64748b" }}>{new Date(f.created_at).toLocaleDateString()}</td>
                  <td style={{ padding: "6px 10px" }}>
                    {f.rating === "negative" && (
                      <button
                        onClick={() => ignoreFeedback(f.trace_id)}
                        disabled={ignoringId === f.trace_id}
                        aria-label={`Ignore feedback for ${f.filename ?? f.trace_id}`}
                        title="Remove from feedback log — Review Agent won't use this entry"
                        style={{
                          background: "none", border: "1px solid #334155", borderRadius: "4px",
                          color: "#64748b", padding: "2px 8px", fontSize: "0.72rem",
                          cursor: ignoringId === f.trace_id ? "not-allowed" : "pointer",
                          fontWeight: 600,
                        }}
                      >
                        {ignoringId === f.trace_id ? "…" : "Ignore"}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Section C: Run Review Agent ── */}
      <h3 style={sectionHd}>AI Review Agent</h3>
      <div style={{ background: "#1e293b", borderRadius: "10px", padding: "20px", marginBottom: "28px" }}>
        <p style={{ color: "#94a3b8", fontSize: "0.85rem", margin: "0 0 14px" }}>
          Analyses accumulated feedback, identifies patterns, and proposes policy updates.
          No scheduling — runs on demand.
        </p>
        <div style={{ display: "flex", alignItems: "center", gap: "12px", flexWrap: "wrap", marginBottom: "14px" }}>
          <label style={{ color: "#94a3b8", fontSize: "0.82rem" }}>
            Min. evidence per doc type:&nbsp;
            <select
              value={minEvidence}
              onChange={(e) => setMinEvidence(Number(e.target.value))}
              aria-label="Minimum evidence threshold"
              style={{ background: "#0f172a", border: "1px solid #334155", borderRadius: "4px", color: "#e2e8f0", padding: "3px 8px", fontSize: "0.82rem" }}
            >
              {[1, 2, 3, 5, 10].map((v) => <option key={v} value={v}>{v}</option>)}
            </select>
          </label>
          <button
            onClick={runReview}
            disabled={reviewRunning}
            aria-label="Run review agent"
            style={{
              background: reviewRunning ? "#1e3a5f" : "#2563eb",
              border: "none", borderRadius: "8px", color: reviewRunning ? "#475569" : "#fff",
              padding: "8px 22px", fontWeight: 700, fontSize: "0.88rem",
              cursor: reviewRunning ? "not-allowed" : "pointer",
            }}
          >
            {reviewRunning ? "Running…" : "▶ Run Review Agent"}
          </button>
        </div>
        {reviewLog.length > 0 && (
          <ul
            ref={logRef}
            aria-label="Review agent log"
            style={{
              listStyle: "none", margin: 0, padding: "10px 14px",
              background: "#0f172a", borderRadius: "6px",
              fontFamily: "'Courier New', monospace", fontSize: "0.78rem",
              color: "#64748b", maxHeight: "220px", overflowY: "auto",
            }}
          >
            {reviewLog.map((line, i) => (
              <li key={i} style={{ color: line.startsWith("✓") || line.startsWith("→") ? "#4ade80" : line.startsWith("  →") ? "#93c5fd" : "#64748b" }}>
                {line}
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* ── Section D: Recommendations ── */}
      <h3 style={sectionHd}>Pending Recommendations ({pending.length})</h3>
      {pending.length === 0 ? (
        <p style={{ color: "#64748b", fontSize: "0.85rem", marginBottom: "20px" }}>No pending recommendations. Run the Review Agent to generate some.</p>
      ) : (
        pending.map((r) => <RecCard key={r.rec_id} rec={r} onAction={loadData} />)
      )}

      {approved.length > 0 && (
        <>
          <h3 style={sectionHd}>Approved ({approved.length})</h3>
          {approved.map((r) => <RecCard key={r.rec_id} rec={r} onAction={loadData} />)}
        </>
      )}

      {rejected.length > 0 && (
        <>
          <h3 style={sectionHd}>Rejected ({rejected.length})</h3>
          {rejected.map((r) => <RecCard key={r.rec_id} rec={r} onAction={loadData} />)}
        </>
      )}

      {undone.length > 0 && (
        <>
          <h3 style={sectionHd}>Undone ({undone.length})</h3>
          {undone.map((r) => (
            <div key={r.rec_id} style={{ background: "#1e293b", borderRadius: "10px", padding: "14px 20px", marginBottom: "10px", opacity: 0.6 }}>
              <span style={{ color: "#94a3b8", fontSize: "0.82rem" }}>
                ↩ {formatDocType(r.doc_type)} — {proposedLabel(r)} — reversed {r.resolved_at ? new Date(r.resolved_at).toLocaleDateString() : ""}
              </span>
            </div>
          ))}
        </>
      )}
    </section>
  );
}
