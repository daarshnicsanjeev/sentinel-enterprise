import { DragEvent, KeyboardEvent, useEffect, useRef, useState } from "react";

const STORAGE_KEY = "sentinel_batch_job";

interface JobResult {
  filename: string;
  final_decision: string;
  evaluation_score: number;
  trace_id?: string;
  from_cache?: boolean;
  sanitized?: boolean;
  can_reanalyze?: boolean;
  error?: string;
}

interface JobStatus {
  job_id: string;
  status: "pending" | "running" | "completed" | "failed";
  total: number;
  completed: number;
  results: JobResult[];
}

const DECISION_COLORS: Record<string, string> = {
  APPROVED: "#15803d",
  REJECTED: "#b91c1c",
  ESCALATE: "#d97706",
  BLOCKED: "#7c3aed",
  UNKNOWN: "#475569",
};

function effectiveDecision(r: JobResult): string {
  return r.sanitized === false ? "BLOCKED" : r.final_decision;
}

interface Props {
  apiBase: string;
}

export function BatchUpload({ apiBase }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [job, setJob] = useState<JobStatus | null>(null);
  const [error, setError] = useState("");
  const [polling, setPolling] = useState(false);
  const [selectedRows, setSelectedRows] = useState<Set<number>>(new Set());

  // Silently resume an in-progress job from localStorage on mount
  useEffect(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (!saved) return;
    try {
      const parsed: { job_id: string; total: number } = JSON.parse(saved);
      if (parsed.job_id) startPolling(parsed.job_id);
    } catch {
      localStorage.removeItem(STORAGE_KEY);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, []);

  const startPolling = (jobId: string) => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    setPolling(true);
    intervalRef.current = setInterval(async () => {
      try {
        const r = await fetch(`${apiBase}/api/jobs/${jobId}`);
        if (!r.ok) return;
        const data: JobStatus = await r.json();
        setJob(data);
        if (data.status === "completed" || data.status === "failed") {
          clearInterval(intervalRef.current!);
          setPolling(false);
          localStorage.removeItem(STORAGE_KEY);
        }
      } catch {
        clearInterval(intervalRef.current!);
        setPolling(false);
      }
    }, 3000);
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) { setSelectedFile(file); handleSubmit(file); }
  };

  const handleSubmit = async (fileArg?: File) => {
    const file = fileArg ?? selectedFile;
    if (!file || polling) return;

    setError("");
    setJob(null);
    setSelectedRows(new Set());

    const formData = new FormData();
    formData.append("file", file);

    let resp: Response;
    try {
      resp = await fetch(`${apiBase}/api/analyze/batch`, { method: "POST", body: formData });
    } catch {
      setError("Network error — could not submit batch.");
      return;
    }

    if (!resp.ok) {
      const body = await resp.json().catch(() => ({}));
      setError((body as { detail?: string }).detail ?? `Server error ${resp.status}`);
      return;
    }

    const created: { job_id: string; total: number } = await resp.json();
    localStorage.setItem(STORAGE_KEY, JSON.stringify(created));
    setJob({ job_id: created.job_id, status: "pending", total: created.total, completed: 0, results: [] });
    startPolling(created.job_id);
  };

  const handleClear = () => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    setPolling(false);
    setJob(null);
    setError("");
    setSelectedFile(null);
    setSelectedRows(new Set());
    localStorage.removeItem(STORAGE_KEY);
  };

  // Row selection
  // A row is selectable only when it has a trace_id, no error, AND raw_text is stored on the server
  const selectableIndices = (job?.results ?? [])
    .map((r, i) => (!r.error && r.trace_id && r.can_reanalyze !== false ? i : -1))
    .filter((i) => i >= 0);

  const allSelected =
    selectableIndices.length > 0 && selectableIndices.every((i) => selectedRows.has(i));

  const toggleSelectAll = () =>
    setSelectedRows(allSelected ? new Set() : new Set(selectableIndices));

  const toggleRow = (i: number) =>
    setSelectedRows((prev) => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i); else next.add(i);
      return next;
    });

  const handleReanalyzeSelected = async () => {
    if (!job || selectedRows.size === 0 || polling) return;
    const traceIds = [...selectedRows]
      .map((i) => job.results[i]?.trace_id)
      .filter(Boolean) as string[];
    if (traceIds.length === 0) return;

    setError("");
    setSelectedRows(new Set());

    let resp: Response;
    try {
      resp = await fetch(`${apiBase}/api/analyze/batch-reanalyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ trace_ids: traceIds }),
      });
    } catch {
      setError("Network error — could not submit re-analysis.");
      return;
    }

    if (!resp.ok) {
      const body = await resp.json().catch(() => ({}));
      setError((body as { detail?: string }).detail ?? `Server error ${resp.status}`);
      return;
    }

    const created: { job_id: string; total: number } = await resp.json();
    localStorage.setItem(STORAGE_KEY, JSON.stringify(created));
    setJob({ job_id: created.job_id, status: "pending", total: created.total, completed: 0, results: [] });
    startPolling(created.job_id);
  };

  const progressPct = job && job.total > 0 ? (job.completed / job.total) * 100 : 0;
  const isRunning = polling || job?.status === "running" || job?.status === "pending";

  return (
    <section aria-label="Batch document analysis" style={{ maxWidth: "760px" }}>
      <h2 style={{ color: "#e2e8f0", marginBottom: "4px" }}>Batch Analysis</h2>
      <p style={{ color: "#94a3b8", fontSize: "0.85rem", marginBottom: "20px" }}>
        Analyse up to 50 documents at once. Upload a ZIP file — results update as each document finishes.
      </p>

      {/* Upload zone — same accessible pattern as single-upload */}
      {!job && (
        <>
          {/* Visually hidden file input — NOT display:none so assistive tech can still reach it via its label */}
          <input
            id="batch-zip-input"
            ref={inputRef}
            type="file"
            accept=".zip,application/zip,application/x-zip-compressed,application/octet-stream"
            style={{
              position: "absolute",
              width: "1px",
              height: "1px",
              padding: 0,
              margin: "-1px",
              overflow: "hidden",
              clip: "rect(0,0,0,0)",
              whiteSpace: "nowrap",
              borderWidth: 0,
            }}
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) { setSelectedFile(f); handleSubmit(f); }
            }}
            disabled={polling}
          />

          {/* Drop zone — role="button" so JAWS announces it as interactive */}
          <div
            role="button"
            tabIndex={0}
            aria-label={
              selectedFile
                ? `Selected file: ${selectedFile.name}, ${(selectedFile.size / 1024 / 1024).toFixed(1)} MB. Analysis starting. Press Enter to choose a different file.`
                : "Upload ZIP file for batch analysis — click or drag and drop. Supported formats: PDF, Word, Excel, PowerPoint, HTML, plain text, and images."
            }
            aria-disabled={polling}
            onDrop={handleDrop}
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onClick={() => !polling && inputRef.current?.click()}
            onKeyDown={(e: KeyboardEvent<HTMLDivElement>) => {
              if ((e.key === "Enter" || e.key === " ") && !polling) {
                e.preventDefault();
                inputRef.current?.click();
              }
            }}
            style={{
              border: `2px dashed ${dragging ? "#2563eb" : "#475569"}`,
              borderRadius: "12px",
              padding: "36px 24px",
              textAlign: "center",
              cursor: polling ? "not-allowed" : "pointer",
              background: dragging ? "#1e3a5f" : "#0f172a",
              transition: "border-color 0.2s, background 0.2s",
              userSelect: "none",
              opacity: polling ? 0.5 : 1,
            }}
          >
            {selectedFile ? (
              <>
                <div style={{ fontSize: "2rem", marginBottom: "6px" }} aria-hidden="true">📦</div>
                <p style={{ margin: 0, color: "#e2e8f0", fontWeight: 600, fontSize: "0.95rem" }}>
                  {selectedFile.name}
                </p>
                <p style={{ margin: "4px 0 0", color: "#64748b", fontSize: "0.8rem" }}>
                  {(selectedFile.size / 1024 / 1024).toFixed(1)} MB — starting analysis…
                </p>
              </>
            ) : (
              <>
                <div style={{ fontSize: "2.5rem", marginBottom: "8px" }} aria-hidden="true">📦</div>
                <p style={{ margin: 0, color: "#cbd5e1", fontWeight: 500 }}>
                  Drag &amp; drop a ZIP file here, or click to browse
                </p>
                <p style={{ margin: "4px 0 0", color: "#475569", fontSize: "0.8rem" }}>
                  PDF, TXT, DOCX, XLSX, PPTX, HTML, PNG, JPG, TIFF &middot; max 50 MB &middot; up to 50 files
                </p>
              </>
            )}
          </div>
        </>
      )}

      {error && (
        <div role="alert" style={{ color: "#dc2626", marginTop: "12px", fontSize: "0.85rem" }}>
          {error}
        </div>
      )}

      {/* Progress + results */}
      {job && (
        <div>
          {/* Status bar */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px" }}>
            <p aria-live="polite" style={{ margin: 0, color: "#94a3b8", fontSize: "0.85rem" }}>
              {job.status === "completed"
                ? `✓ Completed — ${job.completed} / ${job.total} documents`
                : `Processing: ${job.completed} / ${job.total} documents…`}
            </p>
            {!isRunning && (
              <button
                onClick={handleClear}
                style={{ padding: "4px 12px", borderRadius: "6px", border: "1px solid #334155", background: "none", color: "#64748b", cursor: "pointer", fontSize: "0.78rem" }}
              >
                New Batch
              </button>
            )}
          </div>

          {/* Progress bar */}
          {isRunning && (
            <div
              role="progressbar"
              aria-valuenow={job.completed}
              aria-valuemin={0}
              aria-valuemax={job.total}
              aria-label={`Batch processing: ${job.completed} of ${job.total} documents`}
              style={{ background: "#1e293b", borderRadius: "6px", height: "8px", overflow: "hidden", marginBottom: "16px" }}
            >
              <div style={{ width: `${progressPct}%`, background: "#2563eb", height: "100%", borderRadius: "6px", transition: "width 0.4s ease" }} />
            </div>
          )}

          {/* Re-analyse toolbar */}
          {!isRunning && selectableIndices.length > 0 && (
            <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "10px" }}>
              <button
                onClick={handleReanalyzeSelected}
                disabled={selectedRows.size === 0}
                aria-label={selectedRows.size > 0 ? `Re-analyse selected (${selectedRows.size})` : "Re-analyse selected — select rows first"}
                style={{
                  padding: "6px 16px", borderRadius: "7px", border: "none",
                  background: selectedRows.size > 0 ? "#2563eb" : "#1e293b",
                  color: selectedRows.size > 0 ? "#fff" : "#475569",
                  fontWeight: 700, cursor: selectedRows.size > 0 ? "pointer" : "not-allowed",
                  fontSize: "0.82rem", transition: "background 0.2s, color 0.2s",
                }}
              >
                ↺ Re-analyse Selected{selectedRows.size > 0 ? ` (${selectedRows.size})` : ""}
              </button>
              {selectedRows.size > 0 && (
                <button
                  onClick={() => setSelectedRows(new Set())}
                  style={{ padding: "6px 10px", borderRadius: "7px", border: "1px solid #334155", background: "none", color: "#64748b", cursor: "pointer", fontSize: "0.78rem" }}
                >
                  Clear selection
                </button>
              )}
            </div>
          )}

          {/* Results table */}
          {(job.results?.length ?? 0) > 0 && (
            <div style={{ overflowX: "auto" }}>
              <table
                aria-label="Batch results"
                style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.82rem", color: "#e2e8f0" }}
              >
                <caption style={{ display: "none" }}>Batch results</caption>
                <thead>
                  <tr style={{ borderBottom: "1px solid #334155" }}>
                    <th scope="col" style={{ ...thStyle, width: "36px", padding: "8px 8px" }}>
                      {!isRunning && selectableIndices.length > 0 && (
                        <input
                          type="checkbox"
                          checked={allSelected}
                          onChange={toggleSelectAll}
                          aria-label="Select all"
                          title="Select all rows"
                          style={{ cursor: "pointer", accentColor: "#2563eb" }}
                        />
                      )}
                    </th>
                    <th scope="col" style={thStyle}>Filename</th>
                    <th scope="col" style={thStyle}>Decision</th>
                    <th scope="col" style={thStyle}>Faithfulness</th>
                    <th scope="col" style={thStyle}>Source</th>
                    <th scope="col" style={thStyle}>Report</th>
                  </tr>
                </thead>
                <tbody>
                  {job.results.map((r, i) => {
                    const decision = effectiveDecision(r);
                    const selectable = !r.error && !!r.trace_id && r.can_reanalyze !== false;
                    const shortName = r.filename.split("/").pop() ?? r.filename;
                    return (
                      <tr
                        key={i}
                        style={{
                          borderBottom: "1px solid #1e293b",
                          background: selectedRows.has(i) ? "rgba(37,99,235,0.08)" : "transparent",
                        }}
                      >
                        <td style={{ ...tdStyle, padding: "8px 8px" }}>
                          {!isRunning && !r.error && r.trace_id && (
                            selectable ? (
                              <input
                                type="checkbox"
                                checked={selectedRows.has(i)}
                                onChange={() => toggleRow(i)}
                                aria-label={shortName}
                                title={`Select ${shortName} for re-analysis`}
                                style={{ cursor: "pointer", accentColor: "#2563eb" }}
                              />
                            ) : (
                              <span
                                title="Re-analysis unavailable — re-upload the ZIP to refresh this document"
                                aria-label={`Re-analysis unavailable for ${shortName}`}
                                style={{ color: "#334155", fontSize: "0.8rem", cursor: "help" }}
                              >
                                —
                              </span>
                            )
                          )}
                        </td>
                        <td style={tdStyle} title={r.filename}>
                          {shortName}
                        </td>
                        <td style={tdStyle}>
                          {r.error ? (
                            <span style={{ color: "#f87171", fontSize: "0.75rem" }}>Error</span>
                          ) : (
                            <span style={{ background: DECISION_COLORS[decision] ?? "#475569", color: "#fff", padding: "2px 8px", borderRadius: "4px", fontWeight: 700, fontSize: "0.72rem" }}>
                              {decision}
                            </span>
                          )}
                        </td>
                        <td style={tdStyle}>{r.error ? "—" : `${(r.evaluation_score * 100).toFixed(0)}%`}</td>
                        <td style={tdStyle}>
                          {r.from_cache ? (
                            <span style={{
                              background: "#1e3a5f", color: "#93c5fd",
                              border: "1px solid #2563eb", borderRadius: "6px",
                              padding: "2px 8px", fontSize: "0.72rem", fontWeight: 600,
                              letterSpacing: "0.04em", whiteSpace: "nowrap",
                            }}>⚡ Cached</span>
                          ) : (
                            <span style={{
                              background: "#14532d", color: "#86efac",
                              border: "1px solid #15803d", borderRadius: "6px",
                              padding: "2px 8px", fontSize: "0.72rem", fontWeight: 600,
                              letterSpacing: "0.04em", whiteSpace: "nowrap",
                            }}>✓ Fresh</span>
                          )}
                        </td>
                        <td style={tdStyle}>
                          {r.trace_id && !r.error ? (
                            <button
                              onClick={() => window.open(`${apiBase}/api/history/${r.trace_id}/report/html`, "_blank", "noopener,noreferrer")}
                              aria-label={`View HTML compliance report for ${shortName}`}
                              style={{ background: "none", border: "1px solid #334155", borderRadius: "4px", color: "#38bdf8", cursor: "pointer", fontSize: "0.75rem", padding: "2px 8px", whiteSpace: "nowrap" }}
                            >
                              View Report ↗
                            </button>
                          ) : (
                            <span style={{ color: "#475569", fontSize: "0.75rem" }}>—</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </section>
  );
}

const thStyle: React.CSSProperties = {
  textAlign: "left",
  padding: "8px 10px",
  color: "#94a3b8",
  fontWeight: 600,
  fontSize: "0.75rem",
  textTransform: "uppercase",
  letterSpacing: "0.05em",
};

const tdStyle: React.CSSProperties = {
  padding: "8px 10px",
  verticalAlign: "middle",
};
