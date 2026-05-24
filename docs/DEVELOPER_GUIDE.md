# Project Sentinel — Developer Guide

**Version:** Phase G (May 2026)  
**Audience:** Backend engineers, frontend developers, DevOps

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Repository Structure](#2-repository-structure)
3. [Local Development Setup](#3-local-development-setup)
4. [Backend Reference](#4-backend-reference)
5. [Frontend Reference](#5-frontend-reference)
6. [API Reference](#6-api-reference)
7. [LangGraph Pipeline](#7-langgraph-pipeline)
8. [Configuration & Environment Variables](#8-configuration--environment-variables)
9. [Database Schema](#9-database-schema)
10. [Regulatory Database](#10-regulatory-database)
11. [Testing](#11-testing)
12. [Deployment](#12-deployment)
13. [Extending Sentinel](#13-extending-sentinel)
14. [Security Model](#14-security-model)
15. [Limitations and Known Issues](#15-limitations-and-known-issues)

---

## 1. Architecture Overview

```
Browser (React 19 + Vite + TypeScript)
      │
      │  POST /api/analyze                (SSE stream — single doc)
      │  POST /api/analyze/batch          (202 + job_id — ZIP)
      │  POST /api/analyze/batch-reanalyze
      │  GET  /api/jobs/{job_id}
      │  GET  /api/history
      │  GET  /api/history/export         (CSV)
      │  GET  /api/history/{id}/report    (PDF)
      │  GET  /api/history/{id}/report/html
      │  POST /api/history/{id}/reanalyze (SSE)
      │  POST /api/history/{id}/set-decision
      │  POST /api/override/{trace_id}
      │  POST /api/feedback/{trace_id}
      │  GET  /api/feedback/summary
      │  GET  /api/feedback/export        (CSV)
      │  GET  /api/metrics/summary
      │  GET  /api/metrics                (Prometheus text)
      │  GET  /api/failures
      │  GET  /api/samples
      │  GET  /api/samples/{filename}
      │  GET  /api/clauses/{tenant_id}
      │  GET  /api/clauses/{tenant_id}/{doc_type}
      │  POST /api/clauses/{tenant_id}
      │  POST /api/ingest/email
      │  POST /api/admin/insights/run-review  (SSE)
      │  GET  /api/admin/insights/recommendations
      │  POST /api/admin/insights/{rec_id}/approve
      │  POST /api/admin/insights/{rec_id}/reject
      │  POST /api/admin/insights/{rec_id}/undo
      │  POST /api/auth/token
      │  GET  /api/health
      ▼
FastAPI (Python 3.12) — async, SSE, SlowAPI, structlog JSON logging
      │
      ├── SecurityHeadersMiddleware  (X-Frame, CSP, HSTS…)
      ├── SlowAPI rate limiter       (10 req/min per IP for /analyze; 2/min for batch)
      ├── CORS middleware
      ├── JWT auth (python-jose)     — analyst / admin roles
      │
      ▼
LangGraph StateGraph
      │
      ├── guardrail node   — PII / injection detection (no LLM call)
      ├── router node      — LLM document classification + auto-detects tenant (EU/US/default)
      ├── compliance node  — FAISS clause RAG + LLM detection + few-shot injection
      ├── evaluator node   — LLM-as-a-Judge: faithfulness + hallucination risk
      └── retry loop       — up to 3 re-runs when faithfulness < 0.7
            │
            ▼
      SQLite (aiosqlite, WAL mode)
        ├── analyses          — full analysis history
        ├── overrides         — compliance officer overrides
        ├── feedback          — 👍/👎 ratings + comments
        ├── doc_cache         — SHA-256 deduplication cache
        ├── batch_jobs        — batch processing state
        ├── recommendations   — AI review agent proposals
        └── recommendation_blacklist — rejected proposals (never re-suggested)
      FAISS  — in-process embedding index for clause retrieval
      LLM factory (create_llm) — ChatOllama local or Ollama Cloud via OLLAMA_BASE_URL

AI Feedback Loop (on-demand, no scheduling):
  👎 comment → correction_examples.jsonl (background task, gitignored)
  POST /api/admin/insights/run-review → LLM meta-analysis of patterns
    → Recommendation (missing_rule | comprehension_failure)
    → ✓ Approve: patches regulatory_db.json OR appends few_shot_examples.jsonl (live, no restart)
    → ✗ Reject:  blacklisted (doc_type, proposed) pair — never re-suggested
    → ↩ Undo:    physical file reversal + recommendation re-opened
```

**Key technology choices:**

| Layer | Technology | Why |
|-------|-----------|-----|
| Backend framework | FastAPI | Async-native, SSE support, OpenAPI docs |
| AI orchestration | LangGraph | Stateful graph with retry feedback loops |
| LLM | Ollama (ChatOllama) | Local-first; env-var switchable to Ollama Cloud |
| Vector search | FAISS | Fast in-process, no external service |
| Database | SQLite + aiosqlite | Zero-ops, WAL mode for concurrent reads |
| Frontend | React 19 + Vite + TypeScript | Fast HMR, strict types |
| Testing (backend) | pytest + pytest-asyncio | Async-first |
| Testing (frontend) | Vitest + Testing Library | Native Vite integration |
| Logging | structlog | JSON-structured, trace_id threaded through |
| Rate limiting | slowapi | Decorator-based, minimal setup |
| Auth | python-jose + passlib bcrypt | JWT with analyst / admin RBAC |

---

## 2. Repository Structure

```
.
├── backend/
│   ├── main.py                    # FastAPI app, CORS, middleware, startup
│   ├── agents/
│   │   ├── state.py               # AgentState TypedDict — all pipeline fields
│   │   ├── graph.py               # LangGraph StateGraph definition
│   │   ├── router_agent.py        # Guardrail + Router nodes, auto-tenant detection
│   │   ├── compliance_agent.py    # Compliance node, FAISS RAG, few-shot injection
│   │   ├── eval_judge.py          # LLM-as-a-Judge evaluator node
│   │   ├── expiry_agent.py        # Expiry date extraction node
│   │   ├── review_agent.py        # AI feedback loop meta-agent
│   │   └── llm_factory.py         # LLM provider abstraction (env-var driven)
│   ├── api/
│   │   ├── routes.py              # All FastAPI endpoints + SSE + HTML/PDF reports
│   │   ├── auth.py                # JWT login + bcrypt user store + role guards
│   │   ├── auth_router.py         # POST /api/auth/token
│   │   └── email_ingestor.py      # HTML-strip helper for /api/ingest/email
│   ├── data/
│   │   ├── regulatory_db.json     # Clause requirements per tenant + doc type
│   │   ├── few_shot_examples.jsonl  # Approved comprehension corrections (runtime)
│   │   ├── correction_examples.jsonl # Negative feedback log (runtime, gitignored)
│   │   ├── guardrails.py          # PII regexes + injection pattern lists
│   │   ├── embeddings.py          # FAISS index build + search
│   │   ├── history_store.py       # SQLite CRUD: analyses, feedback, cache, recs
│   │   ├── pdf_extractor.py       # PDF → text (pdfminer + Tesseract OCR fallback)
│   │   ├── file_extractor.py      # docx/xlsx/pptx/html/image → text dispatch
│   │   ├── language_detector.py   # langdetect wrapper
│   │   ├── metrics.py             # Prometheus-style counters (in-process)
│   │   ├── anonymizer.py          # PII redaction before LLM submission
│   │   └── report_generator.py    # reportlab PDF compliance report builder
│   ├── prompts/
│   │   ├── router_prompt.json     # Router LLM prompt template (versioned)
│   │   ├── compliance_prompt.json # Compliance LLM prompt template
│   │   └── evaluator_prompt.json  # Evaluator LLM prompt template
│   ├── tests/
│   │   ├── unit/                  # 20 unit test modules (~480 tests)
│   │   └── integration/           # 3 integration modules (~115 tests)
│   ├── requirements.txt
│   ├── .env.example               # All supported environment variables + comments
│   └── docker-compose.prod.yml    # Production compose (no local Ollama)
├── frontend/sentinel-ui/
│   ├── src/
│   │   ├── App.tsx                # 6-tab shell + SSE handler + override + reanalyze
│   │   ├── main.tsx               # React entry point
│   │   └── components/
│   │       ├── DocumentUpload.tsx      # Drag-and-drop file input, keyboard accessible
│   │       ├── WorkflowStream.tsx      # Live agent log, colour-coded node labels
│   │       ├── StatusBadge.tsx         # Decision badge (colour per decision type)
│   │       ├── ConfidenceGauge.tsx     # SVG arc gauge for routing confidence
│   │       ├── ClauseDiffViewer.tsx    # Side-by-side clause diff across retry attempts
│   │       ├── FeedbackWidget.tsx      # Two-step 👍/👎 — positive submits instantly; negative reveals comment textarea
│   │       ├── HistoryPanel.tsx        # Paginated history: 9 cols incl. PDF report + re-analyse
│   │       ├── InsightsDashboard.tsx   # AI feedback loop: stats, feedback table, run-review SSE, approve/reject/undo
│   │       ├── BatchUpload.tsx         # ZIP batch upload, progress bar, per-file results
│   │       ├── MetricsPanel.tsx        # Observability: decisions, faithfulness, risk, 7-day trend
│   │       └── HelpPanel.tsx           # Inline user documentation + sample catalogue
│   └── src/__tests__/            # 12 test files, 173 tests
│       ├── App.test.tsx
│       ├── BatchUpload.test.tsx
│       ├── ClauseDiffViewer.test.tsx
│       ├── ConfidenceGauge.test.tsx
│       ├── DocumentUpload.test.tsx
│       ├── FeedbackWidget.test.tsx
│       ├── HistoryPanel.test.tsx
│       ├── InsightsDashboard.test.tsx
│       ├── MetricsPanel.test.tsx
│       ├── StatusBadge.test.tsx
│       └── WorkflowStream.test.tsx
├── infra/
│   ├── main.tf                    # Terraform: EC2 t3.micro, S3, CloudFront, security groups
│   ├── variables.tf               # Input variables (region, instance_type, ollama_*)
│   ├── outputs.tf                 # cloudfront_url, ec2_public_ip
│   ├── user_data.sh               # EC2 bootstrap: Docker + app startup
│   └── deploy-backend.sh          # Idempotent EC2 deploy script (git pull + systemd restart)
├── sample_docs/                   # 55+ labelled test documents (all types + formats)
│   ├── fl_test_s*.txt             # Feedback loop test documents (5 files)
│   └── ...                        # All other sample documents
├── docs/
│   ├── USER_GUIDE.md              # End-user documentation
│   ├── DEVELOPER_GUIDE.md         # This file
│   └── FEEDBACK_LOOP_TESTING_GUIDE.md  # Step-by-step AI feedback loop demo
├── sample_docs batch demo.zip     # 51-document batch upload demo package
├── sample_docs feedback loop demo.zip  # 5-document feedback loop demo package
├── .github/workflows/
│   ├── deploy.yml                 # Code delivery: test → build → S3 sync → EC2 rsync (every push)
│   └── infra.yml                  # Infrastructure: terraform plan/apply (infra/** changes only)
└── .gitignore
```

---

## 3. Local Development Setup

### Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.12+ | Backend runtime |
| Node.js | 20+ | Frontend build |
| Ollama | latest | Local LLM server |
| Tesseract | 5.x | OCR for image files |
| Git | any | Version control |

### Backend

```powershell
# Create and activate virtual environment
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1       # Windows
# source .venv/bin/activate      # Linux / macOS

# Install dependencies
pip install -r requirements.txt

# Copy environment variables
cp .env.example .env
# Edit .env: set OLLAMA_MODEL, RATE_LIMIT etc.

# Run development server
uvicorn main:app --reload --port 8000
```

API available at `http://localhost:8000`. Interactive OpenAPI docs at `http://localhost:8000/docs`.

### Frontend

```powershell
cd frontend\sentinel-ui
npm install
npm run dev
# Dev server: http://localhost:5173
# Vite proxies /api/* → http://localhost:8000 automatically
```

### LLM

```bash
ollama pull gemma3:4b          # ~3 GB, CPU-friendly for dev
# ollama pull gemma3:27b       # ~32 GB, better accuracy for prod
ollama serve                   # port 11434
```

Set `OLLAMA_MODEL=gemma3:4b` in `backend/.env` for local development.

---

## 4. Backend Reference

### Tenant Auto-Detection

There is **no manual tenant_id parameter** on the `/api/analyze` endpoint. The backend automatically detects the regulatory jurisdiction from the document text:

```python
def _infer_tenant(text: str) -> str:
    """Auto-detect EU vs US regulatory context from document keywords."""
    sample = text[:8000]
    eu_hits = len(_EU_KEYWORDS.findall(sample))   # GDPR, Solvency II, MiFID…
    us_hits = len(_US_KEYWORDS.findall(sample))   # Dodd-Frank, SOX, SEC…
    if eu_hits > us_hits:
        return "EU"
    if us_hits > eu_hits:
        return "US"
    return "default"
```

The detected tenant is passed into the LangGraph pipeline as `AgentState.tenant_id` and used to load the correct clause list from `regulatory_db.json`.

### `AgentState` (`backend/agents/state.py`)

All pipeline data flows through a single typed dictionary:

```python
class AgentState(TypedDict):
    # Input
    raw_text: str                              # Extracted document text
    tenant_id: str                             # "default" | "EU" | "US" (auto-detected)
    trace_id: str                              # UUID for tracking

    # Guardrail
    sanitized: bool                            # True if guardrail passed

    # Router
    doc_type: str                              # Detected document category
    routing_confidence: float                  # 0.0–1.0 classification confidence
    language: str                              # ISO 639-1 language code ("en", "fr", …)

    # Compliance
    required_clauses: list                     # Loaded from regulatory_db.json
    compliance_output: str                     # Raw LLM compliance text
    clause_results: list                       # Current attempt: [{clause, status, evidence}]
    clause_results_history: list               # All retry attempts (list of lists)

    # Evaluator
    evaluation_score: float                    # Faithfulness 0.0–1.0
    hallucination_risk: str                    # "low" | "medium" | "high"

    # Control flow
    final_decision: str                        # "APPROVED" | "REJECTED" | "ESCALATE" | …
    retry_count: int                           # Feedback loop counter (max 3)

    # Expiry
    expiry_date: str                           # Extracted expiry date or ""

    # Logging
    logs: Annotated[list, operator.add]        # Accumulating log entries (SSE stream)
```

### `llm_factory.py`

All agent nodes obtain an LLM instance via:

```python
from agents.llm_factory import create_llm

llm = create_llm(temperature=0.0)
```

The factory reads `LLM_PROVIDER`, `OLLAMA_MODEL`, and `OLLAMA_BASE_URL` from the environment. Empty `OLLAMA_BASE_URL` → local Ollama on port 11434; set it to an Ollama Cloud URL for production.

### Guardrails (`backend/data/guardrails.py`)

Documents are screened before reaching the LLM:

- **Injection patterns** — 9+ regex patterns blocking prompt injection and jailbreak attempts
- **PII patterns** — SSN, credit card, passport, IBAN, SWIFT detection
- **Public alias** — `INJECTION_PATTERNS` list exported for test inspection

Blocked documents receive `final_decision = "BLOCKED"` and `sanitized = False`. No LLM call is made.

### Email Ingestion (`backend/api/email_ingestor.py`)

`POST /api/ingest/email` accepts `{subject, body, tenant_id}`. The `strip_html()` helper removes HTML tags from email bodies before feeding the plain text through the standard compliance pipeline. Useful for forwarding contracts to a compliance inbox.

---

## 5. Frontend Reference

### Six-Tab Architecture

`App.tsx` manages a single `activeTab` state: `"analyze" | "history" | "batch" | "metrics" | "insights" | "help"`.

The **Insights** tab uses a distinct purple colour in the navigation bar (`#7c3aed`) to signal its admin-only nature.

### Component Map

| Component | File | Responsibility |
|-----------|------|---------------|
| `App` | `App.tsx` | 6-tab shell, SSE stream handler, override, re-analyse from history |
| `DocumentUpload` | `DocumentUpload.tsx` | Drag-and-drop file input, keyboard accessible |
| `WorkflowStream` | `WorkflowStream.tsx` | Live log display with colour-coded node labels, LIVE badge |
| `StatusBadge` | `StatusBadge.tsx` | Decision badge (colour per decision type) |
| `ConfidenceGauge` | `ConfidenceGauge.tsx` | SVG arc gauge for routing confidence (0–100%) |
| `ClauseDiffViewer` | `ClauseDiffViewer.tsx` | Side-by-side clause status diff across retry attempts |
| `FeedbackWidget` | `FeedbackWidget.tsx` | Two-step 👍/👎: positive submits instantly; negative reveals 500-char textarea |
| `HistoryPanel` | `HistoryPanel.tsx` | Paginated history table: 9 columns including Feedback, ↓ PDF, ↺ Fresh |
| `InsightsDashboard` | `InsightsDashboard.tsx` | AI feedback loop control centre: stats cards, feedback table, run-review SSE, recommendations with approve/reject/undo |
| `BatchUpload` | `BatchUpload.tsx` | ZIP upload, job polling, progress bar, per-file results table |
| `MetricsPanel` | `MetricsPanel.tsx` | Observability dashboard: decisions, faithfulness, risk distribution, 7-day trend |
| `HelpPanel` | `HelpPanel.tsx` | Inline user documentation and sample document catalogue |

### SSE Stream Format

The backend sends `text/event-stream` with two event types:

```
data: {"type": "log", "node": "router", "message": "Classified as CREDIT_AGREEMENT (tenant=EU)"}

data: {"type": "done", "final_decision": "APPROVED", "doc_type": "CREDIT_AGREEMENT",
       "evaluation_score": 0.91, "hallucination_risk": "low",
       "routing_confidence": 0.87, "trace_id": "abc-123", "sanitized": true,
       "clause_results": [...], "clause_results_history": [[...], [...]],
       "from_cache": false}
```

The frontend's `handleFile()` in `App.tsx` parses these events and updates React state. A 5-minute `AbortController` timeout cancels stalled streams.

### Environment Variables (frontend)

| Variable | Default | Purpose |
|----------|---------|---------|
| `VITE_API_BASE_URL` | `""` (empty) | API base URL; empty = same origin (production proxy via nginx/CloudFront). Set to `http://localhost:8000` only in `.env.local` if backend is on a different port. |

---

## 6. API Reference

Base URL: `http://localhost:8000` (dev) / CloudFront URL (prod)

### `POST /api/analyze`

Submit a document for analysis. Returns an SSE stream.

**Request:** `multipart/form-data`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | file | Yes | Document file (max 5 MB; see supported formats) |
| `callback_url` | string | No | Webhook URL to POST completed result to (SSRF-protected) |
| `force_refresh` | bool | No | If `true`, delete cache entry before analysis (default: `false`) |

> **Note:** There is no `tenant_id` field. The regulatory profile (EU / US / Default) is auto-detected from the document content.

**Response:** `text/event-stream` — see [SSE Stream Format](#sse-stream-format) above.

**Rate limit:** 10 requests per minute per IP.

**Error codes:**

| Code | Reason |
|------|--------|
| 400 | Unsupported file type, empty file, or extraction failure |
| 413 | File exceeds 5 MB |

---

### `GET /api/history`

Retrieve past analyses.

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 50 | Number of records to return (1–1000) |

**Response:** `application/json` — array of analysis records:

```json
[
  {
    "trace_id": "abc-123",
    "filename": "contract.txt",
    "doc_type": "LEGAL_CONTRACT",
    "decision": "APPROVED",
    "faithfulness": 0.92,
    "risk": "low",
    "created_at": "2026-05-21T10:00:00Z",
    "feedback_rating": "positive"
  }
]
```

---

### `GET /api/history/export`

Downloads all analyses as a CSV file.

**Response:** `text/csv`

---

### `GET /api/history/{trace_id}/report`

Generate and download a PDF compliance report for a specific analysis.

**Response:** `application/pdf` — reportlab-generated report including doc type, decision, clause table, faithfulness score, trace ID, and timestamp.

---

### `GET /api/history/{trace_id}/report/html`

Returns the compliance report as an inline HTML page (browser-viewable).

---

### `POST /api/history/{trace_id}/reanalyze`

Re-runs the full analysis pipeline for a previously analysed document stored in the history. Returns an SSE stream identical to `/api/analyze`. Cache is bypassed.

---

### `POST /api/history/{trace_id}/set-decision`

Directly set the decision for a history record (admin use).

**Request body:**

```json
{ "decision": "APPROVED" }
```

Valid values: `"APPROVED"`, `"REJECTED"`, `"ESCALATE"`.

---

### `POST /api/override/{trace_id}`

Apply a compliance officer override to a past analysis.

**Request body:** `application/json`

```json
{ "decision": "APPROVED" }
```

**Response:** `200 OK`

---

### `POST /api/feedback/{trace_id}`

Submit a rating for a completed analysis.

**Request body:**

```json
{ "rating": "negative", "comment": "Indemnity clause was clearly present in Section 6." }
```

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `rating` | `"positive"` \| `"negative"` | Yes | Enum |
| `comment` | string | No | Truncated to 500 chars |

**Response:** `201 Created` — `{"status": "recorded"}`

---

### `GET /api/feedback/summary`

Returns all feedback entries joined with their analysis record.

**Response:** `application/json` — array with fields: `trace_id`, `rating`, `comment`, `created_at`, `filename`, `decision`, `doc_type`.

---

### `GET /api/feedback/export`

Downloads all feedback as CSV.

**Response:** `text/csv` — columns: `trace_id`, `filename`, `doc_type`, `decision`, `rating`, `comment`, `created_at`.

---

### `POST /api/analyze/batch`

Submit a ZIP file for concurrent multi-document analysis. Returns immediately with a job ID.

**Request:** `multipart/form-data`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | file | Yes | ZIP file (max 50 MB, max 50 files) |
| `force_refresh` | bool | No | Bypass cache for all files (default: `false`) |

**Response:** `202 Accepted` — `{"job_id": "...", "total": 12}`

**Error codes:**

| Code | Reason |
|------|--------|
| 400 | Not a ZIP file or corrupted archive |
| 413 | ZIP exceeds 50 MB |
| 422 | > 50 files, disallowed extension, or ZIP slip path detected |

**Security:** ZIP slip protection rejects any entry with `..` in path or starting with `/`.

---

### `GET /api/jobs/{job_id}`

Poll the status of a batch job.

**Response:**

```json
{
  "job_id": "550e8400-...",
  "status": "running",
  "total": 12,
  "completed": 7,
  "results": [
    { "filename": "contract.pdf", "trace_id": "...", "final_decision": "APPROVED",
      "evaluation_score": 0.91, "from_cache": false }
  ],
  "created_at": "2026-05-21T14:00:00Z"
}
```

`status` transitions: `"pending"` → `"running"` → `"completed"` | `"failed"`. Unknown job → 404.

---

### `GET /api/metrics/summary`

Aggregate observability metrics.

**Response:**

```json
{
  "total": 142,
  "by_decision": { "APPROVED": 98, "REJECTED": 30, "ESCALATE": 10, "BLOCKED": 4 },
  "avg_faithfulness": 0.847,
  "risk_distribution": { "low": 85, "medium": 42, "high": 15 },
  "daily_last_7_days": { "2026-05-15": 12, "2026-05-16": 18 }
}
```

---

### `GET /api/clauses/{tenant_id}`

List all required clause sets for a tenant.

**Response:** `application/json` — the full clause map for that tenant from `regulatory_db.json`.

---

### `GET /api/clauses/{tenant_id}/{doc_type}`

Get required clauses for a specific tenant + document type combination.

**Response:** `application/json` — `{"required_clauses": ["clause a", "clause b", ...]}`

---

### `POST /api/clauses/{tenant_id}`

Update the required clauses for a tenant (replaces the entire tenant entry).

**Request body:** `application/json` — the new clause map for that tenant.

**Response:** `200 OK`

---

### `POST /api/ingest/email`

Ingest a document forwarded by email.

**Request body:** `application/json`

```json
{
  "subject": "Contract for review",
  "body": "<p>Please review the attached NDA...</p>",
  "tenant_id": "default"
}
```

HTML is stripped from the body before processing. The plain text is run through the standard compliance pipeline and returns an SSE stream.

---

### `POST /api/admin/insights/run-review`

Runs the AI review agent on accumulated negative feedback. Returns an SSE stream.

**Query parameter:** `min_evidence` (integer, default: `1`) — minimum feedback entries per doc type required before the agent acts.

**Response:** `text/event-stream` — log lines + final `{"type": "done"}` event.

---

### `GET /api/admin/insights/recommendations`

List recommendations filtered by status.

**Query parameter:** `status` — `pending` | `approved` | `rejected` | `undone` | `all` (default: `pending`)

**Response:** `application/json` — array of recommendation objects:

```json
[
  {
    "rec_id": "550e8400-...",
    "doc_type": "LEGAL_CONTRACT",
    "rec_type": "missing_rule",
    "proposed": "data breach notification clause",
    "evidence_count": 2,
    "confidence": "high",
    "rationale": "2 analysts flagged NDAs approving without breach notification language.",
    "status": "pending",
    "created_at": "2026-05-21T10:00:00Z",
    "resolved_at": null
  }
]
```

---

### `POST /api/admin/insights/{rec_id}/approve`

Approve a pending recommendation and apply the change immediately (no restart needed):

- `missing_rule` → appends clause to `regulatory_db.json` + calls `reload_reg_db()`
- `comprehension_failure` → appends entry to `few_shot_examples.jsonl`

**Response:** `200 OK` — `{"status": "approved", "rec_id": "...", "action": "approved"}`

---

### `POST /api/admin/insights/{rec_id}/reject`

Reject a recommendation and blacklist the `(doc_type, proposed)` pair permanently.

**Response:** `200 OK` — `{"status": "rejected", "rec_id": "..."}`

---

### `POST /api/admin/insights/{rec_id}/undo`

Reverse an approved or rejected recommendation:

- Approved `missing_rule` → removes clause from `regulatory_db.json` + `reload_reg_db()`
- Approved `comprehension_failure` → removes entry from `few_shot_examples.jsonl`
- Rejected → status reset to `pending`; blacklist entry removed

**Response:** `200 OK` — `{"status": "undone"}` or `{"status": "reopened"}` for rejected→pending

---

### `POST /api/auth/token`

Obtain a JWT access token.

**Request body:** `application/x-www-form-urlencoded`

```
username=analyst&password=password123
```

**Response:** `application/json`

```json
{ "access_token": "eyJhbGci...", "token_type": "bearer" }
```

Tokens are valid for 60 minutes. Include as `Authorization: Bearer <token>` on protected endpoints.

---

### `GET /api/health`

Health check endpoint.

**Response:**

```json
{
  "status": "ok",
  "checks": { "sqlite": true, "llm": true, "faiss": true }
}
```

`status` is `"degraded"` if any check returns `false`.

---

## 7. LangGraph Pipeline

The pipeline is defined in `backend/agents/graph.py` as a `StateGraph`:

```
START
  │
  ▼
guardrail ──(blocked)──► END
  │
  │ (pass)
  ▼
router        ← sets doc_type, routing_confidence, language, tenant_id (auto-detected)
  │
  ▼
compliance    ← loads clauses from regulatory_db.json[tenant_id][doc_type]
  │            ← injects few_shot_examples.jsonl into prompt
  │
  ▼
evaluator ──(score ≥ 0.7 or retry_count ≥ 3)──► END
  │
  │ (score < 0.7 and retry_count < 3)
  ▼
increment_retry ──► compliance   (feedback loop, max 3 iterations)
```

### Node Responsibilities

| Node | File | What it does |
|------|------|--------------|
| `guardrail` | `router_agent.py` | Checks PII + injection patterns; sets `sanitized = False` if blocked |
| `router` | `router_agent.py` | Classifies doc type + confidence; auto-detects tenant via `_infer_tenant()` |
| `compliance` | `compliance_agent.py` | Loads required clauses, FAISS RAG search, LLM clause detection + few-shot injection |
| `evaluator` | `eval_judge.py` | Second LLM call: faithfulness score + hallucination risk; sets `final_decision` |
| `increment_retry` | `graph.py` | Increments `retry_count`; appends current `clause_results` to `clause_results_history` |

### Adding a New Node

1. Create the node function:
   ```python
   def my_node(state: AgentState) -> dict:
       return {"my_field": computed_value}
   ```
2. Register in `graph.py`:
   ```python
   builder.add_node("my_node", my_node)
   builder.add_edge("evaluator", "my_node")
   ```
3. Add any new fields to `AgentState` in `state.py`.
4. Write tests in `tests/unit/test_my_node.py`.

---

## 8. Configuration & Environment Variables

Copy `backend/.env.example` to `backend/.env`:

```env
# ── LLM Provider ─────────────────────────────────────────────────────────────
LLM_PROVIDER=ollama                  # Only "ollama" is currently supported
OLLAMA_MODEL=gemma3:27b              # Any Ollama-compatible model
OLLAMA_BASE_URL=                     # Empty = local port 11434; set to Ollama Cloud URL in prod

# ── Database ──────────────────────────────────────────────────────────────────
SQLITE_PATH=./sentinel.db            # Path to SQLite database file

# ── Rate limiting ─────────────────────────────────────────────────────────────
RATE_LIMIT=10/minute                 # Format: "{count}/{period}"

# ── Security ──────────────────────────────────────────────────────────────────
ALLOWED_ORIGINS=http://localhost:5173
HSTS_MAX_AGE=31536000                # HSTS max-age in seconds (HTTPS only)
SENTINEL_API_KEY=                    # Optional static API key for all /api/* endpoints

# ── File upload ───────────────────────────────────────────────────────────────
MAX_UPLOAD_BYTES=5242880             # 5 MB (single file); batch ZIP limit is separate (50 MB)

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_LEVEL=INFO                       # DEBUG | INFO | WARNING | ERROR

# ── AI Feedback Loop ──────────────────────────────────────────────────────────
REVIEW_MIN_EVIDENCE=1                # Min 👎 per doc type before review agent acts
                                     # Set to 1 for demos; raise to 3–5 in production
```

**Production (Ollama Cloud):**

```env
OLLAMA_BASE_URL=https://your-ollama-cloud-endpoint.example.com
OLLAMA_MODEL=gemma3:27b
ALLOWED_ORIGINS=https://your-cloudfront-url.cloudfront.net
```

---

## 9. Database Schema

SQLite at `SQLITE_PATH` (default `./sentinel.db`). Managed by `backend/data/history_store.py`.

### `analyses`

```sql
CREATE TABLE analyses (
    trace_id     TEXT PRIMARY KEY,
    filename     TEXT NOT NULL,
    doc_type     TEXT NOT NULL,
    decision     TEXT NOT NULL,
    faithfulness REAL NOT NULL,
    risk         TEXT NOT NULL,
    created_at   TEXT NOT NULL   -- ISO 8601 UTC
);
```

### `overrides`

```sql
CREATE TABLE overrides (
    trace_id   TEXT PRIMARY KEY,
    decision   TEXT NOT NULL,
    created_at TEXT NOT NULL
);
```

### `doc_cache` (deduplication)

```sql
CREATE TABLE doc_cache (
    doc_hash   TEXT PRIMARY KEY,  -- SHA-256 of raw file bytes
    payload    TEXT NOT NULL,     -- DonePayload as JSON
    cached_at  TEXT NOT NULL
);
```

### `feedback`

```sql
CREATE TABLE feedback (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    trace_id   TEXT NOT NULL,
    rating     TEXT NOT NULL CHECK(rating IN ('positive', 'negative')),
    comment    TEXT,
    created_at TEXT NOT NULL
);
```

Multiple ratings per trace_id are allowed; `get_feedback()` returns the most recent.

### `batch_jobs`

```sql
CREATE TABLE batch_jobs (
    job_id     TEXT PRIMARY KEY,
    status     TEXT NOT NULL DEFAULT 'pending',
    total      INTEGER NOT NULL,
    completed  INTEGER NOT NULL DEFAULT 0,
    results    TEXT NOT NULL DEFAULT '[]',  -- JSON array, updated incrementally
    created_at TEXT NOT NULL
);
```

### `recommendations`

```sql
CREATE TABLE recommendations (
    rec_id         TEXT PRIMARY KEY,   -- UUID
    doc_type       TEXT NOT NULL,
    rec_type       TEXT NOT NULL,      -- 'missing_rule' | 'comprehension_failure'
    proposed       TEXT NOT NULL,      -- clause name or JSON object
    evidence_count INTEGER NOT NULL,
    confidence     TEXT NOT NULL,      -- 'high' | 'medium' | 'low'
    rationale      TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'pending',  -- pending|approved|rejected|undone
    created_at     TEXT NOT NULL,
    resolved_at    TEXT               -- NULL until approved/rejected/undone
);
```

**Approve logic:**
- `missing_rule` → clause appended to `regulatory_db.json`; `reload_reg_db()` called (no restart needed)
- `comprehension_failure` → entry appended to `few_shot_examples.jsonl`; injected into next compliance prompt automatically

**Undo logic:**
- Approved `missing_rule` → `_remove_clause_from_reg_db()` removes the clause; `reload_reg_db()` called
- Approved `comprehension_failure` → `_remove_few_shot_example(rec_id)` rewrites JSONL without that entry
- Rejected → status reset to `pending`; blacklist entry deleted

### `recommendation_blacklist`

```sql
CREATE TABLE recommendation_blacklist (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_type   TEXT NOT NULL,
    proposed   TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(doc_type, proposed)
);
```

Populated on reject. Review agent checks `is_blacklisted(doc_type, proposed)` before creating any new recommendation — blacklisted pairs are never re-suggested.

---

## 10. Regulatory Database

`backend/data/regulatory_db.json` — the live compliance rule store. Edited directly to add tenants, document types, or clauses. Patched in-place by the approve action (no file replacement, no restart).

```json
{
  "default": {
    "CREDIT_AGREEMENT": {
      "required_clauses": [
        "governing law clause",
        "events of default clause",
        "indemnification clause",
        "representations and warranties"
      ]
    },
    "LEGAL_CONTRACT": {
      "required_clauses": [
        "force majeure clause",
        "limitation of liability",
        "dispute resolution clause"
      ]
    },
    "EMPLOYMENT_CONTRACT": { ... },
    "INSURANCE_POLICY":    { ... },
    "PARTNERSHIP_AGREEMENT": { ... },
    "REGULATORY_FILING":   { ... }
  },
  "EU": {
    "CREDIT_AGREEMENT": {
      "required_clauses": [
        "governing law clause",
        "events of default clause",
        "indemnification clause",
        "representations and warranties",
        "GDPR data processing agreement"    ← EU-specific addition
      ]
    },
    ...
  },
  "US": {
    "REGULATORY_FILING": {
      "required_clauses": [
        "risk factors section",
        "management discussion and analysis",
        "auditor opinion",
        "SOX Section 302 certification",     ← US-specific addition
        "SOX Section 906 certification"      ← US-specific addition
      ]
    },
    ...
  }
}
```

### Adding a New Document Type

1. Add the type key under each tenant in `regulatory_db.json`.
2. Add the type string to `VALID_CATEGORIES` in `backend/agents/router_agent.py`.
3. Update `backend/prompts/router_prompt.json` to include the new type.
4. Add sample documents to `sample_docs/`.
5. Add tests to `tests/unit/test_regulatory_db.py`.

### Adding a New Tenant / Regulatory Profile

1. Add a new top-level key to `regulatory_db.json` mirroring the `"default"` structure.
2. Add keyword patterns to `_EU_KEYWORDS` or `_US_KEYWORDS` in `routes.py`, or add a new regex set for the new jurisdiction.
3. No other code changes required — the backend picks up the new tenant automatically.

---

## 11. Testing

### Running Tests

```powershell
# Backend — all tests (~595 total)
cd backend
python -m pytest tests/ -v

# Backend — unit tests only
pytest tests/unit/ -v

# Backend — integration tests only
pytest tests/integration/ -v

# Frontend (173 tests)
cd frontend\sentinel-ui
node_modules\.bin\vitest run

# Frontend — watch mode
node_modules\.bin\vitest
```

### Test Counts (Phase G)

| Suite | Tests | Coverage |
|-------|-------|---------|
| Backend unit | ~480 | All agent nodes, data layer, auth + RBAC, guardrails, metrics, feedback loop, review agent, insights endpoints, PDF report, email ingestion, clause API |
| Backend integration | ~115 | Full pipeline end-to-end, all API routes, JWT auth flow |
| Frontend | 173 | All 11 components + App (SSE, override, re-analyse, approve/reject/undo) |
| **Total** | **~768** | |

All LLM calls are mocked — no Ollama required to run tests.

### Test Structure

```
backend/tests/
├── unit/
│   ├── test_anonymizer.py          # PII redaction
│   ├── test_batch.py               # Batch upload endpoints + ZIP security (slip, size, extension)
│   ├── test_dedup.py               # Deduplication cache (SHA-256 hit/miss/force-refresh)
│   ├── test_eval_parse.py          # Evaluator output parsing + score clamping
│   ├── test_expiry.py              # Expiry date extraction + validation
│   ├── test_feedback.py            # Feedback store + /api/feedback/* + insights endpoints
│   │                               #   incl. approve/reject/undo, blacklist, few-shot JSONL patch
│   ├── test_file_extractor.py      # docx/xlsx/pptx/html/image extraction
│   ├── test_graph_routing.py       # LangGraph routing decisions
│   ├── test_guardrails.py          # PII + injection pattern detection
│   ├── test_history_store.py       # SQLite CRUD + cache sanitisation
│   ├── test_language_detection.py  # langdetect wrapper
│   ├── test_llm_factory.py         # LLM provider abstraction (env-var driven)
│   ├── test_llm_utils.py           # LLM response capping
│   ├── test_metrics.py             # Prometheus label escaping
│   ├── test_metrics_summary.py     # GET /api/metrics/summary
│   ├── test_pdf_extractor.py       # PDF → text + OCR fallback
│   ├── test_regulatory_db.py       # Schema validation + tenant structure
│   ├── test_review_agent.py        # Review meta-agent (mocked LLM + mocked DB)
│   └── test_structured_logging.py  # structlog JSON output + trace_id threading
└── integration/
    ├── test_graph_flow.py          # End-to-end pipeline runs (mocked LLM)
    ├── test_routes.py              # All FastAPI endpoints via httpx.AsyncClient
    └── test_rbac.py               # JWT auth + analyst/admin role-based access control
```

### Writing New Tests

- **Unit tests** — mock the LLM using `monkeypatch` or `unittest.mock.patch`. Never hit a real Ollama server.
- **Integration tests** — use `httpx.AsyncClient(app=app, base_url="http://test")`. Still mock the LLM.
- **Frontend tests** — use `vi.stubGlobal('fetch', vi.fn())` to mock API calls. Never make real HTTP requests from tests.

---

## 12. Deployment

### Docker (local / staging)

```bash
cd backend
docker compose up --build
# FastAPI on port 8000; Ollama must run separately
```

### AWS Free Tier (Terraform + manual rsync)

Infrastructure is defined in `infra/`. Provisions EC2 t3.micro + S3 + CloudFront.

```bash
cd infra
terraform init
terraform plan -var="ollama_base_url=https://your-cloud-ollama-url"
terraform apply -auto-approve \
  -var="ollama_base_url=https://your-cloud-ollama-url" \
  -var="ollama_model=gemma3:27b"

terraform output cloudfront_url   # Frontend URL
terraform output ec2_public_ip    # Backend SSH / health check

# Tear down (avoid charges)
terraform destroy -auto-approve
```

### Idempotent EC2 Backend Deploy

`infra/deploy-backend.sh` is safe to re-run at any time:

```bash
bash infra/deploy-backend.sh
```

The script:
1. Detects the public IP dynamically (`curl checkip.amazonaws.com`)
2. `git reset --hard origin/main` on the EC2 (idempotent, no merge conflicts)
3. Creates Python virtualenv at `/opt/sentinel-venv` (first run only)
4. Installs `requirements.txt` (skips if unchanged)
5. Creates `/opt/sentinel/backend/.env` (first run only); patches `REVIEW_MIN_EVIDENCE` if missing
6. Installs + starts `sentinel.service` via systemd
7. Retries `GET /api/health` up to 5 times (3 s apart) before declaring success

### GitHub Actions CI/CD — Two Separate Workflows

There are two workflows, each with a distinct responsibility:

```
infra/**  changed  →  infra.yml   (terraform plan/apply — provision AWS resources)
src/ or backend/ changed  →  deploy.yml  (rsync code to existing EC2)
```

This separation is intentional. Running `terraform apply` on every code push is dangerous — it re-evaluates the full resource graph and can destroy/recreate EC2 or S3 unexpectedly. Terraform only runs when infrastructure files actually change.

---

#### `deploy.yml` — Code Delivery (triggers on every push to `main`)

**Job 1 — `backend-tests`:**
- Sets up Python 3.12 + pip cache
- Installs Tesseract and libmagic
- Runs `python -m pytest tests/ -v --tb=short`

**Job 2 — `frontend-build`:**
- Sets up Node 20 + npm cache
- Runs `npx vitest run`
- Runs `npx vite build` with `VITE_API_BASE_URL` injected from GitHub Secret
- Uploads `dist/` as a build artifact

**Job 3 — `deploy`** (push to `main` only, not PRs):
- Downloads the frontend artifact
- `aws s3 sync` assets — long TTL (`max-age=31536000,immutable`)
- `aws s3 sync` HTML — short TTL (`max-age=0,must-revalidate`) + `--delete`
- `rsync` backend to EC2 (excludes `.env`, `*.db`, `*.jsonl`, `__pycache__`)
- SSH `sudo systemctl restart sentinel` + health check

**Required secrets for `deploy.yml`:**

| Secret | Example |
|--------|---------|
| `AWS_ACCESS_KEY_ID` | IAM key (S3 PutObject + ListBucket) |
| `AWS_SECRET_ACCESS_KEY` | IAM secret |
| `AWS_REGION` | `ap-south-1` |
| `S3_BUCKET` | `sentinel-ui-951066974179` |
| `EC2_HOST` | `65.2.181.197` |
| `EC2_SSH_KEY` | Full contents of the `.pem` file |
| `EC2_USER` | `ubuntu` |
| `VITE_API_BASE_URL` | `http://65.2.181.197:8000` |

---

#### `infra.yml` — Infrastructure Provisioning (triggers on `infra/**` changes only)

**When it runs:**
- **Push to `main`** with changes under `infra/` → plan + apply automatically
- **Pull request** with changes under `infra/` → plan only (no apply; plan posted as PR comment)
- **`workflow_dispatch`** → manual trigger from GitHub Actions UI with action choice: `plan` / `apply` / `destroy`

**Jobs:**
1. `terraform init` — initialises with S3 remote backend (bucket injected via secret)
2. `terraform validate` + `fmt -check`
3. `terraform plan -out=tfplan` — always runs; exit code 2 (changes pending) treated as non-error
4. `terraform apply -auto-approve tfplan` — only on push to `main` or manual `apply`
5. `terraform output` — prints EC2 IP + CloudFront URL to the Actions log after apply
6. `terraform destroy` — only on manual `destroy` dispatch; **never triggered automatically**

**Concurrency lock:** `cancel-in-progress: false` — if two infra runs queue up, the second waits rather than cancelling, preventing state corruption.

**Required secrets for `infra.yml`:**

| Secret | Example |
|--------|---------|
| `AWS_ACCESS_KEY_ID` | IAM key (EC2, S3, CloudFront, IAM) |
| `AWS_SECRET_ACCESS_KEY` | IAM secret |
| `AWS_REGION` | `ap-south-1` |
| `TF_STATE_BUCKET` | `sentinel-tf-state-951066974179` |
| `FRONTEND_BUCKET_NAME` | `sentinel-ui-951066974179` |
| `EC2_KEY_PAIR_NAME` | `sentinel-key` (name only, not `.pem`) |
| `REVIEW_MIN_EVIDENCE` | `1` |
| `OLLAMA_BASE_URL` | *(empty for local Ollama on EC2)* |

**One-time state bucket bootstrap** (run once before the first `terraform init`):

```bash
aws s3api create-bucket \
  --bucket sentinel-tf-state-<your-account-id> \
  --region ap-south-1 \
  --create-bucket-configuration LocationConstraint=ap-south-1

# Enable versioning so you can recover from bad applies
aws s3api put-bucket-versioning \
  --bucket sentinel-tf-state-<your-account-id> \
  --versioning-configuration Status=Enabled
```

Then add `TF_STATE_BUCKET=sentinel-tf-state-<your-account-id>` to GitHub Secrets.

**Local init with S3 backend:**

```bash
cd infra
terraform init \
  -backend-config="bucket=sentinel-tf-state-<your-account-id>" \
  -backend-config="key=sentinel/terraform.tfstate" \
  -backend-config="region=ap-south-1" \
  -backend-config="encrypt=true"
```

### Frontend Build (manual)

```powershell
cd frontend\sentinel-ui
npm run build
# dist/ → deploy to S3

aws s3 sync dist/assets/ s3://your-bucket/assets/ \
  --cache-control "public,max-age=31536000,immutable"
aws s3 sync dist/ s3://your-bucket/ --delete \
  --exclude "assets/*" \
  --cache-control "public,max-age=0,must-revalidate"
```

---

## 13. Extending Sentinel

### Adding a New LLM Provider

1. Edit `backend/agents/llm_factory.py`:
   ```python
   elif provider == "openai":
       from langchain_openai import ChatOpenAI
       return ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-4o"), temperature=temperature)
   ```
2. Add the provider's env vars to `.env.example`.
3. Add tests to `tests/unit/test_llm_factory.py`.

### Adding a New File Format

1. Add an extraction function to `backend/data/file_extractor.py`.
2. Register the new extension in the format dispatch table at the top of `file_extractor.py`.
3. Add `_SINGLE_FILE_ALLOWED_EXT` entry in `routes.py`.
4. Add test documents to `sample_docs/`.
5. Add tests to `tests/unit/test_file_extractor.py`.

### Adding a New Agent Node

See [Section 7 — LangGraph Pipeline](#7-langgraph-pipeline).

### Adding a New API Endpoint

1. Add the route to `backend/api/routes.py`.
2. Add integration tests to `tests/integration/test_routes.py`.
3. Document the endpoint in [Section 6 — API Reference](#6-api-reference).

### Adding a New Frontend Tab

1. Create the component in `frontend/sentinel-ui/src/components/`.
2. Add a new tab key to the `activeTab` union type in `App.tsx`.
3. Add the tab button in the `<nav>` section of `App.tsx`.
4. Add the conditional render in the `<main>` section.
5. Create a test file in `src/__tests__/`.

---

## 14. Security Model

### Authentication & RBAC

JWT-based authentication is implemented via `python-jose` and `passlib[bcrypt]`.

| Role | Permissions |
|------|------------|
| `analyst` | `POST /api/analyze`, `GET /api/history`, `POST /api/feedback/*`, `GET /api/metrics/*`, `GET /api/health` |
| `admin` | All analyst permissions + `POST /api/override/*`, `GET /api/history/export`, `GET /api/feedback/*`, `POST /api/admin/insights/*`, `GET /api/clauses/*`, `POST /api/clauses/*` |

Tokens are obtained via `POST /api/auth/token` and passed as `Authorization: Bearer <token>`.

The optional `SENTINEL_API_KEY` env var adds a simple static key guard as a secondary layer for all `/api/*` routes.

### Input Validation

| Layer | What is validated |
|-------|-----------------|
| File upload | Extension allowlist; MIME magic bytes check; 5 MB hard cap |
| Batch ZIP | ZIP slip path check (no `..`); 50 MB cap; 50 file cap |
| Guardrail | PII patterns + injection patterns block document before LLM |
| Tenant ID | Regex: `^[A-Za-z0-9_-]{1,64}$` |
| LLM response | Capped at 10K–20K chars; parsed fields validated against allowlists |
| Scores | Clamped to [0.0, 1.0]; explicit `math.isnan()` / `math.isinf()` check |
| History limit | Clamped to [1, 1000] |
| Callback URL | Length ≤ 2048; SSRF-blocked private/loopback ranges; `follow_redirects=False` |
| Override lock | `asyncio.Lock` prevents TOCTOU race on check-then-set |

### HTTP Security Headers

Applied by `SecurityHeadersMiddleware` in `main.py`:

| Header | Value |
|--------|-------|
| `X-Frame-Options` | `DENY` |
| `X-Content-Type-Options` | `nosniff` |
| `X-XSS-Protection` | `1; mode=block` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Content-Security-Policy` | `default-src 'none'; frame-ancestors 'none'` |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` (HTTPS only) |

### Rate Limiting

`slowapi` limits:
- `/api/analyze` — **10 requests/minute per IP**
- `/api/analyze/batch` — **2 requests/minute per IP**

Adjust via `RATE_LIMIT` env var.

---

## 15. Limitations and Known Issues

### LLM / AI Limitations

| Limitation | Impact | Mitigation |
|-----------|--------|-----------|
| Non-deterministic outputs | Same document may get slightly different clause results on re-submission | Retry loop re-runs up to 3 times; faithfulness score flags unreliable results |
| Context window | Documents exceeding ~50K tokens may be truncated | `pdf_extractor` hard-caps output at 50K chars |
| Model accuracy | Smaller models (4B params) are faster but miss more clauses | Use `gemma3:27b` for production; `gemma3:4b` for development |
| Hallucination | LLM may confidently report PRESENT for absent clauses | Second evaluator pass quantifies this; Faithfulness Score surfaced in UI |

### System Limitations

| Limitation | Impact | Notes |
|-----------|--------|-------|
| Single SQLite file | Not suitable for high concurrent write loads | Replace with PostgreSQL for multi-instance deployments |
| FAISS in-process | Index rebuilt per request (no cross-restart persistence) | FAISS index persistence is a future enhancement |
| Single-file 5 MB cap | Large PDFs (scanned books, etc.) are rejected | Split before upload; batch ZIP can hold multiple 5 MB files |

### Deployment Limitations

| Limitation | Detail |
|-----------|--------|
| EC2 t3.micro RAM | 1 GB RAM is sufficient for FastAPI + SQLite but cannot run Ollama locally. Ollama Cloud or a larger instance is required for production LLM inference. |
| Ollama Cloud costs | ~$0.05 per demo session. Not covered by AWS Free Tier. |
| Terraform state | Default setup stores `terraform.tfstate` locally. For team deployments, configure an S3 backend in `infra/main.tf`. |
| Cold start | First request after EC2 restart is slower (~5–10 s) while the LLM loads. |

### Known Bugs / Rough Edges

| Issue | Status |
|-------|--------|
| Large TIFF files (> 4 pages) are slow due to per-page OCR | Known; no current fix. Compress or split before upload. |
| `python-multipart < 0.0.18` had CVE-2024-53498 | Fixed — `requirements.txt` pins `>=0.0.18` |
| Non-array response from `/api/history` crashed `HistoryPanel` | Fixed — `Array.isArray` guard added |
| `_clamp_score()` with NaN input returned `1.0` | Fixed — explicit `math.isnan()` / `math.isinf()` check added |
| `useCallback` in `App.tsx` captured stale `tenantId` on first render | No longer applicable — tenant is auto-detected server-side, not passed from the UI |
