# Project Sentinel — User Guide

**Version:** Phase G (May 2026)  
**Audience:** Compliance officers, legal analysts, document reviewers

---

## Table of Contents

1. [What is Project Sentinel?](#1-what-is-project-sentinel)
2. [Getting Started](#2-getting-started)
3. [Uploading a Document](#3-uploading-a-document)
4. [Choosing a Regulatory Profile](#4-choosing-a-regulatory-profile)
5. [Understanding the Analysis Result](#5-understanding-the-analysis-result)
6. [Clause Breakdown](#6-clause-breakdown)
7. [Retry Diff — Comparing Attempts](#7-retry-diff--comparing-attempts)
8. [Rating Your Analysis](#8-rating-your-analysis)
9. [AI Insights & Feedback Loop](#9-ai-insights--feedback-loop)
10. [Batch Analysis](#10-batch-analysis)
11. [Metrics Dashboard](#11-metrics-dashboard)
12. [Analysis History](#12-analysis-history)
13. [Compliance Officer Override](#13-compliance-officer-override)
14. [Sample Documents](#14-sample-documents)
15. [Supported File Formats](#15-supported-file-formats)
16. [Limitations and Known Issues](#16-limitations-and-known-issues)
17. [Glossary](#17-glossary)

---

## 1. What is Project Sentinel?

Project Sentinel is an AI-powered document routing and compliance engine. Upload a contract, filing, or policy document and Sentinel will automatically:

- **Classify** the document type (credit agreement, legal contract, regulatory filing, etc.)
- **Check compliance** against your regulatory profile's required clauses
- **Score** the analysis for faithfulness and hallucination risk
- **Decide** whether to approve, reject, or escalate the document
- **Record** every analysis for audit trail purposes

All processing is streamed live — you can watch each AI agent work in real time.

---

## 2. Getting Started

Open the application in your browser. You will see five tabs:

| Tab | Purpose |
|-----|---------|
| **Analyze Document** | Upload a single document and run an analysis |
| **Analysis History** | View all past analyses (most recent first) |
| **Batch Upload** | Analyse multiple documents at once via ZIP file |
| **Metrics** | Real-time observability dashboard |
| **Help & Docs** | This documentation |

No login is required for the demo deployment. All analyses are stored locally.

---

## 3. Uploading a Document

1. Go to the **Analyze Document** tab.
2. Select a **Regulatory Profile** (see [Section 4](#4-choosing-a-regulatory-profile)).
3. Drag and drop a document onto the upload area, or click it to browse for a file.
4. The analysis starts immediately. Watch the **Agent Workflow Log** for live progress.

> **Tip:** Only one document can be analysed at a time. Wait for the current analysis to finish before uploading another.

---

## 4. Choosing a Regulatory Profile

The **Regulatory Profile** dropdown determines which compliance rules apply:

| Profile | Jurisdiction | Key Regulations |
|---------|-------------|-----------------|
| **Default** | General / Global | Standard clause requirements for each document type |
| **EU (GDPR / Solvency II)** | European Union | Adds GDPR data processing clauses, Solvency II capital adequacy requirements |
| **US (Dodd-Frank / SOX)** | United States | Adds Dodd-Frank risk retention, Sarbanes-Oxley certification requirements |

Choose the profile that matches the jurisdiction of the document being reviewed. You can switch profiles between analyses.

---

## 5. Understanding the Analysis Result

Once analysis completes, four result cards appear:

### Final Decision

| Decision | Meaning |
|----------|---------|
| **APPROVED** | Document meets all compliance requirements |
| **REJECTED** | One or more required clauses are missing or the document fails evaluation |
| **ESCALATE** | Document requires human review (e.g. very large or complex transactions) |
| **RE-ROUTE** | Document was classified to a different workflow than expected |
| **BLOCKED** | Document was flagged by safety guardrails (contains PII, prompt injection, or other prohibited content) |
| **PENDING** | Analysis is in progress or was interrupted |

### Document Type

The AI-detected document category. Possible values:

- `CREDIT_AGREEMENT` — Loan, mortgage, revolving facility, venture debt
- `LEGAL_CONTRACT` — NDA, MSA, service agreement, partnership deed
- `REGULATORY_FILING` — SEC 10-K / 8-K, GDPR DPA, SOX certification
- `EMPLOYMENT_CONTRACT` — Executive, standard, internship agreements
- `INSURANCE_POLICY` — Cyber, D&O, professional indemnity, property & casualty
- `PARTNERSHIP_AGREEMENT` — Joint ventures, technology partnerships
- `UNKNOWN` — Document could not be classified confidently

### Routing Confidence

An arc gauge (0–100%) showing how confident the AI is in its document type classification. Higher confidence means more reliable routing.

- **75–100%** — High confidence (green)
- **50–74%** — Moderate confidence (amber) — review classification manually
- **0–49%** — Low confidence (red) — manual classification recommended

### Faithfulness Score

How accurately the AI's compliance assessment reflects the actual document content. A low score means the AI may have "hallucinated" clause findings.

- **≥ 75%** — Reliable analysis
- **50–74%** — Review clause findings manually
- **< 50%** — Analysis may be unreliable; re-submit or review manually

### Hallucination Risk

A qualitative risk level (`low`, `medium`, `high`) from a second AI evaluation pass. High hallucination risk means clause findings should be independently verified.

---

## 6. Clause Breakdown

Below the result cards, a table lists every required clause for that document type and whether it was found:

| Status | Meaning |
|--------|---------|
| **PRESENT** (green) | Clause was identified in the document |
| **MISSING** (red) | Clause was not found — this may cause a REJECTED decision |

The required clauses depend on the document type and regulatory profile selected.

---

## 7. Retry Diff — Comparing Attempts

If the AI needed multiple attempts to reach a decision (retry loop), a **Retry Diff** table appears below the clause breakdown. It shows which clause statuses changed between the last two attempts, highlighted in amber. This helps you understand what improved (or worsened) between retries.

---

## 8. Rating Your Analysis

After a completed analysis, thumbs-up 👍 and thumbs-down 👎 buttons appear below the results.

- **👍 Helpful** — click once. The rating is submitted immediately and a confirmation appears.
- **👎 Not helpful** — a comment box appears. You can describe what was wrong (optional, up to 500 characters), then click **Submit Feedback**. Click **Cancel** to go back without submitting.

Your rating is logged with the document's trace ID and used by the AI Review Agent to identify patterns and propose rule improvements. Ratings are not available for BLOCKED documents (no analysis was performed).

The **Analysis History** table shows your rating for each past analysis (👍 / 👎 / —).

> **Tip:** The more descriptive your 👎 comment, the better the AI can identify the root cause — for example: *"The indemnity clause was clearly present but shown as MISSING."*

---

## 9. AI Insights & Feedback Loop

The **⚡ Insights** tab is the control centre for Sentinel's self-improvement system. It is intended for compliance administrators and system operators.

### Section A — Feedback Statistics

Four summary cards show:

| Card | Description |
|------|-------------|
| **Total Feedback** | Total 👍 + 👎 ratings submitted |
| **👍 Positive** | Count of positive ratings |
| **👎 Negative** | Count of negative ratings |
| **Negative Rate** | Percentage of analyses rated unhelpful |

A table below the cards shows each feedback entry with its rating, filename, decision, comment, and date.

### Section B — Run the AI Review Agent

Click **▶ Run Review Agent** to trigger an on-demand analysis of all 👎 feedback. The agent:

1. Reads accumulated negative feedback entries grouped by document type
2. Looks at what clauses were flagged and what comments analysts left
3. Calls the LLM to classify each pattern as either:
   - **Missing Rule** — a required clause is simply absent from the compliance database for that document type
   - **Comprehension Failure** — the clause exists in the database but the LLM consistently fails to detect it (e.g., unusual phrasing)
4. Creates a **Recommendation** for each pattern found

A live log streams the agent's reasoning as it runs.

**Min. evidence** dropdown — controls how many 👎 entries per document type are required before the agent acts. Default is 1 (any single thumbs-down triggers analysis). Raise this in production to avoid acting on isolated mis-ratings.

### Section C — Recommendations

Each recommendation shows the document type, pattern type, proposed change, confidence level, evidence count, and the LLM's rationale.

| Button | What it does |
|--------|-------------|
| **✓ Approve** | Applies the change immediately (no restart needed): **Missing Rule** → appends the clause to the compliance database for that document type; **Comprehension Failure** → adds a phrase correction to the prompt |
| **✗ Reject** | Dismisses the recommendation and blacklists it — the same suggestion will never re-appear for that document type |
| **↩ Undo** | Reverses an approved change (removes the clause or phrase correction) and re-opens the recommendation for review |

### Demo Walkthrough

1. Upload a document → receive a result → click 👎 → add a comment → Submit
2. Open Insights tab → click **▶ Run Review Agent**
3. See recommendation appear under "Pending Recommendations"
4. Click **✓ Approve**
5. Re-analyse the same document → observe the improvement
6. Click **↩ Undo** to reverse the change if needed

---

## 10. Batch Analysis

Use the **Batch Upload** tab to analyse multiple documents in one operation.

**Steps:**

1. Click **Batch Upload** in the navigation bar.
2. Select a ZIP file containing the documents you want to analyse.
3. (Optional) Check **Re-analyse (ignore cache)** to force fresh analysis even for documents already processed before.
4. Click **Analyse Batch** — the job is queued immediately and a progress bar appears.
5. Wait for processing to complete. The progress bar shows how many documents have been analysed.
6. When finished, a results table shows the decision, faithfulness score, and source for each document.

**Results table columns:**

| Column | Description |
|--------|-------------|
| Filename | Name of the document inside the ZIP |
| Decision | APPROVED / REJECTED / ESCALATE / BLOCKED |
| Faithfulness | Evaluation score (percentage) |
| Source | **cached** — result returned from cache instantly; **fresh** — pipeline ran for this document |

**Document cache:**

Sentinel computes a SHA-256 fingerprint of each document. If an identical document was analysed in a previous run, the cached result is returned instantly — the AI pipeline is skipped. This makes repeated batch jobs fast when most documents have not changed.

To force the pipeline to re-run (e.g., after a regulatory profile update), check **Re-analyse (ignore cache)** before submitting.

**Limits and requirements:**

| Constraint | Value |
|-----------|-------|
| Maximum files per ZIP | 50 |
| Maximum ZIP size | 50 MB |
| Supported formats | Same as single-file upload (PDF, TXT, DOCX, XLSX, PPTX, HTML, images) |
| Rate limit | 2 batch jobs per minute |

> **Tip:** Each document in the batch is processed independently. Results appear as soon as each document is completed — you do not need to wait for the entire batch.

---

## 11. Metrics Dashboard

Click the **Metrics** tab to view a real-time observability dashboard covering all analyses in the system.

| Panel | Description |
|-------|-------------|
| **Total Analyses** | Count of every document processed since the system started |
| **Decision Breakdown** | Bar chart of APPROVED / REJECTED / ESCALATE / BLOCKED counts |
| **Average Faithfulness** | Mean faithfulness score across all analyses |
| **Hallucination Risk Distribution** | Count of analyses rated low / medium / high risk |
| **7-Day Trend** | Daily volume chart for the past 7 days |

The dashboard is read-only and refreshes each time you navigate to the Metrics tab.

---

## 12. Analysis History

Click the **Analysis History** tab to view all past analyses. The table shows:

| Column | Description |
|--------|-------------|
| Filename | Original document filename |
| Doc Type | Detected document category |
| Decision | Final routing decision |
| Faithfulness | AI faithfulness score |
| Risk | Hallucination risk level |
| Date | Timestamp of analysis |

Analyses are stored persistently. The history survives server restarts.

---

## 13. Compliance Officer Override

If a document is **REJECTED** and the compliance officer disagrees, click **Override & Approve** to manually approve it. The override is recorded in the system. The decision badge updates immediately to show **APPROVED**.

> **Note:** Overrides are permanent and cannot be reversed through the UI.

---

## 14. Sample Documents

A set of ready-made test documents is included in the `sample_docs/` folder. Each filename ends with the expected decision so you know what to expect. Use these to explore Sentinel's capabilities without needing real documents.

### Approved Documents (should return APPROVED)

| File | Type | Notes |
|------|------|-------|
| `credit_agreement_valid.txt` | Credit Agreement | All required clauses present |
| `credit_agreement_valid.pdf` | Credit Agreement | PDF format, same content |
| `credit_agreement_microfinance_SME_all_clauses_APPROVED.txt` | Credit Agreement | SME lending scenario |
| `credit_agreement_consumer_mortgage_residential_APPROVED.txt` | Credit Agreement | Residential mortgage |
| `credit_agreement_venture_debt_convertible_APPROVED.txt` | Credit Agreement | Convertible venture debt |
| `credit_agreement_pdf_revolving_facility_APPROVED.pdf` | Credit Agreement | Revolving credit facility |
| `legal_contract_nda_all_clauses_APPROVED.txt` | Legal Contract | NDA with all clauses |
| `legal_contract_master_services_agreement_APPROVED.txt` | Legal Contract | Full MSA |
| `legal_contract_html_format_nda_APPROVED.html` | Legal Contract | HTML format NDA |
| `regulatory_filing_sec_10k_annual_report_complete_APPROVED.txt` | Regulatory Filing | SEC 10-K annual report |
| `regulatory_filing_sec_10k_us_tenant_sox_certification_APPROVED.txt` | Regulatory Filing | Use with **US** profile |
| `regulatory_filing_gdpr_data_processing_eu_tenant_APPROVED.txt` | Regulatory Filing | Use with **EU** profile |
| `regulatory_filing_html_sec_8k_material_event_APPROVED.html` | Regulatory Filing | SEC 8-K event filing |
| `employment_contract_executive_cto_all_clauses_APPROVED.txt` | Employment Contract | CTO-level executive contract |
| `employment_contract_ceo_word_format_all_clauses_APPROVED.docx` | Employment Contract | Word document format |
| `insurance_policy_cyber_liability_complete_APPROVED.txt` | Insurance Policy | Cyber liability policy |
| `insurance_policy_professional_indemnity_complete_APPROVED.txt` | Insurance Policy | Professional indemnity |
| `insurance_policy_xlsx_property_casualty_complete_APPROVED.xlsx` | Insurance Policy | Excel format |
| `partnership_agreement_jv_technology_all_clauses_APPROVED.txt` | Partnership Agreement | Technology JV |
| `partnership_agreement_pptx_jv_tech_all_clauses_APPROVED.pptx` | Partnership Agreement | PowerPoint format |
| `credit_agreement_png_clean_scan_APPROVED.png` | Credit Agreement | Scanned image (OCR) |
| `employment_contract_jpg_standard_scan_APPROVED.jpg` | Employment Contract | JPG scan (OCR) |
| `insurance_policy_png_watermark_approved_APPROVED.png` | Insurance Policy | Watermarked scan (OCR) |
| `partnership_agreement_jpg_executed_stamp_APPROVED.jpg` | Partnership Agreement | Stamped scan (OCR) |
| `regulatory_filing_tiff_clean_scan_APPROVED.tiff` | Regulatory Filing | TIFF scan (OCR) |

### Rejected Documents (should return REJECTED)

| File | Type | Notes |
|------|------|-------|
| `contract_missing_clause.txt` | Legal Contract | Missing key clauses |
| `contract_missing_clause.pdf` | Legal Contract | PDF of above |
| `credit_agreement_missing_clause.txt` | Credit Agreement | Missing clause |
| `credit_agreement_expired_term_2019_REJECTED.txt` | Credit Agreement | Expired term (2019) |
| `legal_contract_service_agreement_missing_dispute_resolution_REJECTED.txt` | Legal Contract | No dispute resolution clause |
| `legal_contract_incomplete_truncated_document_REJECTED.txt` | Legal Contract | Truncated/incomplete document |
| `regulatory_filing_missing_risk_factors_and_auditor_REJECTED.txt` | Regulatory Filing | Missing risk factors |
| `employment_contract_missing_ip_assignment_REJECTED.txt` | Employment Contract | No IP assignment clause |
| `employment_contract_intern_summer_missing_termination_REJECTED.txt` | Employment Contract | No termination clause |
| `insurance_policy_directors_officers_missing_claims_procedure_REJECTED.txt` | Insurance Policy | Missing claims procedure |
| `partnership_agreement_missing_dissolution_clause_REJECTED.txt` | Partnership Agreement | No dissolution clause |
| `employment_contract_png_missing_noncompete_REJECTED.png` | Employment Contract | Scanned, missing non-compete |
| `legal_contract_png_lowres_scan_REJECTED.png` | Legal Contract | Low-resolution scan |
| `credit_agreement_tiff_expired_2022_REJECTED.tiff` | Credit Agreement | Expired TIFF scan |

### Escalated Documents (should return ESCALATE)

| File | Type | Notes |
|------|------|-------|
| `credit_agreement_syndicated_loan_500M_ESCALATE.txt` | Credit Agreement | $500M syndicated loan — triggers escalation |
| `credit_agreement_billion_dollar_syndicated_infrastructure_ESCALATE.txt` | Credit Agreement | $1B+ infrastructure deal — triggers escalation |

### Blocked Documents (should return BLOCKED — guardrail tests)

| File | Type | Notes |
|------|------|-------|
| `guardrail_prompt_injection_attempt_BLOCKED.txt` | Security Test | Prompt injection attack |
| `guardrail_jailbreak_dan_roleplay_BLOCKED.txt` | Security Test | DAN / roleplay jailbreak |
| `guardrail_pii_ssn_and_credit_card_BLOCKED.txt` | Security Test | SSN + credit card numbers |
| `guardrail_pii_passport_iban_swift_BLOCKED.txt` | Security Test | Passport + IBAN + SWIFT codes |
| `guardrail_sql_injection_attempt_BLOCKED.txt` | Security Test | SQL injection patterns |
| `guardrail_pii_ssn_creditcard_scanned_image_BLOCKED.jpg` | Security Test | PII in scanned image (OCR) |

### Non-English Documents (language detection warning)

| File | Language | Notes |
|------|----------|-------|
| `legal_contract_french_language_non_english_WARNING.txt` | French | May produce unreliable analysis |
| `legal_contract_spanish_nda_non_english_WARNING.txt` | Spanish | May produce unreliable analysis |
| `employment_contract_german_language_WARNING.txt` | German | May produce unreliable analysis |
| `partnership_agreement_tiff_french_scan_WARNING.tiff` | French | Scanned French document |

### Deduplication Test

| File | Notes |
|------|-------|
| `credit_agreement_duplicate_resubmission_tests_dedup_cache.txt` | Upload this file twice — the second submission returns instantly from cache |

---

## 15. Supported File Formats

| Format | Extension | Notes |
|--------|-----------|-------|
| Plain text | `.txt` | Direct text extraction |
| PDF | `.pdf` | Text layer extracted; falls back to OCR if text-only |
| Word document | `.docx` | Full text extraction |
| Excel spreadsheet | `.xlsx` | All sheets concatenated |
| PowerPoint | `.pptx` | All slide text extracted |
| HTML | `.html` | Tags stripped; body text extracted |
| PNG image | `.png` | OCR via Tesseract |
| JPEG image | `.jpg`, `.jpeg` | OCR via Tesseract |
| TIFF image | `.tiff`, `.tif` | OCR via Tesseract |

> **Maximum file size:** 50 MB. Very large files may take longer to process.

---

## 16. Limitations and Known Issues

### AI / LLM Limitations

| Limitation | Detail |
|-----------|--------|
| **Non-English documents** | The AI is optimised for English. French, Spanish, German, and other language documents will be processed but clause detection accuracy is significantly lower. A warning is logged when a non-English document is detected. |
| **Scanned image quality** | OCR accuracy depends on image resolution and quality. Low-resolution or heavily watermarked scans may produce garbled text, leading to incorrect clause detection. Minimum recommended resolution: 150 DPI. |
| **Handwritten documents** | Handwritten text is not reliably extracted. Only typed/printed documents are supported. |
| **Very short documents** | Documents under ~200 words may not contain enough context for accurate classification or clause detection. |
| **Hallucination** | The LLM may occasionally report a clause as PRESENT when it is not clearly stated, or vice versa. Always cross-check REJECTED decisions for high-value documents. The Faithfulness Score and Hallucination Risk indicators help flag unreliable analyses. |
| **Clause wording variations** | Clause detection looks for semantic meaning, not exact wording. Unusual legal phrasing or highly abbreviated clauses may be missed. |

### Classification Limitations

| Limitation | Detail |
|-----------|--------|
| **Hybrid documents** | A document that is simultaneously a credit agreement and a regulatory filing may be classified as one type only. The compliance check applies to the detected type. |
| **Novel document types** | If the document type does not match any of the 6 known categories, it is classified as `UNKNOWN` and no clause compliance check is performed. |
| **Routing confidence** | When routing confidence is below 50%, the classification may be incorrect. Review the document type manually for low-confidence results. |

### System Limitations

| Limitation | Detail |
|-----------|--------|
| **Batch ZIP limit** | Batch upload processes up to 50 documents per ZIP (max 50 MB). Submit multiple batch jobs for larger volumes. |
| **Analysis timeout** | Analyses that take longer than 5 minutes are automatically cancelled. Very large documents (>20 pages with OCR) may time out. |
| **No real-time collaboration** | Multiple users can access the system simultaneously, but there is no locking — two users could analyse the same document at the same time. |
| **Override is irreversible** | Once a Compliance Officer Override is applied, it cannot be undone through the UI. |
| **History is not searchable** | The Analysis History table shows all records in reverse chronological order. There is no search or filter capability. |
| **No email notifications** | The system does not send email alerts when analyses complete or decisions change. |

### Known Issues

| Issue | Workaround |
|-------|-----------|
| TIFF files with more than 4 pages may be slow to process (OCR per page) | Split large TIFFs before uploading |
| Very large Excel files (>10K rows) may exceed the 50 MB limit | Export the relevant sheets only |
| The Retry Diff table only appears after at least 2 analysis attempts | This is by design — retries are only triggered when the first attempt produces a low faithfulness score |
| Browser back/forward navigation resets the upload state | This is a single-page application; use the tab buttons within Sentinel instead |

---

## 17. Glossary

| Term | Definition |
|------|-----------|
| **Agent** | An AI node in the processing pipeline (Guardrail, Router, Compliance, Evaluator) |
| **Clause** | A legally significant provision that must be present in a document of a given type |
| **Compliance Officer Override** | A manual decision to approve a rejected document, recorded for audit |
| **Escalate** | A routing decision indicating the document needs human review due to complexity or value |
| **Faithfulness Score** | A 0–100% measure of how accurately the AI's findings reflect the document content |
| **Guardrail** | A safety filter that blocks documents containing PII, prompt injection, or other prohibited content |
| **Hallucination** | When an AI reports information not present in the source document |
| **OCR** | Optical Character Recognition — extracting text from scanned images |
| **Regulatory Profile** | A set of compliance rules tied to a jurisdiction (Default, EU, US) |
| **Routing Confidence** | How certain the AI is about its document type classification |
| **Retry Loop** | Automatic re-analysis when initial faithfulness is low, up to 3 attempts |
| **SSE** | Server-Sent Events — the technology used to stream live agent logs to the browser |
| **Tenant** | A regulatory profile identifier (default / EU / US) |
| **Trace ID** | A unique identifier for each analysis, used for audit, override, and feedback tracking |
| **Feedback** | A thumbs-up or thumbs-down rating attached to a completed analysis result |
| **Batch Job** | A background task that processes multiple documents from a ZIP file concurrently |
| **Faithfulness Score** | (see above) — also the primary metric shown in the Metrics dashboard |
