# Project Sentinel — User Guide

**Version:** Phase G (May 2026)  
**Audience:** Compliance officers, legal analysts, document reviewers

---

## Table of Contents

1. [What is Project Sentinel?](#1-what-is-project-sentinel)
2. [Getting Started — The Six Tabs](#2-getting-started--the-six-tabs)
3. [Uploading a Document](#3-uploading-a-document)
4. [How Regulatory Profiles Work (Auto-Detection)](#4-how-regulatory-profiles-work-auto-detection)
5. [Understanding the Analysis Result](#5-understanding-the-analysis-result)
6. [Clause Breakdown](#6-clause-breakdown)
7. [Retry Diff — Comparing Attempts](#7-retry-diff--comparing-attempts)
8. [Rating Your Analysis](#8-rating-your-analysis)
9. [AI Insights & Feedback Loop](#9-ai-insights--feedback-loop)
10. [Batch Analysis](#10-batch-analysis)
11. [Metrics Dashboard](#11-metrics-dashboard)
12. [Analysis History](#12-analysis-history)
13. [Compliance Officer Override](#13-compliance-officer-override)
14. [Demo Packages — Ready-to-Use ZIP Files](#14-demo-packages--ready-to-use-zip-files)
15. [Sample Documents (Individual Files)](#15-sample-documents-individual-files)
16. [Supported File Formats](#16-supported-file-formats)
17. [Limitations and Known Issues](#17-limitations-and-known-issues)
18. [Glossary](#18-glossary)

---

## 1. What is Project Sentinel?

Project Sentinel is an AI-powered document routing and compliance engine. Upload a contract, filing, or policy document and Sentinel will automatically:

- **Classify** the document type (credit agreement, legal contract, regulatory filing, etc.)
- **Detect** the applicable regulatory jurisdiction (Default / EU / US) from the document content
- **Check compliance** against the required clauses for that document type and jurisdiction
- **Score** the analysis for faithfulness and hallucination risk
- **Decide** whether to approve, reject, or escalate the document
- **Learn** from analyst feedback through an AI-driven review loop that proposes and applies rule improvements

All processing is streamed live — you can watch each AI agent work in real time.

---

## 2. Getting Started — The Six Tabs

Open the application in your browser. You will see six tabs in the navigation bar:

| Tab | Label | Purpose |
|-----|-------|---------|
| 1 | **Analyze Document** | Upload a single document and run a compliance analysis |
| 2 | **Analysis History** | View all past analyses with PDF report download and re-analyse options |
| 3 | **Batch Upload** | Analyse an entire ZIP file of documents in one go |
| 4 | **Metrics** | Real-time observability dashboard (decisions, faithfulness, trends) |
| 5 | **⚡ Insights** | AI feedback loop control centre — run the review agent, approve/reject recommendations |
| 6 | **Help & Docs** | Inline user documentation and sample document catalogue |

No login is required for the demo deployment. All analyses are stored locally in a SQLite database and survive server restarts.

---

## 3. Uploading a Document

1. Go to the **Analyze Document** tab.
2. Drag and drop a document onto the upload area, or click it to browse for a file.
3. The analysis starts immediately. Watch the **Agent Workflow Log** for a live stream of each agent step.
4. When the stream ends, the result cards and clause breakdown table appear automatically.

> **Tip:** Only one document can be analysed at a time on the Analyze tab. For bulk processing, use the [Batch Upload](#10-batch-analysis) tab.

> **File size limit:** Single-file uploads are limited to **5 MB**. For larger documents, split them before uploading.

---

## 4. How Regulatory Profiles Work (Auto-Detection)

Sentinel **automatically detects** the applicable regulatory jurisdiction from the document's content — there is no profile selector to set manually. The backend scans the first 8,000 characters of the document for regulatory keywords:

| Profile | Auto-detected when the document contains… |
|---------|------------------------------------------|
| **EU** | GDPR, Solvency II, MiFID, MiFIR, EMIR, PRIIP, AIFMD, UCITS, "European Union", "General Data Protection Regulation", etc. |
| **US** | Dodd-Frank, Sarbanes-Oxley, SOX, "SEC filing", FINRA, "Securities Exchange Act", Volcker Rule, CFTC, US GAAP, etc. |
| **Default** | No strong EU or US signals detected — generic international clause requirements apply |

### What this means for testing

- The **EU-specific sample documents** (`regulatory_filing_gdpr_data_processing_eu_tenant_APPROVED.txt`, `partnership_agreement_tiff_french_scan_WARNING.tiff`, etc.) contain enough GDPR / EU language for the auto-detector to pick the EU profile automatically — no action needed on your part.
- The **US-specific sample documents** (`regulatory_filing_sec_10k_us_tenant_sox_certification_APPROVED.txt`) contain Sarbanes-Oxley / SEC language and will be auto-detected as US.
- **Plain contracts** (NDAs, employment agreements, insurance policies) typically auto-detect as Default.

### What each profile adds

| Profile | Extra clauses beyond Default |
|---------|------------------------------|
| **EU** | GDPR data processing agreement (CREDIT_AGREEMENT), Solvency II capital adequacy (INSURANCE_POLICY), GDPR Data Processor Obligations (REGULATORY_FILING) |
| **US** | Dodd-Frank risk retention (CREDIT_AGREEMENT), SOX Section 302 / 906 certification (REGULATORY_FILING) |
| **Default** | Standard international clause requirements only |

> **Note:** The detected tenant is shown in the Agent Workflow Log stream (`[router] Tenant: EU`) so you can confirm which profile was applied.

---

## 5. Understanding the Analysis Result

Once analysis completes, four result cards appear.

### Final Decision

| Decision | Meaning |
|----------|---------|
| **APPROVED** | Document meets all compliance requirements for the detected jurisdiction |
| **REJECTED** | One or more required clauses are missing, or the document failed evaluation |
| **ESCALATE** | Document requires human review (e.g. very large or complex transaction — typically $500 M+) |
| **RE-ROUTE** | Document was classified to a different workflow than expected |
| **BLOCKED** | Document was flagged by safety guardrails (contains PII, prompt injection, or other prohibited content) — no compliance analysis was performed |
| **PENDING** | Analysis is in progress or was interrupted |

### Document Type

The AI-detected document category:

| Type | Examples |
|------|---------|
| `CREDIT_AGREEMENT` | Loan, mortgage, revolving facility, venture debt, syndicated facility |
| `LEGAL_CONTRACT` | NDA, MSA, service agreement, partnership deed |
| `REGULATORY_FILING` | SEC 10-K / 8-K, GDPR DPA, SOX certification |
| `EMPLOYMENT_CONTRACT` | Executive, standard, internship agreements |
| `INSURANCE_POLICY` | Cyber, D&O, professional indemnity, property & casualty |
| `PARTNERSHIP_AGREEMENT` | Joint ventures, technology partnerships |
| `UNKNOWN` | Document could not be classified confidently — no clause check is performed |

### Routing Confidence

An arc gauge (0–100%) showing how confident the AI is in its document type classification.

| Range | Colour | Meaning |
|-------|--------|---------|
| 75–100% | Green | High confidence — classification is reliable |
| 50–74% | Amber | Moderate confidence — verify the document type manually |
| 0–49% | Red | Low confidence — manual classification recommended |

### Faithfulness Score

How accurately the AI's compliance assessment reflects the actual document content. A low score means the AI may have hallucinated clause findings.

| Score | Meaning |
|-------|---------|
| ≥ 75% | Reliable analysis |
| 50–74% | Review clause findings manually |
| < 50% | Analysis may be unreliable; re-submit or review manually |

### Hallucination Risk

A qualitative risk level (`low` / `medium` / `high`) from a second independent AI evaluation pass. High hallucination risk means clause findings should be independently verified by a human reviewer.

### Cache Badge

If the same document was previously analysed, the result is returned instantly from cache with an **⚡ Cached Result** badge. A **✓ Fresh Analysis** badge means the full pipeline ran. If you see a cached result and want to force re-analysis (e.g. after a regulatory database update), click **↺ Re-analyse (clear cache)** next to the badge.

---

## 6. Clause Breakdown

Below the result cards, a table lists every required clause for the detected document type and jurisdiction, and whether it was found:

| Status | Colour | Meaning |
|--------|--------|---------|
| **PRESENT** | Green | Clause was identified in the document |
| **MISSING** | Red | Clause was not found — this typically causes a REJECTED decision |
| **⚠ UNVERIFIED** | Amber | Clause was not found but the overall result is not REJECTED (e.g., ESCALATE path) |

The required clauses depend on the document type and the auto-detected regulatory profile.

---

## 7. Retry Diff — Comparing Attempts

If the AI needed multiple attempts to reach a decision (because the first pass had a faithfulness score below 75%), a **Retry Diff** table appears below the clause breakdown. It shows which clause statuses changed between the last two attempts, highlighted in amber. This helps you understand what improved or worsened between retries.

The retry loop runs a maximum of 3 times before the pipeline stops regardless of score.

---

## 8. Rating Your Analysis

After a completed analysis, **👍** and **👎** buttons appear below the results.

- **👍 Helpful** — click once. The rating is submitted immediately and a confirmation message appears.
- **👎 Not helpful** — a comment box slides open. You can describe what was wrong (optional, up to 500 characters), then click **Submit Feedback**. Click **Cancel** to dismiss without submitting.

Your rating is logged with the document's trace ID and used by the AI Review Agent (see [Section 9](#9-ai-insights--feedback-loop)) to identify patterns and propose rule improvements.

> **Tip:** The more descriptive your 👎 comment, the better the AI can identify the root cause. Examples of useful comments:
> - *"The indemnity clause was clearly present in Section 6 but shown as MISSING"*
> - *"This NDA should require a 48-hour data breach notification obligation — the clause is not currently checked"*
> - *"Section 5 titled 'Obligor Acceleration Events' IS the events of default clause — unusual heading"*

Ratings are not available for BLOCKED documents (no compliance analysis was performed). The **Analysis History** table shows the submitted rating for each past analysis (👍 / 👎 / —).

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

A table below the cards shows every feedback entry with its rating, filename, decision, comment text, and submission date. This table is also downloadable as a CSV from the API (`GET /api/feedback/export`).

### Section B — Run the AI Review Agent

Click **▶ Run Review Agent** to trigger an on-demand analysis of all 👎 feedback. A live log streams the agent's reasoning as it runs.

**Min. evidence** dropdown — controls how many 👎 entries per document type are required before the agent acts on that type. Default is `1` (any single thumbs-down triggers analysis). Raise this in production to avoid acting on isolated mis-ratings.

The review agent:

1. Reads all negative feedback entries grouped by document type
2. Examines which clauses were flagged and what comments analysts left
3. Calls the LLM to classify each pattern as one of two types:
   - **Missing Rule** (`missing_rule`) — a required clause is simply absent from the compliance database for that document type; the LLM correctly reports it missing because it is not listed
   - **Comprehension Failure** (`comprehension_failure`) — the clause is required and exists in the document, but the LLM consistently fails to detect it (e.g. due to unusual phrasing or non-standard headings)
4. Creates a **Recommendation** for each distinct pattern found

### Section C — Recommendations

Each recommendation shows: document type, pattern type, proposed change, confidence level, evidence count, and the LLM's rationale.

| Button | What it does |
|--------|-------------|
| **✓ Approve** | Applies the change **immediately, no restart needed**: **Missing Rule** → appends the clause to `regulatory_db.json` for that document type; **Comprehension Failure** → adds a phrase correction to `few_shot_examples.jsonl` so the LLM recognises the unusual phrasing next time |
| **✗ Reject** | Dismisses the recommendation and blacklists it — the same suggestion will never re-appear for that document type |
| **↩ Undo** | Reverses an approved change (removes the clause or phrase correction) and re-opens the recommendation for review; for a rejected recommendation, removes from blacklist and resets to Pending |

### Demo Walkthrough

Use the **`sample_docs feedback loop demo.zip`** package (see [Section 14](#14-demo-packages--ready-to-use-zip-files)) and the [`docs/FEEDBACK_LOOP_TESTING_GUIDE.md`](FEEDBACK_LOOP_TESTING_GUIDE.md) for a complete step-by-step demo of all three scenarios.

**Quick summary of the loop:**
1. Upload a document → receive a result → click **👎** → add a descriptive comment → **Submit Feedback**
2. Open the **⚡ Insights** tab → click **▶ Run Review Agent**
3. A recommendation appears under "Pending Recommendations"
4. Click **✓ Approve** — the rule is applied live
5. Re-upload the same document → observe the improved result
6. Click **↩ Undo** to reverse the change if needed

---

## 10. Batch Analysis

Use the **Batch Upload** tab to analyse multiple documents in a single operation.

### Steps

1. Click **Batch Upload** in the navigation bar.
2. Select a ZIP file containing the documents you want to analyse.
   > **Quick start:** Use the included **`sample_docs batch demo.zip`** (51 documents, all types and formats) — see [Section 14](#14-demo-packages--ready-to-use-zip-files).
3. (Optional) Check **Re-analyse (ignore cache)** to force fresh analysis even for documents already processed previously.
4. Click **Analyse Batch** — the job is queued immediately and a progress bar appears.
5. Results appear as each document completes — you do not need to wait for the full batch.
6. When finished, a results table shows the decision, faithfulness score, and cache source for each file.

### Results Table Columns

| Column | Description |
|--------|-------------|
| Filename | Name of the document inside the ZIP |
| Decision | APPROVED / REJECTED / ESCALATE / BLOCKED |
| Faithfulness | Evaluation score (percentage) |
| Source | **cached** — returned from dedup cache instantly; **fresh** — pipeline ran |

### Document Deduplication Cache

Sentinel computes a SHA-256 fingerprint of each uploaded file. If an identical document was analysed in any previous run, the cached result is returned instantly — the full AI pipeline is skipped. This makes repeated batch jobs fast when most documents have not changed.

To force the pipeline to re-run (e.g. after a regulatory profile update or a new few-shot correction was approved), check **Re-analyse (ignore cache)** before submitting the batch.

### Limits

| Constraint | Value |
|-----------|-------|
| Maximum files per ZIP | 50 |
| Maximum ZIP file size | 50 MB |
| Rate limit | 2 batch jobs per minute per IP |
| Supported formats | Same as single-file upload |

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

The dashboard refreshes each time you navigate to the Metrics tab.

---

## 12. Analysis History

Click the **Analysis History** tab to view all past analyses. The table shows nine columns:

| Column | Description |
|--------|-------------|
| Filename | Original document filename |
| Doc Type | Auto-detected document category |
| Decision | Final routing decision (colour-coded) |
| Faithfulness | AI faithfulness score (%) |
| Risk | Hallucination risk level (low / medium / high) |
| Date | Timestamp of analysis |
| Feedback | Rating submitted for this analysis (👍 / 👎 / —) |
| Report | **↓ PDF** button — downloads a full compliance report PDF for that analysis |
| Fresh | **↺ Fresh** button — re-runs a fresh analysis on that document (bypasses cache, streams back to the Analyze tab) |

Analyses are stored persistently in SQLite. History survives server restarts.

You can also export the full history as CSV: `GET /api/history/export`.

---

## 13. Compliance Officer Override

If a document is **REJECTED** and the compliance officer disagrees with the decision, click **Override & Approve** (shown below the clause breakdown when a REJECTED result is on screen) to manually approve it. The override is recorded with a timestamp in the system and the decision badge updates immediately to **APPROVED**.

> **Note:** Overrides are permanent and cannot be reversed through the UI. If you need to revert an override, contact your system administrator.

---

## 14. Demo Packages — Ready-to-Use ZIP Files

Two ZIP packages are included in the repository root for running demos without needing to source your own documents.

---

### `sample_docs batch demo.zip` (1.9 MB) — Batch Upload Demo

Drop this ZIP directly into the **Batch Upload** tab for a complete end-to-end batch processing demo. Contains **51 labelled documents** covering every supported file format, document type, and decision outcome.

| Category | Documents | Expected result |
|----------|-----------|----------------|
| **Legal Contracts — APPROVED** | NDA (all clauses), MSA, HTML-format NDA | APPROVED |
| **Legal Contracts — REJECTED** | Missing dispute resolution, truncated document, low-res scan | REJECTED |
| **Credit Agreements — APPROVED** | SME microfinance, consumer mortgage, venture debt, revolving facility (PDF) | APPROVED |
| **Credit Agreements — REJECTED** | Missing clause, expired term (2019), expired TIFF scan (2022) | REJECTED |
| **Credit Agreements — ESCALATE** | $500 M syndicated loan, $1 B+ infrastructure deal | ESCALATE |
| **Employment Contracts — APPROVED** | CTO (TXT), CEO (DOCX), standard scan (JPG) | APPROVED |
| **Employment Contracts — REJECTED** | Missing IP assignment, missing termination clause (intern), missing non-compete (PNG) | REJECTED |
| **Insurance Policies — APPROVED** | Cyber liability, professional indemnity, property & casualty (XLSX), watermarked scan (PNG) | APPROVED |
| **Insurance Policies — REJECTED** | D&O missing claims procedure | REJECTED |
| **Partnership Agreements — APPROVED** | JV technology (TXT + PPTX), executed stamp scan (JPG) | APPROVED |
| **Partnership Agreements — REJECTED** | Missing dissolution clause | REJECTED |
| **Regulatory Filings — APPROVED** | SEC 10-K, 8-K (HTML), GDPR DPA (EU auto-detected), SOX certification (US auto-detected), clean TIFF scan | APPROVED |
| **Regulatory Filings — REJECTED** | Missing risk factors and auditor opinion | REJECTED |
| **Guardrail Tests** | SSN + credit card, passport + IBAN + SWIFT, SSN on scanned image (JPG), SQL injection, prompt injection, DAN jailbreak | BLOCKED |
| **Language Tests** | French NDA, Spanish NDA, German employment contract, French TIFF scan | WARNING (non-English) |
| **Deduplication Test** | `credit_agreement_duplicate_resubmission_tests_dedup_cache.txt` (submit twice — second is instant) | Cached on 2nd run |

---

### `sample_docs feedback loop demo.zip` (20 KB) — Feedback Loop Demo

Use this ZIP together with the **[Feedback Loop Testing Guide](FEEDBACK_LOOP_TESTING_GUIDE.md)** to demonstrate all three feedback loop scenarios. The guide includes exact copy-paste feedback text for each 👎 submission and the expected before/after results.

| File | Scenario | Use |
|------|----------|-----|
| `fl_test_s1_nda_all_current_clauses_APPROVED.txt` | S1 — Missing Rule | **Trigger:** NDA currently APPROVED but missing data breach notification |
| `fl_test_s1_nda_with_breach_notice_APPROVED.txt` | S1 — Missing Rule | **Verify:** Same NDA with breach notice clause — still APPROVED after fix |
| `fl_test_s2_credit_unusual_phrasing_REJECTED_before_fix.txt` | S2 — Comprehension Failure | Credit agreement with all 4 clauses but non-standard headings — REJECTED before fix |
| `fl_test_s3_employment_all_current_clauses_APPROVED.txt` | S3 — Missing Rule | **Trigger:** Employment contract APPROVED but missing remote work policy |
| `fl_test_s3_employment_with_remote_work_APPROVED.txt` | S3 — Missing Rule | **Verify:** Same contract with remote work clause — APPROVED after fix |
| `FEEDBACK_LOOP_TESTING_GUIDE.md` | All | Step-by-step instructions |

**Three scenarios demonstrated:**

| # | Doc Type | Feedback Type | What changes |
|---|----------|--------------|-------------|
| S1 | LEGAL_CONTRACT | `missing_rule` | `data breach notification clause` added to required clauses |
| S2 | CREDIT_AGREEMENT | `comprehension_failure` | LLM learns "Obligor Acceleration Events" = events of default |
| S3 | EMPLOYMENT_CONTRACT | `missing_rule` | `remote work and flexible arrangements policy` added |

---

## 15. Sample Documents (Individual Files)

All sample documents are also available individually in the `sample_docs/` folder. Each filename ends with the expected decision. Below is the complete catalogue.

### Approved Documents

| File | Type | Notes |
|------|------|-------|
| `credit_agreement_valid.txt` | Credit Agreement | All required clauses |
| `credit_agreement_valid.pdf` | Credit Agreement | PDF format |
| `credit_agreement_microfinance_SME_all_clauses_APPROVED.txt` | Credit Agreement | SME lending |
| `credit_agreement_consumer_mortgage_residential_APPROVED.txt` | Credit Agreement | Residential mortgage |
| `credit_agreement_venture_debt_convertible_APPROVED.txt` | Credit Agreement | Convertible venture debt |
| `credit_agreement_pdf_revolving_facility_APPROVED.pdf` | Credit Agreement | Revolving credit PDF |
| `credit_agreement_png_clean_scan_APPROVED.png` | Credit Agreement | Scanned image (OCR) |
| `legal_contract_nda_all_clauses_APPROVED.txt` | Legal Contract | NDA with all clauses |
| `legal_contract_master_services_agreement_APPROVED.txt` | Legal Contract | Full MSA |
| `legal_contract_html_format_nda_APPROVED.html` | Legal Contract | HTML format NDA |
| `regulatory_filing_sec_10k_annual_report_complete_APPROVED.txt` | Regulatory Filing | SEC 10-K — Default profile |
| `regulatory_filing_sec_10k_us_tenant_sox_certification_APPROVED.txt` | Regulatory Filing | SOX language → **auto-detected as US** |
| `regulatory_filing_gdpr_data_processing_eu_tenant_APPROVED.txt` | Regulatory Filing | GDPR language → **auto-detected as EU** |
| `regulatory_filing_html_sec_8k_material_event_APPROVED.html` | Regulatory Filing | SEC 8-K event filing |
| `regulatory_filing_tiff_clean_scan_APPROVED.tiff` | Regulatory Filing | TIFF scan (OCR) |
| `employment_contract_executive_cto_all_clauses_APPROVED.txt` | Employment Contract | CTO-level contract |
| `employment_contract_ceo_word_format_all_clauses_APPROVED.docx` | Employment Contract | Word document |
| `employment_contract_jpg_standard_scan_APPROVED.jpg` | Employment Contract | JPG scan (OCR) |
| `insurance_policy_cyber_liability_complete_APPROVED.txt` | Insurance Policy | Cyber liability |
| `insurance_policy_professional_indemnity_complete_APPROVED.txt` | Insurance Policy | Professional indemnity |
| `insurance_policy_xlsx_property_casualty_complete_APPROVED.xlsx` | Insurance Policy | Excel format |
| `insurance_policy_png_watermark_approved_APPROVED.png` | Insurance Policy | Watermarked scan (OCR) |
| `partnership_agreement_jv_technology_all_clauses_APPROVED.txt` | Partnership Agreement | Technology JV |
| `partnership_agreement_pptx_jv_tech_all_clauses_APPROVED.pptx` | Partnership Agreement | PowerPoint format |
| `partnership_agreement_jpg_executed_stamp_APPROVED.jpg` | Partnership Agreement | Stamped scan (OCR) |

### Rejected Documents

| File | Type | Missing / Issue |
|------|------|-----------------|
| `contract_missing_clause.txt` | Legal Contract | Missing key clauses |
| `contract_missing_clause.pdf` | Legal Contract | PDF of above |
| `credit_agreement_missing_clause.txt` | Credit Agreement | Missing clause |
| `credit_agreement_expired_term_2019_REJECTED.txt` | Credit Agreement | Expired term (2019) |
| `credit_agreement_tiff_expired_2022_REJECTED.tiff` | Credit Agreement | Expired TIFF scan (2022) |
| `legal_contract_service_agreement_missing_dispute_resolution_REJECTED.txt` | Legal Contract | No dispute resolution |
| `legal_contract_incomplete_truncated_document_REJECTED.txt` | Legal Contract | Truncated / incomplete |
| `legal_contract_png_lowres_scan_REJECTED.png` | Legal Contract | Low-resolution OCR |
| `regulatory_filing_missing_risk_factors_and_auditor_REJECTED.txt` | Regulatory Filing | Missing risk factors |
| `employment_contract_missing_ip_assignment_REJECTED.txt` | Employment Contract | No IP assignment |
| `employment_contract_intern_summer_missing_termination_REJECTED.txt` | Employment Contract | No termination clause |
| `employment_contract_png_missing_noncompete_REJECTED.png` | Employment Contract | Missing non-compete (scanned) |
| `insurance_policy_directors_officers_missing_claims_procedure_REJECTED.txt` | Insurance Policy | Missing claims procedure |
| `partnership_agreement_missing_dissolution_clause_REJECTED.txt` | Partnership Agreement | No dissolution clause |

### Escalated Documents

| File | Type | Why escalated |
|------|------|---------------|
| `credit_agreement_syndicated_loan_500M_ESCALATE.txt` | Credit Agreement | $500 M transaction value |
| `credit_agreement_billion_dollar_syndicated_infrastructure_ESCALATE.txt` | Credit Agreement | $1 B+ infrastructure deal |

### Blocked Documents (Guardrail Tests)

| File | Threat type |
|------|-------------|
| `guardrail_prompt_injection_attempt_BLOCKED.txt` | Prompt injection |
| `guardrail_jailbreak_dan_roleplay_BLOCKED.txt` | DAN / roleplay jailbreak |
| `guardrail_pii_ssn_and_credit_card_BLOCKED.txt` | SSN + credit card numbers |
| `guardrail_pii_passport_iban_swift_BLOCKED.txt` | Passport + IBAN + SWIFT |
| `guardrail_sql_injection_attempt_BLOCKED.txt` | SQL injection patterns |
| `guardrail_pii_ssn_creditcard_scanned_image_BLOCKED.jpg` | PII in scanned image (OCR extracts PII) |

### Non-English Documents (Language Warning)

| File | Language | Behaviour |
|------|----------|-----------|
| `legal_contract_french_language_non_english_WARNING.txt` | French | WARNING logged; clause detection accuracy reduced |
| `legal_contract_spanish_nda_non_english_WARNING.txt` | Spanish | WARNING logged; clause detection accuracy reduced |
| `employment_contract_german_language_WARNING.txt` | German | WARNING logged; clause detection accuracy reduced |
| `partnership_agreement_tiff_french_scan_WARNING.tiff` | French | Scanned — OCR then language warning |

### Deduplication Test

| File | How to test |
|------|-------------|
| `credit_agreement_duplicate_resubmission_tests_dedup_cache.txt` | Upload once (fresh analysis) → upload again → second result shows **⚡ Cached Result** badge and returns instantly |

### Feedback Loop Test Documents

| File | Scenario | See |
|------|----------|-----|
| `fl_test_s1_nda_all_current_clauses_APPROVED.txt` | S1 — missing_rule | [Section 14](#14-demo-packages--ready-to-use-zip-files) |
| `fl_test_s1_nda_with_breach_notice_APPROVED.txt` | S1 — verification | [Section 14](#14-demo-packages--ready-to-use-zip-files) |
| `fl_test_s2_credit_unusual_phrasing_REJECTED_before_fix.txt` | S2 — comprehension_failure | [Section 14](#14-demo-packages--ready-to-use-zip-files) |
| `fl_test_s3_employment_all_current_clauses_APPROVED.txt` | S3 — missing_rule | [Section 14](#14-demo-packages--ready-to-use-zip-files) |
| `fl_test_s3_employment_with_remote_work_APPROVED.txt` | S3 — verification | [Section 14](#14-demo-packages--ready-to-use-zip-files) |

---

## 16. Supported File Formats

| Format | Extension(s) | Text extraction method |
|--------|-------------|----------------------|
| Plain text | `.txt` | Direct |
| PDF | `.pdf` | Text layer; OCR fallback via Tesseract |
| Word document | `.docx` | python-docx |
| Excel spreadsheet | `.xlsx` | openpyxl (all sheets concatenated) |
| PowerPoint | `.pptx` | python-pptx (all slide text) |
| HTML | `.html` | BeautifulSoup (tags stripped) |
| PNG image | `.png` | Tesseract OCR |
| JPEG image | `.jpg`, `.jpeg` | Tesseract OCR |
| TIFF image | `.tiff`, `.tif` | Tesseract OCR (per page) |

**Maximum file sizes:**

| Upload type | Limit |
|-------------|-------|
| Single document | **5 MB** |
| Batch ZIP (total) | **50 MB** |

---

## 17. Limitations and Known Issues

### AI / LLM Limitations

| Limitation | Detail |
|-----------|--------|
| **Non-English documents** | The AI is optimised for English. French, Spanish, German and other language documents will be processed but clause detection accuracy is significantly lower. A warning is logged when a non-English document is detected. |
| **Scanned image quality** | OCR accuracy depends on resolution and quality. Low-resolution or heavily watermarked scans may produce garbled text. Minimum recommended resolution: 150 DPI. |
| **Handwritten documents** | Handwritten text is not reliably extracted. Only typed / printed documents are supported. |
| **Very short documents** | Documents under ~200 words may not contain enough context for accurate classification or clause detection. |
| **Hallucination** | The LLM may occasionally report a clause as PRESENT when it is absent, or vice versa. The Faithfulness Score and Hallucination Risk indicators help flag unreliable analyses. Always cross-check REJECTED decisions for high-value documents. |
| **Clause wording variations** | Detection is semantic, not keyword-based. Highly unusual phrasing may be missed — use the 👎 feedback and comprehension_failure recommendations to teach the system over time. |

### Classification Limitations

| Limitation | Detail |
|-----------|--------|
| **Hybrid documents** | A document that is simultaneously a credit agreement and a regulatory filing will be classified as one type only. |
| **Novel document types** | Documents that don't match any of the 6 known categories are classified as `UNKNOWN` and no clause check is performed. |
| **Low routing confidence** | When routing confidence is below 50%, the classification may be incorrect. Always review the document type for low-confidence results. |
| **Auto-detection edge cases** | A document with both EU and US keywords will be assigned based on which set has more matches. Ambiguous documents fall back to Default. |

### System Limitations

| Limitation | Detail |
|-----------|--------|
| **Single-file upload limit** | 5 MB per file. Large PDFs with many pages may need to be split. |
| **Batch ZIP limit** | 50 files, 50 MB total. Submit multiple batch jobs for larger volumes. |
| **Analysis timeout** | Analyses cancelled automatically after 5 minutes. Very large documents with heavy OCR may time out. |
| **Override is irreversible** | Compliance Officer Overrides cannot be undone through the UI. |
| **No real-time collaboration locking** | Multiple users can analyse the same document simultaneously — no conflict detection. |
| **No email notifications** | The system does not send alerts when analyses complete or decisions change. |
| **History not searchable** | History shows all records in reverse chronological order. No search or filter yet. |

### Known Issues

| Issue | Workaround |
|-------|-----------|
| TIFF files with more than 4 pages are slow (OCR per page) | Split large TIFFs before uploading |
| Very large Excel files (>10 K rows) may exceed the 5 MB single-file limit | Export only the relevant sheets |
| Retry Diff table only appears after 2+ analysis attempts | By design — triggered only when faithfulness is low enough to warrant a retry |
| Browser back/forward navigation resets upload state | This is a single-page application; use the tab buttons within Sentinel |

---

## 18. Glossary

| Term | Definition |
|------|-----------|
| **Agent** | An AI node in the processing pipeline (Guardrail, Router, Compliance, Evaluator) |
| **Auto-Detection** | The backend's automatic selection of EU / US / Default regulatory profile based on document keywords — no manual selection required |
| **Batch Job** | A background task that processes all documents from a ZIP file concurrently |
| **Blacklist** | A list of rejected recommendations that will never be re-suggested for a given document type |
| **Clause** | A legally significant provision that must be present in a document of a given type and jurisdiction |
| **Comprehension Failure** | A feedback pattern where the LLM consistently misses a clause due to unusual phrasing — fixed by adding a few-shot example |
| **Compliance Officer Override** | A manual decision to approve a rejected document, recorded for audit |
| **Deduplication Cache** | A SHA-256 fingerprint store that returns instant results for previously seen documents |
| **Escalate** | A routing decision indicating the document needs human review due to complexity or transaction value |
| **Faithfulness Score** | A 0–100% measure of how accurately the AI's findings reflect the actual document content |
| **few_shot_examples.jsonl** | File storing approved comprehension corrections that are automatically injected into compliance prompts |
| **Guardrail** | A safety filter that blocks documents containing PII, prompt injection, or other prohibited content before any LLM processing |
| **Hallucination** | When an AI reports information that is not present in the source document |
| **Missing Rule** | A feedback pattern where a required clause is absent from the regulatory database — fixed by adding it |
| **OCR** | Optical Character Recognition — extracting text from scanned images using Tesseract |
| **Recommendation** | A proposed rule change generated by the review agent from negative feedback patterns |
| **regulatory_db.json** | The compliance database file listing required clauses per document type and tenant — patched live by approved recommendations |
| **Regulatory Profile / Tenant** | The jurisdiction-specific compliance rule set applied to a document (Default / EU / US) |
| **Routing Confidence** | How certain the AI is about its document type classification (0–100%) |
| **Retry Loop** | Automatic re-analysis when initial faithfulness is low, up to 3 attempts |
| **Review Agent** | The AI meta-agent that reads negative feedback, identifies patterns, and proposes regulatory database improvements |
| **SSE** | Server-Sent Events — the technology used to stream live agent logs to the browser in real time |
| **Trace ID** | A UUID uniquely identifying each analysis — used for audit, override, feedback, and PDF report tracking |
