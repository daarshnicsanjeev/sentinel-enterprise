# Project Sentinel
### Enterprise Agentic Document Routing & Compliance Engine

A production-quality local PoC demonstrating multi-agent AI orchestration, RAG pipelines, LLM-as-a-Judge evaluation, and real-time SSE streaming — built for a JPMorgan CIB-style interview project.

---

## Architecture

```
[Document Upload]
      │
      ▼
[Guardrail Node]  ← blocks prompt injection & PII
      │
      ▼
[Router Node]     ← ChatOllama classifies doc type (prompts/router_v1.0.0.json)
      │
      ▼
[Compliance Node] ← queries regulatory_db.json tool, runs FAISS RAG + ChatOllama
      │
      ▼
[Evaluator Node]  ← LLM-as-a-Judge faithfulness score (prompts/evaluator_v1.0.0.json)
      │
      ├── score < 0.65 & retries < 2 → back to Compliance (feedback loop)
      └── else → END
      │
      ▼
[FastAPI SSE]     ← streams log events token-by-token to React dashboard
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Orchestration | LangGraph 1.2 (StateGraph + conditional edges) |
| LLM | Ollama `gemma4:e2b` (local, no cloud API key needed) |
| Embeddings + RAG | FAISS + OllamaEmbeddings (langchain-ollama) |
| Backend | FastAPI + uvicorn (SSE via StreamingResponse) |
| Frontend | React 19 + TypeScript + Vite |

## Quick Start

### 1. Backend

```powershell
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

> Requires Ollama running with `gemma4:e2b` pulled:
> `ollama pull gemma4:e2b`

### 2. Frontend

```powershell
cd frontend/sentinel-ui
npm install
npm run dev
```

Open `http://localhost:5173` and upload a document from `sample_docs/`.

---

## Sample Documents

| File | Expected Result |
|------|----------------|
| `sample_docs/credit_agreement_valid.txt` | `APPROVED` — all 4 required clauses present |
| `sample_docs/contract_missing_clause.txt` | `REJECTED` — missing force majeure & limitation of liability |

---

## MVP Success Criteria Verification

### 1. Successful loop handling
Upload `contract_missing_clause.txt`. The compliance node detects missing clauses, evaluator scores low, and the graph safely reaches `REJECTED` without runtime exceptions.

### 2. No-code prompt changes
Edit `backend/prompts/router_v1.0.0.json` — change the `"system"` field. Restart the backend. Router behaviour changes with zero Python edits.

### 3. End-to-end log stream
Expected console/UI output:
```
[Guardrail] Input sanitized: OK
[Router] Document classified as: LEGAL_CONTRACT
[Compliance Tool] Queried regulatory DB for LEGAL_CONTRACT → Required: ['force majeure clause', 'limitation of liability', 'dispute resolution clause']
[Compliance] Verdict: REJECTED
[Evaluator] Faithfulness: 0.82 | Hallucination Risk: low | Agent correctly identified missing clauses.
```

---

## FR Coverage Map

| Feature | Implementation |
|---------|---------------|
| FR-01 Multi-agent state machine | `agents/graph.py` — StateGraph with 5 nodes + conditional feedback loop |
| FR-02 Tool integration | `agents/compliance_agent.py` — `query_regulatory_db()` reads `data/regulatory_db.json` |
| FR-03 Hybrid RAG | `data/embeddings.py` — FAISS + OllamaEmbeddings + RecursiveCharacterTextSplitter |
| FR-04 Input guardrails | `data/guardrails.py` — injection pattern matching + PII regex |
| FR-05 LLM-as-a-Judge | `agents/eval_judge.py` — faithfulness + hallucination scoring |
| FR-06 Streaming UI | `api/routes.py` SSE + `WorkflowStream.tsx` with `aria-live="polite"` |
