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
Browser (React + Vite)
      │
      │ POST /api/analyze               (multipart form — single doc)
      │ POST /api/analyze/batch         (multipart form — ZIP)
      │ GET  /api/jobs/{job_id}         (batch job polling)
      │ GET  /api/history
      │ GET  /api/history/export        (CSV)
      │ POST /api/override/{trace_id}
      │ POST /api/feedback/{trace_id}
      │ GET  /api/metrics/summary
      │ GET  /api/metrics               (Prometheus format)
      │ GET  /api/failures
      │ GET  /api/samples / /api/samples/{filename}
      │ GET  /health
      │
      │ POST /api/feedback/{trace_id}   (👍/👎 + optional comment)
      │ GET  /api/feedback/summary      (feedback rows for Insights table)
      │ GET  /api/feedback/export       (CSV download)
      │
      │ POST /api/admin/insights/run-review          (SSE — review agent)
      │ GET  /api/admin/insights/recommendations     (list with status filter)
      │ POST /api/admin/insights/{rec_id}/approve
      │ POST /api/admin/insights/{rec_id}/reject
      │ POST /api/admin/insights/{rec_id}/undo
      ▼
FastAPI (Python 3.12)
      │
      ├── SecurityHeadersMiddleware  (X-Frame, CSP, HSTS…)
      ├── SlowAPI rate limiter       (10 req/min per IP)
      ├── CORS middleware
      │
      ▼
LangGraph StateGraph
      │
      ├── guardrail node   — PII / injection detection
      ├── router node      — document type classification
      ├── compliance node  — clause checking via FAISS RAG
      ├── evaluator node   — LLM-as-a-Judge faithfulness score
      └── retry loop       — up to 3 attempts if score < 0.7
            │
            ▼
      SQLite (aiosqlite)  — history + dedup cache
      FAISS               — embedding index for clause retrieval
      Ollama / LLM        — ChatOllama (local) or Ollama Cloud (prod)
```

**Key technology choices:**

| Layer | Technology | Why |
|-------|-----------|-----|
| Backend framework | FastAPI | Async-native, SSE support, automatic OpenAPI docs |
| AI orchestration | LangGraph | Stateful graph with feedback loops |
| LLM | Ollama (ChatOllama) | Local-first; env-var switchable to cloud |
| Vector search | FAISS | Fast in-process embedding search, no external service |
| Database | SQLite + aiosqlite | Zero-ops, sufficient for demo/small teams |
| Frontend | React 19 + Vite + TypeScript | Fast HMR, strict types |
| Testing (backend) | pytest + pytest-asyncio | Async-first |
| Testing (frontend) | Vitest + Testing Library | Native Vite integration |
| Logging | structlog | JSON-structured, trace_id threaded through |
| Rate limiting | slowapi | Decorator-based, minimal setup |

---

## 2. Repository Structure

```
.
├── backend/
│   ├── main.py                    # FastAPI app, CORS, middleware, startup
│   ├── agents/
│   │   ├── state.py               # AgentState TypedDict — all pipeline fields
│   │   ├── graph.py               # LangGraph StateGraph definition
│   │   ├── router_agent.py        # Guardrail + Router nodes, VALID_CATEGORIES
│   │   ├── compliance_agent.py    # Compliance node, RAG clause lookup, few-shot injection
│   │   ├── eval_judge.py          # LLM-as-a-Judge evaluator node
│   │   ├── expiry_agent.py        # Expiry date extraction node
│   │   ├── review_agent.py        # AI feedback loop meta-agent (Phase G)
│   │   └── llm_factory.py         # LLM provider abstraction (env-var driven)
│   ├── api/
│   │   ├── routes.py              # All endpoints: analyze, history, feedback, insights, override
│   │   ├── auth.py                # JWT login + bcrypt user store
│   │   └── auth_router.py         # /api/auth/* routes
│   ├── data/
│   │   ├── regulatory_db.json     # Clause requirements — patched by approve action
│   │   ├── few_shot_examples.jsonl  # Approved corrections injected into prompts (runtime)
│   │   ├── correction_examples.jsonl # Negative feedback log — gitignored (runtime)
│   │   ├── guardrails.py          # PII regexes, injection patterns
│   │   ├── embeddings.py          # FAISS index build + search
│   │   ├── history_store.py       # SQLite CRUD for analyses + dedup cache
│   │   ├── pdf_extractor.py       # PDF → text (pdfminer + Tesseract OCR fallback)
│   │   ├── file_extractor.py      # .docx/.xlsx/.pptx/.html/.img → text
│   │   ├── language_detector.py   # langdetect wrapper
│   │   ├── metrics.py             # Prometheus-style counters (in-process)
│   │   └── anonymizer.py          # PII redaction before LLM submission
│   ├── prompts/
│   │   ├── router_prompt.json     # Router LLM prompt template (versioned)
│   │   ├── compliance_prompt.json # Compliance LLM prompt template
│   │   └── evaluator_prompt.json  # Evaluator LLM prompt template
│   ├── tests/
│   │   ├── unit/                  # 18 unit test modules (~240 tests)
│   │   └── integration/           # 2 integration modules (~98 tests)
│   ├── requirements.txt
│   ├── .env.example               # All supported environment variables
│   └── docker-compose.prod.yml    # Production compose (no local Ollama)
├── frontend/sentinel-ui/
│   ├── src/
│   │   ├── App.tsx                # Main component, SSE handling
│   │   ├── components/
│   │   │   ├── DocumentUpload.tsx
│   │   │   ├── WorkflowStream.tsx
│   │   │   ├── StatusBadge.tsx
│   │   │   ├── HistoryPanel.tsx
│   │   │   ├── ConfidenceGauge.tsx
│   │   │   └── ClauseDiffViewer.tsx
│   │   └── __tests__/             # 7 test files, 75 tests
│   ├── vite.config.ts
│   ├── tsconfig.json
│   └── package.json
├── infra/
│   ├── main.tf                    # Terraform: EC2, S3, CloudFront
│   ├── variables.tf
│   ├── outputs.tf
│   └── user_data.sh               # EC2 bootstrap script
├── sample_docs/                   # 55+ test documents (all types + formats)
├── docs/
│   ├── USER_GUIDE.md              # End-user documentation (this repo)
│   └── DEVELOPER_GUIDE.md         # This file
└── .github/workflows/deploy.yml   # CI/CD: Terraform + S3 frontend sync
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
python -m venv .venv
.venv\Scripts\Activate.ps1

# Install dependencies
cd backend
pip install -r requirements.txt

# Copy environment variables
cp .env.example .env
# Edit .env to set OLLAMA_MODEL etc.

# Run development server
uvicorn main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

### Frontend

```powershell
cd frontend\sentinel-ui
npm install
npm run dev
```

The dev server starts at `http://localhost:5173` with Vite HMR. API requests to `/api/*` are proxied to `http://localhost:8000` via `vite.config.ts`.

### Ollama (LLM)

```bash
# Install Ollama, then pull the model
ollama pull gemma3:27b

# Start Ollama server (runs on port 11434 by default)
ollama serve
```

If you don't have a GPU, use a smaller model: `ollama pull gemma3:4b`. Set `OLLAMA_MODEL=gemma3:4b` in `.env`.

---

## 4. Backend Reference

### `AgentState` (`backend/agents/state.py`)

All pipeline data flows through a single typed dictionary:

```python
class AgentState(TypedDict):
    # Input
    raw_text: str                              # Extracted document text
    tenant_id: str                             # "default" | "EU" | "US"
    trace_id: str                              # UUID for tracking

    # Guardrail
    sanitized: bool                            # True if guardrail passed

    # Router
    doc_type: str                              # Detected document category
    routing_confidence: float                  # 0.0–1.0 classification confidence
    language: str                              # ISO 639-1 language code ("en", "fr", …)

    # Compliance
    required_clauses: list                     # Clause list from regulatory_db.json
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
    logs: Annotated[list, operator.add]        # Accumulating log entries
```

### `llm_factory.py`

All agent nodes obtain an LLM instance via:

```python
from agents.llm_factory import create_llm

llm = create_llm(temperature=0.0)
```

The factory reads environment variables — see [Section 8](#8-configuration--environment-variables). This means you can switch from local Ollama to Ollama Cloud without changing any agent code.

### Guard rails (`backend/data/guardrails.py`)

Documents are screened before reaching the LLM:

- **Injection patterns** — 9 regex patterns blocking prompt injection and jailbreak attempts
- **PII patterns** — SSN, credit card, passport, IBAN, SWIFT detection
- **Public alias** — `INJECTION_PATTERNS` (list of strings) for test inspection

Blocked documents receive `final_decision = "BLOCKED"` and are not forwarded to the router.

---

## 5. Frontend Reference

### Component Map

| Component | File | Responsibility |
|-----------|------|---------------|
| `App` | `App.tsx` | State management, SSE stream handling, 5-tab routing |
| `DocumentUpload` | `DocumentUpload.tsx` | Drag-and-drop file input, keyboard accessible |
| `WorkflowStream` | `WorkflowStream.tsx` | Live log display with colour-coded node labels |
| `StatusBadge` | `StatusBadge.tsx` | Decision badge (colour per decision type) |
| `ConfidenceGauge` | `ConfidenceGauge.tsx` | SVG arc gauge for routing confidence |
| `ClauseDiffViewer` | `ClauseDiffViewer.tsx` | Side-by-side clause diff across retry attempts |
| `HistoryPanel` | `HistoryPanel.tsx` | Paginated history table with error/empty states |
| `FeedbackWidget` | `FeedbackWidget.tsx` | Two-step 👍/👎 — positive submits instantly; negative reveals comment textarea |
| `InsightsDashboard` | `InsightsDashboard.tsx` | AI feedback loop control centre: stats, feedback table, run-review SSE, recommendations with approve/reject/undo |
| `BatchUpload` | `BatchUpload.tsx` | ZIP batch upload, progress bar, per-file results table |
| `MetricsPanel` | `MetricsPanel.tsx` | Observability dashboard: decisions, faithfulness, risk, 7-day trend |
| `HelpPanel` | `HelpPanel.tsx` | User documentation, sample document catalogue |

### SSE Stream Format

The backend sends `text/event-stream` with two event types:

```
data: {"type": "log", "node": "router", "message": "Classified as CREDIT_AGREEMENT"}

data: {"type": "done", "final_decision": "APPROVED", "doc_type": "CREDIT_AGREEMENT",
       "evaluation_score": 0.91, "hallucination_risk": "low",
       "routing_confidence": 0.87, "trace_id": "abc-123",
       "clause_results": [...], "clause_results_history": [[...], [...]]}
```

The frontend's `handleFile` function in `App.tsx` parses these events and updates React state accordingly. A 5-minute `AbortController` timeout cancels stalled streams.

### Environment Variables (frontend)

| Variable | Default | Purpose |
|----------|---------|---------|
| `VITE_API_BASE_URL` | `""` (empty) | API base URL; empty = same origin (production proxy) |

Set `VITE_API_BASE_URL=http://localhost:8000` in `.env.local` only if the API runs on a different port than the dev server.

---

## 6. API Reference

Base URL: `http://localhost:8000` (dev) / CloudFront URL (prod)

### `POST /api/analyze`

Submit a document for analysis. Returns an SSE stream.

**Request:** `multipart/form-data`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | file | Yes | Document file (see supported formats) |
| `tenant_id` | string | No | `"default"` \| `"EU"` \| `"US"` (default: `"default"`) |
| `callback_url` | string | No | Webhook URL to POST result to on completion |

**Response:** `text/event-stream`

Each line is a JSON object (see SSE format above). The stream ends after a `type: "done"` event.

**Rate limit:** 10 requests per minute per IP.

---

### `GET /api/history`

Retrieve past analyses.

**Query parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 50 | Number of records (1–1000) |

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
    "created_at": "2026-05-21T10:00:00Z"
  }
]
```

---

### `POST /api/override/{trace_id}`

Apply a compliance officer override to a past analysis.

**Path parameter:** `trace_id` — UUID from the analysis result.

**Request body:** `application/json`

```json
{ "decision": "APPROVED" }
```

**Response:** `200 OK` on success.

---

### `POST /api/feedback/{trace_id}`

Submit a thumbs-up or thumbs-down rating for a completed analysis.

**Path parameter:** `trace_id` — UUID from the analysis result.

**Request body:** `application/json`

```json
{ "rating": "positive", "comment": "Clause extraction was accurate." }
```

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `rating` | `"positive"` \| `"negative"` | Yes | Enum; anything else → 422 |
| `comment` | string | No | Truncated to 500 chars |

**Response:** `201 Created` — `{"status": "recorded"}`

**Rate limit:** 10/minute per IP. UUID-format validation on `trace_id` (non-UUID → 422).

---

### `GET /api/metrics/summary`

Aggregate observability metrics across all analyses.

**Response:**

```json
{
  "total": 142,
  "by_decision": { "APPROVED": 98, "REJECTED": 30, "ESCALATE": 10, "BLOCKED": 4 },
  "avg_faithfulness": 0.847,
  "risk_distribution": { "low": 85, "medium": 42, "high": 15 },
  "daily_last_7_days": { "2026-05-15": 12, "2026-05-16": 18, "2026-05-17": 25 }
}
```

---

### `POST /api/analyze/batch`

Submit a ZIP file for concurrent multi-document analysis. Returns immediately with a job ID.

**Request:** `multipart/form-data`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | file | Yes | ZIP file (max 50 MB, max 50 files) |
| `tenant_id` | string | No | Regulatory profile (default: `"default"`) |
| `force_refresh` | bool | No | If `true`, bypass cache for all files (default: `false`) |

**Response:** `202 Accepted`

```json
{ "job_id": "550e8400-e29b-41d4-a716-446655440000", "total": 12 }
```

**Error codes:**

| Code | Reason |
|------|--------|
| 400 | Not a ZIP file or corrupted archive |
| 413 | ZIP exceeds 50 MB |
| 422 | > 50 files, disallowed extension, or ZIP slip path detected |

**Security:** ZIP slip protection rejects any entry with `..` in path or starting with `/`.

**Rate limit:** 2/minute per IP.

**Cache behaviour:** For each file in the ZIP, `_process_batch` computes a SHA-256 fingerprint and queries `doc_cache`. On a cache hit, the stored result is returned immediately with `from_cache: true` — the LangGraph pipeline is skipped. On a miss, the pipeline runs and the result is written to `doc_cache`. Setting `force_refresh: true` calls `delete_doc_cache` before the lookup, ensuring the pipeline always runs.

---

### `GET /api/jobs/{job_id}`

Poll the status of a batch job.

**Path parameter:** `job_id` — UUID returned by `POST /api/analyze/batch`.

**Response:**

```json
{
  "job_id": "550e8400-...",
  "status": "running",
  "total": 12,
  "completed": 7,
  "results": [
    { "filename": "contract.pdf", "trace_id": "...", "final_decision": "APPROVED", "evaluation_score": 0.91, "from_cache": false }
  ],
  "created_at": "2026-05-21T14:00:00Z"
}
```

`status` is one of: `"pending"` → `"running"` → `"completed"` | `"failed"`. Poll until `completed` or `failed`. Non-UUID `job_id` → 422. Unknown job → 404.

---

### `GET /health`

Health check endpoint for load balancers and monitoring.

**Response:**

```json
{
  "status": "ok",
  "checks": {
    "sqlite": true,
    "llm": true,
    "faiss": true
  }
}
```

`status` is `"degraded"` if any check fails.

---

### `GET /api/feedback/summary`

Returns all feedback entries joined with their analysis record, for display in the Insights tab.

**Response:** `application/json` — array of objects:

```json
[
  {
    "trace_id": "abc-123",
    "rating": "negative",
    "comment": "Missing indemnity clause was clearly present.",
    "created_at": "2026-05-21T10:00:00Z",
    "filename": "contract.pdf",
    "decision": "REJECTED",
    "doc_type": "NDA"
  }
]
```

---

### `GET /api/feedback/export`

Downloads all feedback as a CSV file.

**Response:** `text/csv` — columns: `trace_id`, `filename`, `doc_type`, `decision`, `rating`, `comment`, `created_at`.

---

### `POST /api/admin/insights/run-review`

Runs the AI review agent on accumulated feedback. Returns an SSE stream identical in format to `/api/analyze`.

**Query parameter:** `min_evidence` (integer, default: `1`) — minimum feedback entries per doc type.

**Response:** `text/event-stream` — log lines + a final `{"type": "done"}` event.

---

### `GET /api/admin/insights/recommendations`

List recommendations, optionally filtered by status.

**Query parameter:** `status` — `pending` | `approved` | `rejected` | `undone` | `all` (default: `pending`)

**Response:** `application/json` — array of recommendation objects:

```json
[
  {
    "rec_id": "550e8400-...",
    "doc_type": "NDA",
    "rec_type": "missing_rule",
    "proposed": "indemnity clause",
    "evidence_count": 3,
    "confidence": "high",
    "rationale": "3 analysts flagged missing indemnity language.",
    "status": "pending",
    "created_at": "2026-05-21T10:00:00Z",
    "resolved_at": null
  }
]
```

---

### `POST /api/admin/insights/{rec_id}/approve`

Approve a pending recommendation and apply the change.

- `missing_rule` → appends clause to `regulatory_db.json` + calls `reload_reg_db()`
- `comprehension_failure` → appends entry to `few_shot_examples.jsonl`

**Response:** `200 OK` — `{"status": "approved", "rec_id": "...", "action": "approved"}`

**Errors:** `404` unknown rec_id · `400` already approved/rejected

---

### `POST /api/admin/insights/{rec_id}/reject`

Reject a pending recommendation and blacklist it.

**Response:** `200 OK` — `{"status": "rejected", "rec_id": "..."}`

**Errors:** `404` unknown rec_id · `400` already rejected

---

### `POST /api/admin/insights/{rec_id}/undo`

Reverse an approved or rejected recommendation.

- Approved `missing_rule` → removes clause from `regulatory_db.json` + `reload_reg_db()`
- Approved `comprehension_failure` → removes entry from `few_shot_examples.jsonl`
- Rejected → status reset to `pending`; blacklist entry removed

**Response:** `200 OK` — `{"status": "undone", "action": "undone"}` (or `"reopened"` for rejected→pending)

**Errors:** `404` unknown rec_id · `400` status is `pending` or `undone`

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
router
  │
  ▼
compliance
  │
  ▼
evaluator ──(score ≥ 0.7 or retry_count ≥ 3)──► END
  │
  │ (score < 0.7 and retry_count < 3)
  ▼
increment_retry ──► compliance   (feedback loop)
```

### Node Responsibilities

| Node | Agent file | What it does |
|------|-----------|--------------|
| `guardrail` | `router_agent.py` | Checks PII + injection patterns; sets `sanitized` |
| `router` | `router_agent.py` | Calls LLM to classify document type + confidence; sets `doc_type`, `routing_confidence`, `language` |
| `compliance` | `compliance_agent.py` | Loads required clauses, does FAISS RAG search, calls LLM for clause detection |
| `evaluator` | `eval_judge.py` | Second LLM call rates faithfulness + hallucination risk; sets `final_decision` |
| `increment_retry` | `graph.py` | Increments `retry_count`; appends current `clause_results` to `clause_results_history` |

### Adding a New Node

1. Create the node function in the appropriate agent file:
   ```python
   def my_node(state: AgentState) -> dict:
       # read from state, return partial update dict
       return {"my_field": computed_value}
   ```
2. Register it in `graph.py`:
   ```python
   builder.add_node("my_node", my_node)
   builder.add_edge("evaluator", "my_node")
   ```
3. Add any new fields to `AgentState` in `state.py`.
4. Write tests in `tests/unit/test_my_node.py`.

---

## 8. Configuration & Environment Variables

Copy `backend/.env.example` to `backend/.env` and set values:

```env
# LLM Provider
LLM_PROVIDER=ollama                     # Currently only "ollama" is supported
OLLAMA_MODEL=gemma3:27b                 # Any Ollama-compatible model name
OLLAMA_BASE_URL=                        # Empty = local (port 11434); set to cloud URL in prod

# Database
SQLITE_PATH=./sentinel.db              # Path to SQLite database file

# Rate limiting
RATE_LIMIT=10/minute                   # Format: "{count}/{period}"

# Security
ALLOWED_ORIGINS=http://localhost:5173  # Comma-separated CORS origins
HSTS_MAX_AGE=31536000                  # HSTS max-age in seconds (production only)

# Logging
LOG_LEVEL=INFO                         # DEBUG | INFO | WARNING | ERROR

# File upload
MAX_UPLOAD_BYTES=52428800              # 50 MB default

# AI Feedback Loop
REVIEW_MIN_EVIDENCE=1                  # Min 👎 per doc type before review agent acts
                                       # Set to 1 for demos; raise to 3–5 in production
```

For production (Ollama Cloud):

```env
OLLAMA_BASE_URL=https://your-ollama-cloud-endpoint.example.com
OLLAMA_MODEL=gemma3:27b
ALLOWED_ORIGINS=https://your-cloudfront-url.cloudfront.net
```

---

## 9. Database Schema

SQLite database at `SQLITE_PATH` (default `./sentinel.db`). Managed by `backend/data/history_store.py`.

### `analyses` table

```sql
CREATE TABLE analyses (
    trace_id    TEXT PRIMARY KEY,
    filename    TEXT NOT NULL,
    doc_type    TEXT NOT NULL,
    decision    TEXT NOT NULL,
    faithfulness REAL NOT NULL,
    risk        TEXT NOT NULL,
    created_at  TEXT NOT NULL        -- ISO 8601 UTC
);
```

### `overrides` table

```sql
CREATE TABLE overrides (
    trace_id    TEXT PRIMARY KEY,
    decision    TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
```

### `doc_cache` table (deduplication)

```sql
CREATE TABLE doc_cache (
    doc_hash    TEXT PRIMARY KEY,    -- SHA-256 of raw file bytes
    payload     TEXT NOT NULL,       -- Sanitised DonePayload as JSON
    cached_at   TEXT NOT NULL
);
```

A duplicate submission (same file bytes) hits the cache and returns the stored result instantly, skipping the entire LLM pipeline.

### `feedback` table

```sql
CREATE TABLE feedback (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    trace_id    TEXT NOT NULL,
    rating      TEXT NOT NULL CHECK(rating IN ('positive', 'negative')),
    comment     TEXT,
    created_at  TEXT NOT NULL
);
```

Stores user ratings submitted via `POST /api/feedback/{trace_id}`. Multiple ratings per trace_id are allowed; `get_feedback()` returns the most recent.

### `recommendations` table

```sql
CREATE TABLE recommendations (
    rec_id        TEXT PRIMARY KEY,          -- UUID
    doc_type      TEXT NOT NULL,
    rec_type      TEXT NOT NULL,             -- 'missing_rule' | 'comprehension_failure'
    proposed      TEXT NOT NULL,             -- clause name (str) or JSON object
    evidence_count INTEGER NOT NULL,
    confidence    TEXT NOT NULL,             -- 'high' | 'medium' | 'low'
    rationale     TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'pending',  -- 'pending'|'approved'|'rejected'|'undone'
    created_at    TEXT NOT NULL,
    resolved_at   TEXT                       -- NULL until approved/rejected/undone
);
```

Created by the review agent; managed by `create_recommendation`, `get_recommendation`, `set_recommendation_status`.

**Approve logic** (`POST /api/admin/insights/{rec_id}/approve`):
- `missing_rule` → clause appended to `regulatory_db.json`; `reload_reg_db()` called (no restart)
- `comprehension_failure` → entry appended to `few_shot_examples.jsonl`; injected into the next compliance prompt automatically

**Undo logic** (`POST /api/admin/insights/{rec_id}/undo`):
- Approved `missing_rule` → `_remove_clause_from_reg_db()` removes the clause; `reload_reg_db()` called
- Approved `comprehension_failure` → `_remove_few_shot_example(rec_id)` rewrites the JSONL without that entry
- Rejected recommendation → status reset to `pending`; blacklist entry removed

### `recommendation_blacklist` table

```sql
CREATE TABLE recommendation_blacklist (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_type  TEXT NOT NULL,
    proposed  TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(doc_type, proposed)
);
```

Populated on reject. The review agent checks `is_blacklisted(doc_type, proposed)` before creating a new recommendation — blacklisted (doc_type, proposed) pairs are never re-suggested.

### `batch_jobs` table

```sql
CREATE TABLE batch_jobs (
    job_id      TEXT PRIMARY KEY,
    status      TEXT NOT NULL DEFAULT 'pending',
    total       INTEGER NOT NULL,
    completed   INTEGER NOT NULL DEFAULT 0,
    results     TEXT NOT NULL DEFAULT '[]',  -- JSON array of per-file results
    created_at  TEXT NOT NULL
);
```

Tracks in-flight and completed batch processing jobs. `results` is a JSON array updated incrementally as each document in the ZIP is processed.

---

## 10. Regulatory Database

`backend/data/regulatory_db.json` — edited directly to add tenants, document types, or clauses.

Structure:

```json
{
  "default": {
    "CREDIT_AGREEMENT": {
      "required_clauses": [
        "interest rate provisions",
        "repayment schedule",
        "default and acceleration",
        "representations and warranties"
      ]
    },
    "LEGAL_CONTRACT": { ... },
    ...
  },
  "EU": {
    "CREDIT_AGREEMENT": {
      "required_clauses": [
        "interest rate provisions",
        "repayment schedule",
        "default and acceleration",
        "representations and warranties",
        "GDPR data processing agreement"    ← EU-specific addition
      ]
    },
    ...
  },
  "US": { ... }
}
```

### Adding a New Document Type

1. Add the type key to each tenant in `regulatory_db.json`.
2. Add the type string to `VALID_CATEGORIES` in `backend/agents/router_agent.py`.
3. Update the router prompt template (`backend/prompts/router_prompt.json`) to include the new type.
4. Write test documents and add them to `sample_docs/`.
5. Add test cases to `tests/unit/test_regulatory_db.py`.

### Adding a New Tenant / Regulatory Profile

1. Add a new top-level key to `regulatory_db.json` mirroring the structure of `"default"`.
2. The backend picks up the new tenant automatically — no code changes needed.
3. Update the frontend `Regulatory Profile` dropdown in `frontend/sentinel-ui/src/App.tsx`.

---

## 11. Testing

### Running Tests

```powershell
# Backend — all tests
cd backend
C:\sanjeev\job-search\.python312\python.exe -m pytest tests/ -v

# Backend — unit tests only
pytest tests/unit/ -v

# Backend — integration tests only
pytest tests/integration/ -v

# Frontend
cd frontend\sentinel-ui
node_modules\.bin\vitest run

# Frontend — watch mode
node_modules\.bin\vitest
```

### Test Counts (Phase G)

| Suite | Tests | Coverage |
|-------|-------|---------|
| Backend unit | ~470 | agents, data layer, auth, guardrails, metrics, feedback loop, review agent, insights endpoints |
| Backend integration | ~114 | full pipeline, all API routes |
| Frontend | 173 | all 11 components + App + InsightsDashboard (SSE, approve/reject/undo) |
| **Total** | **~757** | |

### Test Structure

```
backend/tests/
├── unit/
│   ├── test_anonymizer.py          # PII redaction
│   ├── test_batch.py               # Batch upload endpoints + ZIP security
│   ├── test_dedup.py               # Deduplication cache
│   ├── test_eval_parse.py          # Evaluator output parsing
│   ├── test_expiry.py              # Date extraction + validation
│   ├── test_feedback.py            # Feedback store + /api/feedback + insights endpoints
│   │                               #   incl. approve/reject/undo + blacklist + few-shot JSONL
│   ├── test_file_extractor.py      # docx/xlsx/pptx/html/image extraction
│   ├── test_graph_routing.py       # LangGraph routing logic
│   ├── test_guardrails.py          # PII + injection patterns
│   ├── test_history_store.py       # SQLite CRUD + cache sanitisation
│   ├── test_language_detection.py  # langdetect wrapper
│   ├── test_llm_factory.py         # LLM provider abstraction
│   ├── test_llm_utils.py           # LLM response capping
│   ├── test_metrics.py             # Prometheus label escaping
│   ├── test_metrics_summary.py     # GET /api/metrics/summary endpoint
│   ├── test_pdf_extractor.py       # PDF → text + OCR
│   ├── test_regulatory_db.py       # Regulatory DB schema validation
│   ├── test_review_agent.py        # Review meta-agent (mocked LLM, mocked DB)
│   └── test_structured_logging.py  # structlog JSON output
└── integration/
    ├── test_graph_flow.py          # End-to-end pipeline runs (mocked LLM)
    ├── test_routes.py              # FastAPI endpoint tests
    └── test_rbac.py               # JWT auth + role-based access control
```

### Writing New Tests

- **Unit tests** — mock the LLM using `monkeypatch` or `unittest.mock.patch`. Never hit a real Ollama server in unit tests.
- **Integration tests** — use `httpx.AsyncClient` with the FastAPI `app` as transport. Still mock the LLM.
- **Frontend tests** — use `vi.stubGlobal('fetch', vi.fn())` to mock API calls. Never make real HTTP requests from tests.

---

## 12. Deployment

### Docker (local / staging)

```powershell
cd backend
docker compose up --build
```

Builds the FastAPI image and starts it on port 8000. Ollama must be running separately.

### AWS Free Tier (Terraform)

Infrastructure is defined in `infra/`. Provisions EC2 t2.micro + S3 + CloudFront.

```bash
# One-time setup
cd infra
terraform init

# Preview changes
terraform plan -var="ollama_base_url=https://your-cloud-ollama-url"

# Apply (creates all AWS resources, ~3 minutes)
terraform apply -auto-approve \
  -var="ollama_base_url=https://your-cloud-ollama-url" \
  -var="ollama_model=gemma3:27b"

# Get URLs
terraform output cloudfront_url   # Frontend URL
terraform output ec2_public_ip    # Backend IP

# Tear down (avoid charges)
terraform destroy -auto-approve
```

### Manual EC2 Deployment

```bash
# SCP backend files
scp -i sentinel-key.pem -r backend/ ubuntu@<EC2_IP>:/tmp/backend/

# SSH and copy to app directory
ssh -i sentinel-key.pem ubuntu@<EC2_IP>
sudo cp -r /tmp/backend/* /opt/sentinel/backend/
sudo systemctl restart sentinel

# Check health (from local machine, wait 10 seconds first)
curl http://<EC2_IP>:8000/health
```

### Frontend Build

```powershell
cd frontend\sentinel-ui
npm run build
# Output in dist/ — deploy to S3 or any static host
```

For S3 deployment:

```bash
aws s3 sync dist/ s3://your-sentinel-bucket/ --delete
aws cloudfront create-invalidation --distribution-id YOUR_ID --paths "/*"
```

### GitHub Actions CI/CD

The workflow at `.github/workflows/deploy.yml` triggers on push to `main`:

1. Runs backend `pytest` and frontend `vitest`
2. Builds the frontend
3. Syncs `dist/` to S3
4. Runs `terraform apply` to update backend infrastructure
5. Invalidates CloudFront cache

---

## 13. Extending Sentinel

### Adding a New LLM Provider

1. Edit `backend/agents/llm_factory.py`:
   ```python
   elif provider == "openai":
       from langchain_openai import ChatOpenAI
       return ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-4o"), temperature=temperature)
   ```
2. Add the new provider's env vars to `.env.example`.
3. Add tests to `tests/unit/test_llm_factory.py`.

### Adding a New File Format

1. Add an extraction function to `backend/data/file_extractor.py`.
2. Register the new extension in the format dispatch table.
3. Add test documents to `sample_docs/`.
4. Add tests to `tests/unit/test_file_extractor.py`.

### Adding a New Agent Node

See [Section 7 — LangGraph Pipeline](#7-langgraph-pipeline).

### Adding a New API Endpoint

1. Add the route to `backend/api/routes.py`.
2. Add integration tests to `tests/integration/test_routes.py`.
3. Document the endpoint in [Section 6 — API Reference](#6-api-reference).

### Adding a New Frontend Component

1. Create `frontend/sentinel-ui/src/components/MyComponent.tsx`.
2. Import and render it in `App.tsx`.
3. Create `frontend/sentinel-ui/src/__tests__/MyComponent.test.tsx` with at least:
   - Renders without crashing
   - Empty / null props are handled gracefully
   - All user-visible text is rendered correctly

---

## 14. Security Model

### Input Validation

| Layer | What is validated |
|-------|-----------------|
| File upload | Filename sanitised (`Path().name`, backslash normalisation); MIME type checked against allowlist |
| Guardrail | PII patterns + injection patterns block document before LLM |
| LLM response | Capped at 10K–20K chars; parsed fields validated against allowlists |
| Scores | Clamped to [0.0, 1.0]; NaN/Inf rejected |
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

`slowapi` limits `/api/analyze` to **10 requests per minute per IP**. Adjust via `RATE_LIMIT` env var.

### Prometheus Label Safety

All metric label values pass through `_escape_label_value()` in `metrics.py` to prevent label injection.

---

## 15. Limitations and Known Issues

### LLM / AI Limitations

| Limitation | Impact | Mitigation |
|-----------|--------|-----------|
| Non-deterministic outputs | Same document may get slightly different clause results on re-submission | Retry loop re-runs up to 3 times; faithfulness score flags unreliable results |
| Context window | Very long documents (>50K tokens) may be truncated before reaching the LLM | pdf_extractor returns max 50K chars of text |
| Model size vs. accuracy | Smaller Ollama models (4B params) are faster but less accurate | Use gemma3:27b for production; 4B for development only |
| Hallucination in clause detection | LLM may confidently report PRESENT for missing clauses | Second evaluator pass quantifies this; Faithfulness Score surfaced to users |

### System Limitations

| Limitation | Impact | Workaround / Future Work |
|-----------|--------|--------------------------|
| Single SQLite file | Not suitable for concurrent high write loads | Replace with PostgreSQL for multi-instance deployments |
| FAISS in-process index | Index rebuilt per request (no persistence across restarts) | Phase 8E: FAISS index persistence (SHA-256-keyed to disk) — not yet implemented |
| No authentication | All users can read all history and apply overrides | JWT + RBAC is a planned enhancement; API key guard available via `SENTINEL_API_KEY` env var |
| No PDF export of results | Cannot download a compliance report | `reportlab` PDF export is a planned enhancement |
| Batch job history | Completed batch jobs are not shown in Analysis History tab | Each file within a batch is individually stored in the `analyses` table |

### Deployment Limitations

| Limitation | Detail |
|-----------|--------|
| EC2 t2.micro RAM | 1 GB RAM is sufficient for FastAPI + SQLite but gives no headroom for running Ollama locally. Ollama Cloud (or a larger instance) is required for production. |
| Ollama Cloud costs | Approximately $0.05 per demo session. Not free-tier. |
| Terraform state | Default setup stores Terraform state locally. For team deployments, configure an S3 backend for `terraform.tfstate`. |
| Cold start | After an EC2 restart or new deployment, the first request is slower (~5–10 s) while the LLM loads into Ollama's memory. |

### Known Bugs / Rough Edges

| Issue | Status |
|-------|--------|
| Large TIFF files (>4 pages) are slow due to per-page OCR | Known; no current fix. Compress or split before upload. |
| `useCallback` in `App.tsx` previously captured stale `tenantId` on first render | Fixed in Phase 8 final audit — `tenantId` now in dependency array. |
| `python-multipart < 0.0.18` has CVE-2024-53498 | Fixed — `requirements.txt` pins `>=0.0.18`. |
| Non-array JSON from `/api/history` caused HistoryPanel to crash | Fixed — Array.isArray guard added. |
| `_clamp_score()` with NaN input returned 1.0 (Python min/max NaN behaviour) | Fixed — explicit `math.isnan()` / `math.isinf()` check added. |
