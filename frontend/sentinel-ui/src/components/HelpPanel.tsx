const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ""

// ─── Styled primitives ────────────────────────────────────────────────────────

const H2: React.CSSProperties = {
  color: "#e2e8f0",
  fontSize: "1.35rem",
  fontWeight: 700,
  marginBottom: "20px",
  marginTop: 0,
}

const H3: React.CSSProperties = {
  color: "#94a3b8",
  fontSize: "0.78rem",
  fontWeight: 700,
  textTransform: "uppercase" as const,
  letterSpacing: "0.07em",
  marginBottom: "12px",
  marginTop: "32px",
  paddingBottom: "6px",
  borderBottom: "1px solid #1e293b",
}

const P: React.CSSProperties = {
  color: "#cbd5e1",
  fontSize: "0.9rem",
  lineHeight: 1.7,
  marginBottom: "12px",
  marginTop: 0,
}

const TABLE: React.CSSProperties = {
  width: "100%",
  borderCollapse: "collapse" as const,
  fontSize: "0.85rem",
  marginBottom: "8px",
}

const TH: React.CSSProperties = {
  textAlign: "left" as const,
  padding: "7px 12px",
  color: "#64748b",
  fontWeight: 600,
  fontSize: "0.75rem",
  textTransform: "uppercase" as const,
  letterSpacing: "0.04em",
  borderBottom: "1px solid #1e293b",
}

const TD: React.CSSProperties = {
  padding: "8px 12px",
  color: "#e2e8f0",
  borderBottom: "1px solid #0f172a",
  verticalAlign: "top",
}

const TDmuted: React.CSSProperties = { ...TD, color: "#94a3b8", fontSize: "0.82rem" }

// ─── Sample document catalogue ────────────────────────────────────────────────

interface Sample {
  file: string
  type: string
  expected: string
  note: string
}

const QUICK_START: Sample[] = [
  { file: "credit_agreement_valid.txt",                                            type: "Credit Agreement",    expected: "APPROVED",        note: "All required clauses present — straightforward approval" },
  { file: "contract_missing_clause.txt",                                           type: "Legal Contract",      expected: "REJECTED",        note: "Missing clauses — good first rejection example" },
  { file: "credit_agreement_syndicated_loan_500M_ESCALATE.txt",                    type: "Credit Agreement",    expected: "ESCALATE",        note: "$500 M syndicated loan — triggers human-review escalation" },
  { file: "guardrail_prompt_injection_attempt_BLOCKED.txt",                        type: "Security Test",       expected: "BLOCKED",         note: "Prompt injection — blocked by guardrail before LLM" },
  { file: "credit_agreement_duplicate_resubmission_tests_dedup_cache.txt",         type: "Credit Agreement",    expected: "APPROVED (cached)", note: "Upload twice — second result returns instantly from cache" },
]

const BY_TYPE: Sample[] = [
  { file: "legal_contract_nda_all_clauses_APPROVED.txt",                           type: "Legal Contract",      expected: "APPROVED", note: "Non-disclosure agreement, all clauses" },
  { file: "regulatory_filing_sec_10k_annual_report_complete_APPROVED.txt",         type: "Regulatory Filing",   expected: "APPROVED", note: "SEC 10-K annual report, complete" },
  { file: "employment_contract_executive_cto_all_clauses_APPROVED.txt",            type: "Employment Contract", expected: "APPROVED", note: "CTO executive contract, all clauses" },
  { file: "insurance_policy_cyber_liability_complete_APPROVED.txt",                type: "Insurance Policy",    expected: "APPROVED", note: "Cyber liability policy, complete" },
  { file: "partnership_agreement_jv_technology_all_clauses_APPROVED.txt",          type: "Partnership Agreement", expected: "APPROVED", note: "Technology JV, all clauses" },
]

const MISSING_CLAUSES: Sample[] = [
  { file: "employment_contract_missing_ip_assignment_REJECTED.txt",                type: "Employment Contract", expected: "REJECTED", note: "No IP assignment clause" },
  { file: "partnership_agreement_missing_dissolution_clause_REJECTED.txt",         type: "Partnership Agreement", expected: "REJECTED", note: "No dissolution clause" },
  { file: "regulatory_filing_missing_risk_factors_and_auditor_REJECTED.txt",       type: "Regulatory Filing",   expected: "REJECTED", note: "Missing risk factors and auditor sign-off" },
  { file: "insurance_policy_directors_officers_missing_claims_procedure_REJECTED.txt", type: "Insurance Policy", expected: "REJECTED", note: "D&O policy — no claims procedure" },
]

// Regulatory profile is AUTO-DETECTED from document keywords — no manual selection needed.
// These documents contain GDPR / SOX language that triggers the correct profile automatically.
const REG_PROFILES: Sample[] = [
  { file: "regulatory_filing_gdpr_data_processing_eu_tenant_APPROVED.txt",         type: "Regulatory Filing",   expected: "APPROVED", note: "GDPR language → EU profile auto-detected" },
  { file: "regulatory_filing_sec_10k_us_tenant_sox_certification_APPROVED.txt",    type: "Regulatory Filing",   expected: "APPROVED", note: "SOX / SEC language → US profile auto-detected" },
]

const ALT_FORMATS: Sample[] = [
  { file: "credit_agreement_valid.pdf",                                             type: "Credit Agreement",    expected: "APPROVED", note: "PDF format" },
  { file: "employment_contract_ceo_word_format_all_clauses_APPROVED.docx",         type: "Employment Contract", expected: "APPROVED", note: "Microsoft Word (.docx)" },
  { file: "legal_contract_html_format_nda_APPROVED.html",                          type: "Legal Contract",      expected: "APPROVED", note: "HTML format" },
  { file: "credit_agreement_png_clean_scan_APPROVED.png",                          type: "Credit Agreement",    expected: "APPROVED", note: "PNG scan — extracted by OCR" },
]

const GUARDRAILS: Sample[] = [
  { file: "guardrail_pii_ssn_and_credit_card_BLOCKED.txt",                         type: "Security Test", expected: "BLOCKED", note: "SSN + credit card numbers" },
  { file: "guardrail_pii_passport_iban_swift_BLOCKED.txt",                         type: "Security Test", expected: "BLOCKED", note: "Passport, IBAN, SWIFT codes" },
  { file: "guardrail_jailbreak_dan_roleplay_BLOCKED.txt",                          type: "Security Test", expected: "BLOCKED", note: "DAN / roleplay jailbreak attempt" },
  { file: "guardrail_sql_injection_attempt_BLOCKED.txt",                           type: "Security Test", expected: "BLOCKED", note: "SQL injection patterns" },
]

const FEEDBACK_LOOP: Sample[] = [
  { file: "fl_test_s1_nda_all_current_clauses_APPROVED.txt",                       type: "Legal Contract",      expected: "APPROVED", note: "S1 trigger — NDA missing data breach notification clause" },
  { file: "fl_test_s1_nda_with_breach_notice_APPROVED.txt",                        type: "Legal Contract",      expected: "APPROVED", note: "S1 verify — same NDA with breach notice clause added" },
  { file: "fl_test_s2_credit_unusual_phrasing_REJECTED_before_fix.txt",            type: "Credit Agreement",    expected: "REJECTED", note: "S2 — all 4 clauses present but LLM misses non-standard headings" },
  { file: "fl_test_s3_employment_all_current_clauses_APPROVED.txt",                type: "Employment Contract", expected: "APPROVED", note: "S3 trigger — employment contract missing remote work policy" },
  { file: "fl_test_s3_employment_with_remote_work_APPROVED.txt",                   type: "Employment Contract", expected: "APPROVED", note: "S3 verify — same contract with remote work clause added" },
]

// ─── Sub-components ───────────────────────────────────────────────────────────

const decisionBadge = (d: string) => {
  const colors: Record<string, string> = {
    APPROVED: "#15803d",
    REJECTED: "#b91c1c",
    ESCALATE: "#b45309",
    BLOCKED:  "#6d28d9",
  }
  const text = d.split(" ")[0] // strip "(cached)" etc.
  const bg = colors[text] ?? "#475569"
  return (
    <span style={{ background: bg, color: "#fff", padding: "2px 8px", borderRadius: "4px", fontSize: "0.72rem", fontWeight: 700, whiteSpace: "nowrap" as const }}>
      {d}
    </span>
  )
}

function SampleTable({ samples }: { samples: Sample[] }) {
  return (
    <div style={{ overflowX: "auto", marginBottom: "4px" }}>
      <table style={TABLE}>
        <thead>
          <tr>
            <th style={TH}>File</th>
            <th style={TH}>Type</th>
            <th style={TH}>Expected</th>
            <th style={TH}>Notes</th>
            <th style={{ ...TH, textAlign: "center" as const }}>Download</th>
          </tr>
        </thead>
        <tbody>
          {samples.map((s) => (
            <tr key={s.file}>
              <td style={{ ...TDmuted, fontFamily: "'Courier New', monospace", fontSize: "0.78rem" }}>{s.file}</td>
              <td style={TDmuted}>{s.type}</td>
              <td style={{ ...TD, whiteSpace: "nowrap" as const }}>{decisionBadge(s.expected)}</td>
              <td style={TDmuted}>{s.note}</td>
              <td style={{ ...TD, textAlign: "center" as const }}>
                <a
                  href={`${API_BASE}/api/samples/${encodeURIComponent(s.file)}`}
                  download={s.file}
                  style={{
                    display: "inline-block",
                    padding: "4px 12px",
                    background: "#1e293b",
                    color: "#94a3b8",
                    borderRadius: "6px",
                    fontSize: "0.78rem",
                    textDecoration: "none",
                    border: "1px solid #334155",
                    cursor: "pointer",
                  }}
                  aria-label={`Download ${s.file}`}
                >
                  ↓ Download
                </a>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ─── Info callout ─────────────────────────────────────────────────────────────

function InfoBox({ children }: { children: React.ReactNode }) {
  return (
    <div style={{
      background: "#0f1f3d",
      border: "1px solid #1e40af",
      borderRadius: "8px",
      padding: "12px 16px",
      marginBottom: "16px",
      fontSize: "0.87rem",
      color: "#93c5fd",
      lineHeight: 1.6,
    }}>
      {children}
    </div>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────

export function HelpPanel() {
  return (
    <section style={{ marginTop: "24px", maxWidth: "900px" }}>
      <h2 style={H2}>Help &amp; Documentation</h2>

      {/* ── Overview ── */}
      <h3 style={H3}>What is Project Sentinel?</h3>
      <p style={P}>
        Project Sentinel is an AI-powered document routing and compliance engine. Upload a contract,
        regulatory filing, or policy document and Sentinel automatically classifies it, checks that all
        required legal clauses are present, scores the analysis for reliability, and returns a routing
        decision — all in real time.
      </p>
      <p style={P}>
        The system learns from analyst feedback through an AI-driven review loop: submit a{" "}
        <strong style={{ color: "#e2e8f0" }}>👎</strong> rating with a comment, run the Review Agent in the{" "}
        <strong style={{ color: "#a78bfa" }}>⚡ Insights</strong> tab, and approve or reject its proposed
        rule changes — all without restarting the service.
      </p>

      {/* ── Steps ── */}
      <h3 style={H3}>How to Analyse a Document</h3>
      <ol style={{ color: "#cbd5e1", fontSize: "0.9rem", lineHeight: 2, paddingLeft: "20px", marginTop: 0 }}>
        <li>Go to the <strong style={{ color: "#e2e8f0" }}>Analyse Document</strong> tab.</li>
        <li>Drag and drop your document onto the upload area, or click to browse for a file.</li>
        <li>Watch the <strong style={{ color: "#e2e8f0" }}>Agent Workflow Log</strong> for live progress as each AI agent processes your document.</li>
        <li>Review the <strong style={{ color: "#e2e8f0" }}>Analysis Result</strong> when the stream ends.</li>
      </ol>
      <p style={{ ...P, fontSize: "0.82rem", color: "#64748b" }}>
        Maximum file size: 5 MB. For multiple documents at once, use the{" "}
        <strong style={{ color: "#94a3b8" }}>Batch Upload</strong> tab.
      </p>

      {/* ── Regulatory Profiles ── */}
      <h3 style={H3}>Regulatory Profiles — Automatic Detection</h3>
      <InfoBox>
        <strong>No profile selector is needed.</strong> Sentinel automatically detects the applicable
        regulatory jurisdiction by scanning the document's content for EU or US keywords. The detected
        profile is shown in the Agent Workflow Log (e.g. <code style={{ color: "#93c5fd" }}>[router] Tenant: EU</code>).
      </InfoBox>
      <div style={{ overflowX: "auto" }}>
        <table style={TABLE}>
          <thead>
            <tr>
              <th style={TH}>Profile</th>
              <th style={TH}>Auto-detected when the document contains…</th>
              <th style={TH}>Extra clauses checked</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td style={TD}><strong>Default</strong></td>
              <td style={TDmuted}>No strong EU or US signals</td>
              <td style={TDmuted}>Standard clause requirements for all document types</td>
            </tr>
            <tr>
              <td style={TD}><strong>EU</strong></td>
              <td style={TDmuted}>GDPR, Solvency II, MiFID, MiFIR, EMIR, PRIIP, AIFMD, "European Union"…</td>
              <td style={TDmuted}>GDPR data processing clauses, Solvency II capital adequacy requirements</td>
            </tr>
            <tr>
              <td style={TD}><strong>US</strong></td>
              <td style={TDmuted}>Dodd-Frank, Sarbanes-Oxley, SOX, "SEC filing", FINRA, "US GAAP"…</td>
              <td style={TDmuted}>Dodd-Frank risk retention, Sarbanes-Oxley certification requirements</td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* ── Results ── */}
      <h3 style={H3}>Understanding Your Results</h3>

      <p style={{ ...P, marginBottom: "6px" }}><strong style={{ color: "#e2e8f0" }}>Final Decision</strong></p>
      <div style={{ overflowX: "auto", marginBottom: "16px" }}>
        <table style={TABLE}>
          <thead><tr><th style={TH}>Decision</th><th style={TH}>Meaning</th></tr></thead>
          <tbody>
            {[
              ["APPROVED",  "Document meets all compliance requirements for its type and detected profile"],
              ["REJECTED",  "One or more required clauses are missing, or the document fails evaluation"],
              ["ESCALATE",  "Document requires human review — typically large or complex transactions"],
              ["RE-ROUTE",  "Document was directed to a different workflow than initially expected"],
              ["BLOCKED",   "Document was stopped by safety guardrails (PII, prompt injection, etc.) — no analysis performed"],
              ["PENDING",   "Analysis is in progress or was interrupted"],
            ].map(([d, desc]) => (
              <tr key={d}>
                <td style={{ ...TD, whiteSpace: "nowrap" as const }}>{decisionBadge(d)}</td>
                <td style={TDmuted}>{desc}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p style={{ ...P, marginBottom: "6px" }}><strong style={{ color: "#e2e8f0" }}>Cache Badge</strong></p>
      <p style={P}>
        Results served from the document deduplication cache show an{" "}
        <strong style={{ color: "#93c5fd" }}>⚡ Cached Result</strong> badge. A{" "}
        <strong style={{ color: "#86efac" }}>✓ Fresh Analysis</strong> badge means the full pipeline ran.
        If you see a cached result and want to force re-analysis, click{" "}
        <strong style={{ color: "#e2e8f0" }}>↺ Re-analyse (clear cache)</strong>.
      </p>

      <p style={{ ...P, marginBottom: "6px" }}><strong style={{ color: "#e2e8f0" }}>Routing Confidence</strong></p>
      <p style={P}>
        The arc gauge shows how confident the AI is in its document type classification.
        Green (≥ 75%) means reliable routing; amber (50–74%) means review the document type manually;
        red (&lt; 50%) means the classification may be wrong.
      </p>

      <p style={{ ...P, marginBottom: "6px" }}><strong style={{ color: "#e2e8f0" }}>Faithfulness Score</strong></p>
      <p style={P}>
        A 0–100% measure of how accurately the AI's clause findings reflect the actual document content.
        Scores below 50% indicate the analysis may be unreliable — re-submit or verify manually.
      </p>

      <p style={{ ...P, marginBottom: "6px" }}><strong style={{ color: "#e2e8f0" }}>Hallucination Risk</strong></p>
      <p style={P}>
        A qualitative risk level (low / medium / high) from a second independent AI evaluation. High risk
        means clause findings should be verified against the original document.
      </p>

      <p style={{ ...P, marginBottom: "6px" }}><strong style={{ color: "#e2e8f0" }}>Clause Breakdown</strong></p>
      <p style={P}>
        A table listing every required clause for the detected document type and whether it was found
        (<span style={{ color: "#15803d", fontWeight: 700 }}>PRESENT</span> /&nbsp;
        <span style={{ color: "#b91c1c", fontWeight: 700 }}>MISSING</span>).
        Missing clauses are the primary reason for a REJECTED decision.
        The required clauses depend on the document type and the auto-detected regulatory profile.
      </p>

      <p style={{ ...P, marginBottom: "6px" }}><strong style={{ color: "#e2e8f0" }}>Retry Diff</strong></p>
      <p style={P}>
        Appears when the AI ran more than one attempt (faithfulness was below 75% on the first pass).
        Shows which clause statuses changed between the last two attempts, highlighted in amber.
        The pipeline retries up to 3 times.
      </p>

      <p style={{ ...P, marginBottom: "6px" }}><strong style={{ color: "#e2e8f0" }}>Compliance Officer Override</strong></p>
      <p style={P}>
        If a document is <strong>REJECTED</strong> and you disagree, click{" "}
        <em>Override &amp; Approve</em> to manually approve it. The override is recorded permanently
        for audit purposes and cannot be reversed through the UI.
      </p>

      <p style={{ ...P, marginBottom: "6px" }}><strong style={{ color: "#e2e8f0" }}>Rating Your Analysis</strong></p>
      <p style={P}>
        After each completed analysis, use the <strong>👍</strong> or <strong>👎</strong> buttons to
        rate the result.
      </p>
      <ul style={{ color: "#cbd5e1", fontSize: "0.9rem", lineHeight: 2, paddingLeft: "20px", marginTop: 0, marginBottom: "12px" }}>
        <li><strong style={{ color: "#e2e8f0" }}>👍 Helpful</strong> — click once; rating submitted immediately.</li>
        <li><strong style={{ color: "#e2e8f0" }}>👎 Not helpful</strong> — a comment box appears; describe what was wrong (optional, up to 500 characters), then click <strong style={{ color: "#e2e8f0" }}>Submit Feedback</strong>.</li>
      </ul>
      <p style={P}>
        Your feedback is used by the AI Review Agent (see <strong style={{ color: "#a78bfa" }}>⚡ Insights</strong> below)
        to identify patterns and propose rule improvements. Ratings are not available for BLOCKED documents.
      </p>

      {/* ── Analysis History ── */}
      <h3 style={H3}>Analysis History</h3>
      <p style={P}>
        The <strong style={{ color: "#e2e8f0" }}>Analysis History</strong> tab shows all past analyses.
        Each row includes three action buttons:
      </p>
      <div style={{ overflowX: "auto", marginBottom: "12px" }}>
        <table style={TABLE}>
          <thead><tr><th style={TH}>Column / Button</th><th style={TH}>What it does</th></tr></thead>
          <tbody>
            {[
              ["Feedback (👍 / 👎 / —)", "Rating you submitted for that analysis"],
              ["↓ PDF", "Downloads a full compliance report PDF for that analysis (doc type, decision, clause table, trace ID)"],
              ["↺ Fresh", "Re-runs a fresh analysis on that document — bypasses cache, streams back to the Analyse tab"],
            ].map(([col, desc]) => (
              <tr key={col as string}>
                <td style={{ ...TD, fontWeight: 600, whiteSpace: "nowrap" as const }}>{col}</td>
                <td style={TDmuted}>{desc}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* ── AI Insights ── */}
      <h3 style={H3}>⚡ AI Insights &amp; Feedback Loop</h3>
      <p style={P}>
        The <strong style={{ color: "#a78bfa" }}>Insights</strong> tab is the control centre for Sentinel's
        self-improvement system. It is intended for compliance administrators.
      </p>
      <p style={{ ...P, marginBottom: "6px" }}><strong style={{ color: "#e2e8f0" }}>How to run the loop</strong></p>
      <ol style={{ color: "#cbd5e1", fontSize: "0.9rem", lineHeight: 2, paddingLeft: "20px", marginTop: 0, marginBottom: "12px" }}>
        <li>Submit a <strong style={{ color: "#e2e8f0" }}>👎</strong> rating with a descriptive comment on any analysis result.</li>
        <li>Open the <strong style={{ color: "#a78bfa" }}>⚡ Insights</strong> tab and click <strong style={{ color: "#e2e8f0" }}>▶ Run Review Agent</strong>.</li>
        <li>The AI reads all negative feedback, groups patterns by document type, and proposes a recommendation.</li>
        <li>Click <strong style={{ color: "#e2e8f0" }}>✓ Approve</strong> to apply the change immediately — no restart needed.</li>
        <li>Re-upload the same document to observe the improvement.</li>
        <li>Click <strong style={{ color: "#e2e8f0" }}>↩ Undo</strong> at any time to reverse the change.</li>
      </ol>
      <div style={{ overflowX: "auto", marginBottom: "12px" }}>
        <table style={TABLE}>
          <thead><tr><th style={TH}>Button</th><th style={TH}>What it does</th></tr></thead>
          <tbody>
            {[
              ["✓ Approve", "Missing Rule → appends clause to the compliance database; Comprehension Failure → adds a phrase example to the LLM prompt. Applied live, no restart needed."],
              ["✗ Reject", "Dismisses the recommendation and blacklists it — the same suggestion will never re-appear for that document type."],
              ["↩ Undo",   "Reverses an approved change (removes the clause or phrase correction) and re-opens the recommendation for review."],
            ].map(([btn, desc]) => (
              <tr key={btn as string}>
                <td style={{ ...TD, fontWeight: 700, whiteSpace: "nowrap" as const }}>{btn}</td>
                <td style={TDmuted}>{desc}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* ── Batch Analysis ── */}
      <h3 style={H3}>Batch Analysis</h3>
      <p style={P}>
        Use the <strong style={{ color: "#e2e8f0" }}>Batch Upload</strong> tab to analyse multiple
        documents in one operation.
      </p>
      <InfoBox>
        <strong>Quick demo:</strong> use the <strong>sample_docs batch demo.zip</strong> package (51 documents
        covering all document types, formats, and decision outcomes) — download it from the project repository
        and drop it directly into the Batch Upload tab.
      </InfoBox>
      <ol style={{ color: "#cbd5e1", fontSize: "0.9rem", lineHeight: 2, paddingLeft: "20px", marginTop: 0, marginBottom: "12px" }}>
        <li>Click <strong style={{ color: "#e2e8f0" }}>Batch Upload</strong> in the navigation bar.</li>
        <li>Drag and drop a <strong style={{ color: "#e2e8f0" }}>ZIP file</strong> onto the upload zone, or click to browse.</li>
        <li>Analysis starts automatically — no extra button to click.</li>
        <li>A progress bar tracks how many documents have been processed.</li>
        <li>When complete, a results table shows the decision, faithfulness score, and <strong style={{ color: "#e2e8f0" }}>Source</strong> (cached / fresh) for each file.</li>
        <li>(Optional) Tick the checkboxes next to individual results, then click <strong style={{ color: "#e2e8f0" }}>↺ Re-analyse Selected</strong> to force a fresh run for those documents — bypasses the deduplication cache.</li>
      </ol>
      <p style={P}>
        Sentinel caches each document by its SHA-256 fingerprint. If an identical document was analysed
        previously, the result is returned instantly — the AI pipeline is skipped. To force re-analysis
        after approving a new recommendation, select the relevant rows and use{" "}
        <strong style={{ color: "#e2e8f0" }}>↺ Re-analyse Selected</strong>.
      </p>
      <p style={{ ...P, fontSize: "0.82rem", color: "#64748b" }}>
        Limits: up to 50 documents per ZIP, maximum 50 MB total. Rate limit: 2 batch jobs per minute.
      </p>

      {/* ── Metrics Dashboard ── */}
      <h3 style={H3}>Metrics Dashboard</h3>
      <p style={P}>
        Click the <strong style={{ color: "#e2e8f0" }}>Metrics</strong> tab to see a real-time
        observability dashboard covering all analyses recorded in the system:
      </p>
      <div style={{ overflowX: "auto", marginBottom: "12px" }}>
        <table style={TABLE}>
          <thead><tr><th style={TH}>Panel</th><th style={TH}>What it shows</th></tr></thead>
          <tbody>
            {[
              ["Total Analyses",                 "Count of all documents processed since the system started"],
              ["Decision Breakdown",             "Bar chart showing APPROVED / REJECTED / ESCALATE / BLOCKED counts"],
              ["Average Faithfulness",           "Mean faithfulness score (0–100%) across all analyses"],
              ["Hallucination Risk Distribution","Count of analyses rated low / medium / high risk"],
              ["7-Day Trend",                    "Daily analysis volume for the past 7 days"],
            ].map(([panel, desc]) => (
              <tr key={panel as string}>
                <td style={{ ...TD, fontWeight: 600, whiteSpace: "nowrap" as const }}>{panel}</td>
                <td style={TDmuted}>{desc}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* ── Sample Documents ── */}
      <h3 style={H3}>Sample Documents</h3>
      <p style={P}>
        Download any of the test files below and upload them to try Sentinel immediately. Each filename
        includes the expected decision so you know what to look for.
      </p>

      <p style={{ ...P, fontWeight: 700, color: "#e2e8f0", marginBottom: "6px" }}>
        Quick Start — one of each decision type
      </p>
      <SampleTable samples={QUICK_START} />

      <p style={{ ...P, fontWeight: 700, color: "#e2e8f0", marginBottom: "6px", marginTop: "20px" }}>
        By Document Type — all clauses present (APPROVED)
      </p>
      <SampleTable samples={BY_TYPE} />

      <p style={{ ...P, fontWeight: 700, color: "#e2e8f0", marginBottom: "6px", marginTop: "20px" }}>
        Missing Clause Tests (REJECTED)
      </p>
      <SampleTable samples={MISSING_CLAUSES} />

      <p style={{ ...P, fontWeight: 700, color: "#e2e8f0", marginBottom: "6px", marginTop: "20px" }}>
        Regulatory Profile Tests — profile auto-detected from document content
      </p>
      <InfoBox>
        These documents are detected as EU or US automatically — no profile selection required.
        Upload them as-is and the correct rules are applied.
      </InfoBox>
      <SampleTable samples={REG_PROFILES} />

      <p style={{ ...P, fontWeight: 700, color: "#e2e8f0", marginBottom: "6px", marginTop: "20px" }}>
        Alternative Formats — PDF, Word, HTML, scanned image
      </p>
      <SampleTable samples={ALT_FORMATS} />

      <p style={{ ...P, fontWeight: 700, color: "#e2e8f0", marginBottom: "6px", marginTop: "20px" }}>
        Guardrail Tests — all should be BLOCKED immediately
      </p>
      <SampleTable samples={GUARDRAILS} />

      <p style={{ ...P, fontWeight: 700, color: "#e2e8f0", marginBottom: "6px", marginTop: "20px" }}>
        AI Feedback Loop Test Documents
      </p>
      <p style={{ ...P, fontSize: "0.87rem", color: "#94a3b8" }}>
        Use these with the Insights tab to demo the full feedback loop. See the{" "}
        <strong style={{ color: "#e2e8f0" }}>FEEDBACK_LOOP_TESTING_GUIDE.md</strong> in the repository
        for step-by-step instructions and exact feedback text to submit for each scenario.
      </p>
      <SampleTable samples={FEEDBACK_LOOP} />

      {/* ── Formats ── */}
      <h3 style={H3}>Supported File Formats</h3>
      <div style={{ overflowX: "auto" }}>
        <table style={TABLE}>
          <thead><tr><th style={TH}>Format</th><th style={TH}>Extension</th><th style={TH}>Notes</th></tr></thead>
          <tbody>
            {[
              ["Plain text",        ".txt",         "Direct extraction"],
              ["PDF",               ".pdf",         "Text layer extracted; OCR fallback for image-only PDFs"],
              ["Word document",     ".docx",        "Full text from all paragraphs"],
              ["Excel spreadsheet", ".xlsx",        "All sheets concatenated"],
              ["PowerPoint",        ".pptx",        "All slide text extracted"],
              ["HTML",              ".html",        "Tags stripped; body text used"],
              ["PNG image",         ".png",         "OCR via Tesseract — min 150 DPI recommended"],
              ["JPEG image",        ".jpg / .jpeg", "OCR via Tesseract"],
              ["TIFF image",        ".tiff / .tif", "OCR via Tesseract — multi-page supported"],
            ].map(([fmt, ext, note]) => (
              <tr key={fmt as string}>
                <td style={TD}>{fmt}</td>
                <td style={{ ...TDmuted, fontFamily: "'Courier New', monospace" }}>{ext}</td>
                <td style={TDmuted}>{note}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p style={{ ...P, fontSize: "0.82rem", color: "#64748b" }}>
        Maximum file size: <strong style={{ color: "#94a3b8" }}>5 MB</strong> (single file) ·{" "}
        <strong style={{ color: "#94a3b8" }}>50 MB</strong> (batch ZIP)
      </p>

      {/* ── Limitations ── */}
      <h3 style={H3}>Limitations &amp; Known Issues</h3>
      <div style={{ overflowX: "auto" }}>
        <table style={TABLE}>
          <thead><tr><th style={TH}>Limitation</th><th style={TH}>Detail</th></tr></thead>
          <tbody>
            {[
              ["Non-English documents",   "The AI is optimised for English. French, Spanish, German, and other languages are processed but clause detection accuracy is significantly lower. A warning appears in the workflow log."],
              ["Scanned image quality",   "OCR accuracy depends on image resolution. Low-resolution or heavily watermarked scans may produce garbled text. Minimum recommended: 150 DPI."],
              ["Handwritten documents",   "Handwritten text is not reliably extracted. Typed or printed documents only."],
              ["Hallucination",           "The AI may occasionally report a clause as PRESENT when it is not clearly stated. The Faithfulness Score and Hallucination Risk indicators flag unreliable analyses."],
              ["Single file limit",       "Maximum 5 MB per file. Large PDFs with many pages may need to be split before uploading."],
              ["Batch ZIP limit",         "Up to 50 files per ZIP, maximum 50 MB total. Use multiple batch jobs for larger volumes."],
              ["5-minute timeout",        "Analyses that take longer than 5 minutes are automatically cancelled. Large documents with many OCR pages may time out."],
              ["Override is permanent",   "Once a Compliance Officer Override is applied it cannot be undone through the UI."],
              ["History is not searchable","The Analysis History table shows all records in reverse chronological order with no search or filter."],
              ["Novel document types",    "If the document does not match any of the 6 known categories it is classified as UNKNOWN and no clause compliance check is performed."],
              ["Profile auto-detection edge cases", "A document with equal EU and US keyword counts falls back to the Default profile. Highly ambiguous documents can be split or re-worded for clarity."],
            ].map(([lim, detail]) => (
              <tr key={lim as string}>
                <td style={{ ...TD, fontWeight: 600, whiteSpace: "nowrap" as const, minWidth: "180px" }}>{lim}</td>
                <td style={TDmuted}>{detail}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div style={{ height: "40px" }} />
    </section>
  )
}
