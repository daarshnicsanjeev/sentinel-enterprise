# Project Sentinel — Enterprise Agentic Document Routing & Compliance Engine

An end-to-end AI system for automated document classification, compliance checking, and self-improving policy management — built on LangGraph, FastAPI, and React.

[![Backend Tests](https://img.shields.io/badge/backend-584%20tests%20passing-4ade80)](#testing)
[![Frontend Tests](https://img.shields.io/badge/frontend-173%20tests%20passing-4ade80)](#testing)
[![AWS Free Tier](https://img.shields.io/badge/AWS-Free%20Tier%20Deployed-orange)](#aws-deployment)

---

## What It Does

Upload any legal or compliance document (PDF, DOCX, scanned image, HTML, spreadsheet…).  
Sentinel's multi-agent pipeline classifies it, checks compliance, scores it, and streams a live audit log:

1. **Guards** against PII leaks and prompt injection
2. **Classifies** the document type via LLM (credit agreement, NDA, regulatory filing, employment contract, insurance policy, partnership agreement)
3. **Checks compliance** against a per-tenant clause database using FAISS RAG retrieval
4. **Scores** faithfulness and hallucination risk with a second LLM-as-a-Judge pass
5. **Decides** APPROVED / REJECTED / ESCALATE / BLOCKED — streamed live
6. **Learns** from analyst 👎 feedback via an AI-driven review loop that proposes, applies, and undoes rule improvements

---

## Architecture

```
Browser (React 19 + Vite + TypeScript)
  │
  ├── POST /api/analyze          → SSE stream (live agent log)
  ├── POST /api/analyze/batch    → ZIP multi-doc, async job
  ├── POST /api/feedback/{id}    → 👍 / 👎 rating + optional comment
  ├── GET  /api/admin/insights/* → AI review agent (on-demand)
  ├── GET  /api/history          → paginated history + feedback column
  ├── GET  /api/metrics/summary  → observability dashboard
  └── GET  /api/health           → dependency health check
  │
  ▼
FastAPI (Python 3.12) — async, SSE, SlowAPI rate limiting, structlog JSON logging
  │
  ▼
LangGraph StateGraph
  ├── guardrail node    — PII + injection regex patterns
  ├── router node       — LLM document classification + confidence score
  ├── compliance node   — FAISS clause RAG + LLM detection
  │                       ↳ injects approved few-shot corrections automatically
  ├── evaluator node    — LLM-as-a-Judge: faithfulness + hallucination risk
  └── retry loop        — up to 3 re-runs when faithfulness < 0.7
  │
  ├── SQLite (aiosqlite, WAL mode) — history, feedback, dedup cache, recommendations, blacklist
  ├── FAISS                        — in-process embedding index for clause retrieval
  └── LLM factory (create_llm)     — local Ollama or Ollama Cloud via OLLAMA_BASE_URL

AI Feedback Loop (on-demand, no scheduling):
  👎 feedback → correction_examples.jsonl (background task)
  ⚡ "Run Review Agent" button → LLM meta-analysis of patterns
  → Recommendation (missing_rule | comprehension_failure)
  → ✓ Approve: patches regulatory_db.json or few_shot_examples.jsonl (live, no restart)
  → ✗ Reject:  blacklisted — never re-suggested for that doc type
  → ↩ Undo:    physical disk reversal + recommendation re-opened
```

---

## Features

| Category | Feature |
|----------|---------|
| **Ingestion** | PDF (pdfminer + Tesseract OCR fallback), DOCX, XLSX, PPTX, HTML, TXT, PNG/JPG/TIFF |
| **Multi-tenant** | Default / EU (GDPR + Solvency II) / US (Dodd-Frank + SOX) regulatory profiles |
| **Deduplication** | SHA-256 cache — identical uploads return instantly, pipeline skipped |
| **Batch** | ZIP upload → `asyncio.gather` — all documents run concurrently |
| **Streaming** | Every agent step streamed via SSE; 5-min AbortController timeout |
| **Retry loop** | Auto compliance re-check if faithfulness < 0.7, max 3 attempts |
| **Clause diff** | Side-by-side diff of clause results across retry attempts |
| **Confidence gauge** | SVG arc showing routing classification confidence (0–100%) |
| **Language detection** | `langdetect` — warns when non-English document submitted |
| **Override** | Compliance officer can flip REJECTED → APPROVED with audit record |
| **Feedback widget** | Two-step: 👍 submits instantly; 👎 reveals textarea for comment before submit |
| **AI review loop** | Meta-agent reads corrections, classifies patterns, proposes rule changes |
| **Approve/Reject/Undo** | Rules applied live to `regulatory_db.json`; fully reversible |
| **PDF report** | Per-analysis downloadable report from history, with inline feedback |
| **CSV export** | Full feedback history as downloadable CSV |
| **JWT auth + RBAC** | `analyst` (read + analyse) / `admin` (+ override + export + insights) |
| **Structured logging** | `structlog` JSON with `trace_id` in every log line |
| **Prometheus metrics** | `/api/metrics` endpoint + 7-day trend in Metrics tab |
| **Terraform IaC** | One-command AWS provisioning: EC2 + S3 + CloudFront |
| **GitHub Actions CI/CD** | Push to `main` → tests → build → deploy |

---

## Quick Start (Local)

### Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Python | 3.12+ | |
| Node.js | 20+ | |
| Ollama | latest | `ollama pull gemma3:4b` |
| Tesseract | 5.x | For image/scanned-PDF OCR |

### Backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1          # Windows
# source .venv/bin/activate         # Linux / macOS
pip install -r requirements.txt
cp .env.example .env                # edit OLLAMA_MODEL if needed
uvicorn main:app --reload --port 8000
```

### Frontend

```powershell
cd frontend\sentinel-ui
npm install
npm run dev                         # http://localhost:5173
```

### LLM

```bash
ollama pull gemma3:4b               # ~3 GB, CPU-friendly
ollama serve                        # port 11434
```

Set `OLLAMA_MODEL=gemma3:4b` in `backend/.env`.

> For best accuracy use `gemma3:27b` (requires ~32 GB RAM).

---

## AWS Deployment

Infrastructure is defined in `infra/` (Terraform). Everything stays within the AWS Free Tier:

| Resource | Purpose | Free Tier Limit |
|----------|---------|----------------|
| EC2 t3.micro | FastAPI + uvicorn | 750 hrs/month (first 12 months) |
| EBS 25 GB gp3 | App + model storage | 30 GB total |
| S3 bucket | React frontend (static site) | 5 GB + 20K GET/month |
| CloudFront | HTTPS CDN for frontend | 1 TB transfer/month |

### Provision Infrastructure

```bash
cd infra
terraform init
terraform plan                      # preview
terraform apply                     # ~3 minutes
```

### Deploy Backend

```bash
# One-shot: provision + deploy app code
bash infra/deploy-backend.sh
```

The script:
1. Clones the repo (or `git pull` if already present)
2. Creates a Python virtualenv at `/opt/sentinel-venv`
3. Installs `requirements.txt`
4. Writes `/opt/sentinel/backend/.env` (first run only)
5. Installs and starts `sentinel.service` (systemd)
6. Health-checks `GET /api/health`

### Deploy Frontend

```powershell
cd frontend\sentinel-ui
node_modules\.bin\vite build
aws s3 sync dist s3://<your-bucket> --delete
```

### Tear Down

```bash
terraform destroy                   # removes all AWS resources
```

---

## AI Feedback Loop — Demo Guide

The ⚡ **Insights** tab is the control centre for the closed-loop learning system.

```
Step 1 — Submit a 👎 rating on any analysis result (optionally add a comment)
         → correction logged to correction_examples.jsonl in the background

Step 2 — Open the Insights tab → click "▶ Run Review Agent"
         → LLM reads all 👎 entries, groups by doc type, classifies patterns:
              missing_rule         — a required clause is absent from the DB
              comprehension_failure — LLM consistently misreads an existing clause
         → Recommendation appears under "Pending Recommendations"

Step 3 — Click ✓ Approve
         missing_rule        → clause appended to regulatory_db.json (live immediately)
         comprehension_failure → phrase added to few_shot_examples.jsonl (injected into
                                 next compliance prompt automatically)

Step 4 — Re-analyse the same document → observe improvement

Step 5 — Click ↩ Undo at any time to reverse the change
```

`REVIEW_MIN_EVIDENCE=1` by default so the loop is demonstrable with a single 👎.

---

## Testing

```powershell
# Backend (584 tests, ~35 seconds)
cd backend
python -m pytest tests/ -v

# Frontend (173 tests)
cd frontend\sentinel-ui
node_modules\.bin\vitest run
```

| Suite | Tests | Covers |
|-------|-------|--------|
| Backend unit | ~470 | All agent nodes, data layer, auth, batch, feedback loop, review agent, insights endpoints |
| Backend integration | ~114 | Full pipeline + all API routes |
| Frontend | 173 | All 11 components + App + InsightsDashboard (SSE, approve/reject/undo) |
| **Total** | **~757** | |

All LLM calls are mocked — no Ollama required to run tests.

---

## Environment Variables

See `backend/.env.example` for the complete list.

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `ollama` | LLM backend (`ollama` only) |
| `OLLAMA_MODEL` | `gemma3:27b` | Model name passed to Ollama |
| `OLLAMA_BASE_URL` | `` | Empty = local port 11434; set to cloud URL in prod |
| `REVIEW_MIN_EVIDENCE` | `1` | Min 👎 items per doc type before review agent acts |
| `RATE_LIMIT` | `10` | Analyse requests per minute per IP |
| `EVAL_THRESHOLD` | `0.7` | Faithfulness below which pipeline retries |
| `SENTINEL_API_KEY` | `` | Optional static API key for all `/api/*` endpoints |

---

## Repository Structure

```
.
├── backend/
│   ├── agents/
│   │   ├── state.py               # AgentState TypedDict
│   │   ├── graph.py               # LangGraph StateGraph definition
│   │   ├── router_agent.py        # Guardrail + Router nodes
│   │   ├── compliance_agent.py    # Compliance node + few-shot injection
│   │   ├── eval_judge.py          # LLM-as-a-Judge evaluator
│   │   ├── expiry_agent.py        # Contract expiry date extraction
│   │   ├── review_agent.py        # AI feedback loop meta-agent  ← Phase G
│   │   └── llm_factory.py         # Provider abstraction (env-var driven)
│   ├── api/
│   │   ├── routes.py              # All FastAPI endpoints + SSE + HTML reports
│   │   ├── auth.py                # JWT login + bcrypt user store
│   │   └── auth_router.py         # /api/auth/* routes
│   ├── data/
│   │   ├── regulatory_db.json     # Clause requirements — patched by approve action
│   │   ├── few_shot_examples.jsonl  # Approved corrections injected into prompts
│   │   ├── correction_examples.jsonl # Negative feedback log (runtime, gitignored)
│   │   ├── history_store.py       # SQLite CRUD (analyses, feedback, recommendations…)
│   │   ├── embeddings.py          # FAISS index build + search
│   │   ├── guardrails.py          # PII regexes + injection patterns
│   │   ├── language_detector.py   # langdetect wrapper
│   │   └── metrics.py             # In-process Prometheus counters
│   ├── prompts/                   # Versioned LLM prompt templates (JSON)
│   ├── tests/
│   │   ├── unit/                  # 20 unit test modules
│   │   └── integration/           # 3 integration modules
│   ├── requirements.txt
│   └── .env.example
├── frontend/sentinel-ui/
│   ├── src/
│   │   ├── App.tsx                # 6-tab shell + SSE handler
│   │   └── components/
│   │       ├── FeedbackWidget.tsx       # Two-step 👍/👎 with comment box
│   │       ├── InsightsDashboard.tsx    # AI feedback loop control centre  ← Phase G
│   │       ├── HistoryPanel.tsx         # Paginated history + feedback column
│   │       ├── MetricsPanel.tsx         # Observability dashboard
│   │       ├── ClauseDiffViewer.tsx     # Retry diff table
│   │       ├── ConfidenceGauge.tsx      # SVG arc gauge
│   │       ├── BatchUpload.tsx          # ZIP batch upload + job polling
│   │       └── HelpPanel.tsx            # Inline user docs
│   └── src/__tests__/            # 11 test files, 173 tests
├── infra/
│   ├── main.tf                   # EC2 + S3 + CloudFront
│   ├── variables.tf              # Input variables with defaults
│   ├── outputs.tf                # URLs + SSH command
│   └── deploy-backend.sh         # EC2 bootstrap + app deploy script
├── docs/
│   ├── USER_GUIDE.md             # End-user documentation
│   └── DEVELOPER_GUIDE.md        # Architecture, API reference, extending Sentinel
├── sample_docs/                  # 55+ labelled test documents (all formats)
├── .github/workflows/
│   └── deploy.yml                # CI/CD: test → build → S3 sync → EC2 deploy
└── .gitignore
```

---

## Docs

- [User Guide](docs/USER_GUIDE.md) — for compliance officers and analysts
- [Developer Guide](docs/DEVELOPER_GUIDE.md) — architecture, API reference, how to extend

---

## License

MIT
