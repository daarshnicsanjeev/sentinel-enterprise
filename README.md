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
| **Vercel + Cloudflare Tunnel** | React frontend on Vercel HTTPS CDN; FastAPI backend tunnelled via Cloudflare Quick Tunnel — no domain required, no port exposure |
| **Self-healing tunnel URL** | EC2 systemd service auto-detects new tunnel URL on restart, patches Vercel env var, and triggers GitHub Actions redeploy automatically |
| **Terraform IaC** | One-command EC2 provisioning; S3 + CloudFront defined for reference/fallback |
| **GitHub Actions CI/CD** | Push to `main` → tests → Vercel frontend deploy → EC2 backend rsync → restart |

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

The live deployment uses **Vercel** for the HTTPS frontend and a **Cloudflare Quick Tunnel** for the HTTPS backend — both free, no domain required.

| Resource | Purpose | Cost |
|----------|---------|------|
| EC2 t3.micro | FastAPI + uvicorn | Free Tier — 750 hrs/month |
| EBS 25 GB gp3 | App + SQLite storage | Free Tier — 30 GB total |
| Cloudflare Quick Tunnel | HTTPS endpoint for FastAPI (no port 8000 exposure) | Free — no account needed |
| Vercel | React SPA hosting (HTTPS CDN, global edge) | Free — Hobby tier |

> S3 + CloudFront are defined in `infra/main.tf` for reference / fallback but are **not** used in the live deployment — S3 is HTTP-only and triggers Mixed Content errors in an HTTPS browser.

### Provision EC2 Infrastructure

```bash
cd infra
terraform init
terraform plan                      # preview
terraform apply                     # ~3 minutes — provisions EC2 only
```

### Deploy Backend (EC2 + Cloudflare Tunnel)

```bash
# One-shot: deploy app code + set up Cloudflare tunnel
bash infra/deploy-backend.sh
```

The script:
1. Installs system packages (Python, git, Tesseract, cloudflared)
2. Clones/updates the repo at `/opt/sentinel`
3. Creates a Python virtualenv at `/opt/sentinel-venv`
4. Installs `requirements.txt`
5. Writes `/opt/sentinel/backend/.env` (first run only)
6. Installs and starts `sentinel.service` (systemd)
7. Installs `cloudflared` from Cloudflare's apt repo
8. Writes and enables `cloudflared-tunnel.service` (systemd)
9. Creates `/opt/sentinel/update-tunnel-url.sh` (self-heal script)
10. Health-checks `GET /api/health`
11. Prints the live Cloudflare HTTPS tunnel URL

### Deploy Frontend (Vercel)

```bash
cd frontend/sentinel-ui
npm install -g vercel
vercel link                         # one-time: link to your Vercel account
vercel --prod                       # deploy to production
```

After every EC2 restart, the self-heal script automatically:
1. Reads the new `trycloudflare.com` URL from the systemd journal
2. PATCHes the Vercel `VITE_API_BASE_URL` env var via the Vercel API
3. Triggers a GitHub Actions `workflow_dispatch` to rebuild the frontend

### Tear Down

```bash
terraform destroy                   # removes EC2 + EBS
# To remove Vercel project: vercel remove sentinel-enterprise
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
│   └── deploy.yml                # CI/CD: test → Vercel frontend deploy → EC2 rsync → restart tunnel
└── .gitignore
```

---

## Demo Packages

Two ready-to-use ZIP files are included for running demos without any setup:

### `sample_docs batch demo.zip` (1.9 MB)
A complete batch upload demo — 51 labelled documents covering every supported format and decision path. Drop the ZIP directly into the **Batch Upload** tab.

| Category | Documents | Expected results |
|----------|-----------|-----------------|
| Legal Contracts | NDA, MSA, service agreement | APPROVED / REJECTED (missing clauses) |
| Credit Agreements | Syndicated loan, consumer mortgage, venture debt | APPROVED / REJECTED / ESCALATE |
| Employment Contracts | CEO, CTO, intern, missing-clause variants | APPROVED / REJECTED |
| Insurance Policies | Cyber liability, professional indemnity, D&O | APPROVED / REJECTED |
| Partnership Agreements | JV technology, missing dissolution | APPROVED / REJECTED |
| Regulatory Filings | SEC 10-K, GDPR DPA, EU tenant, missing risk factors | APPROVED / REJECTED |
| Guardrail tests | PII (SSN, passport, IBAN), prompt injection, SQL injection, DAN jailbreak | BLOCKED |
| Format variety | PDF, DOCX, XLSX, PPTX, HTML, PNG, JPG, TIFF (scanned), plain TXT | — |
| Language tests | French, Spanish, German contracts | WARNING (non-English) |
| Dedup test | Duplicate resubmission | Instant cached result |

### `sample_docs feedback loop demo.zip` (20 KB)
Five targeted documents + the Testing Guide for demonstrating the AI feedback loop end-to-end:

| File | Scenario | Purpose |
|------|----------|---------|
| `fl_test_s1_nda_all_current_clauses_APPROVED.txt` | S1 — missing_rule | Trigger: approved NDA missing data breach notification |
| `fl_test_s1_nda_with_breach_notice_APPROVED.txt` | S1 — missing_rule | Verify: NDA with breach notice clause (passes after fix) |
| `fl_test_s2_credit_unusual_phrasing_REJECTED_before_fix.txt` | S2 — comprehension_failure | Credit agreement with non-standard clause headings |
| `fl_test_s3_employment_all_current_clauses_APPROVED.txt` | S3 — missing_rule | Trigger: employment contract missing remote work policy |
| `fl_test_s3_employment_with_remote_work_APPROVED.txt` | S3 — missing_rule | Verify: employment contract with remote work clause |
| `FEEDBACK_LOOP_TESTING_GUIDE.md` | All | Step-by-step instructions with exact feedback text |

See [Feedback Loop Testing Guide](docs/FEEDBACK_LOOP_TESTING_GUIDE.md) for the complete walkthrough.

---

## Docs

- [User Guide](docs/USER_GUIDE.md) — for compliance officers and analysts
- [Developer Guide](docs/DEVELOPER_GUIDE.md) — architecture, API reference, how to extend
- [Feedback Loop Testing Guide](docs/FEEDBACK_LOOP_TESTING_GUIDE.md) — end-to-end demo walkthrough

---

## License

MIT
