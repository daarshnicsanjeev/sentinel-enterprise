# Plan Project Sentinel – Enterprise Agentic Document Routing & Compliance Engine

## Context

Building a weekend PoC that demonstrates enterprise-grade multi-agent AI architecture patterns for a JPMorgan CIB-style interview project. The goal is to show LangGraph state machines, RAG pipelines, SSE streaming, prompt versioning, and LLM-as-a-Judge evaluation — all running locally on Ollama with `gemma4e2b`.

Target directory `CSentinel Enterprise Agentic Document Routing & Compliance Engine` (currently empty).

---

## System Environment

- Python 3.12.10 — LangChain 1.0.7, LangGraph 1.2.0, pydantic 2.x already installed
- Ollama 0.23.3 — `gemma4e2b` (7.2 GB) available locally
- Node.js v24.11.0  npm 11.6.2
- Need to install `fastapi`, `uvicorn[standard]`, `faiss-cpu`, `python-multipart`, `sentence-transformers` (for embeddings)

---

## Final Directory Layout

```
CSentinel Enterprise Agentic Document Routing & Compliance Engine
├── backend
│   ├── agents
│   │   ├── __init__.py
│   │   ├── state.py               # AgentState TypedDict
│   │   ├── graph.py               # LangGraph compiled graph
│   │   ├── router_agent.py        # Node 1 document classifier
│   │   ├── compliance_agent.py    # Node 2 compliance checker + tool call
│   │   └── eval_judge.py          # Node 3 LLM-as-a-Judge
│   ├── api
│   │   ├── __init__.py
│   │   └── routes.py              # FastAPI endpoints + SSE stream
│   ├── data
│   │   ├── __init__.py
│   │   ├── guardrails.py          # FR-04 injectionPII blocking
│   │   ├── embeddings.py          # FR-03 FAISS RAG pipeline
│   │   └── regulatory_db.json     # Required clause ledger per doc type
│   ├── prompts
│   │   ├── router_v1.0.0.json
│   │   ├── compliance_v1.0.0.json
│   │   └── evaluator_v1.0.0.json
│   ├── main.py                    # FastAPI app entry point
│   └── requirements.txt
├── frontend
│   └── sentinel-ui               # Vite + React + TypeScript (npm create vite)
│       ├── src
│       │   ├── App.tsx
│       │   ├── components
│       │   │   ├── DocumentUpload.tsx
│       │   │   ├── WorkflowStream.tsx   # SSE consumer, aria-live
│       │   │   └── StatusBadge.tsx
│       │   └── main.tsx
│       ├── package.json
│       └── vite.config.ts
├── sample_docs
│   ├── credit_agreement_valid.txt
│   └── contract_missing_clause.txt
└── README.md
```

---

## Step-by-Step Implementation

### Step 1 — Install Missing Python Dependencies

```powershell
cd CSentinel Enterprise Agentic Document Routing & Compliance Engine
pip install fastapi uvicorn[standard] faiss-cpu python-multipart langchain-ollama
```

`langchain-ollama` provides `ChatOllama` and `OllamaEmbeddings` with the newer langchain-core interface.

---

### Step 2 — `backendagentsstate.py`

```python
from typing import TypedDict

class AgentState(TypedDict)
    raw_text str
    sanitized bool
    doc_type str
    required_clauses list
    evaluation_score float
    final_decision str
    retry_count int        # tracks feedback loop iterations
    logs list              # append-only event log for SSE streaming
```

---

### Step 3 — Prompt Files (`backendprompts`)

Three versioned JSON files. Agents load these at startup — no prompt strings in Python code.

router_v1.0.0.json
```json
{
  version 1.0.0,
  system You are a financial document classifier for a Commercial & Investment Bank...,
  categories [CREDIT_AGREEMENT, LEGAL_CONTRACT, REGULATORY_FILING, UNKNOWN]
}
```

compliance_v1.0.0.json
```json
{
  version 1.0.0,
  system You are a compliance officer checking a {doc_type} document...,
  check_instruction Verify the document contains all required clauses {required_clauses}...
}
```

evaluator_v1.0.0.json
```json
{
  version 1.0.0,
  system You are an impartial evaluator scoring compliance analysis for faithfulness...,
  scoring_rubric Return a JSON object with keys faithfulness (0.0-1.0), hallucination_risk (lowmediumhigh), rationale (string).
}
```

---

### Step 4 — `backenddataguardrails.py` (FR-04)

```python
INJECTION_PATTERNS = [
    ignore previous instructions,
    disregard your system prompt,
    you are now,
    act as if,
]
PII_PATTERNS = [rbd{3}-d{2}-d{4}b]   # SSN pattern example

def sanitize(text str) - tuple[bool, str]
    # Returns (is_clean, reason). Blocks prompt injection and PII.
```

---

### Step 5 — `backenddataregulatory_db.json` (FR-02 Tool)

```json
{
  CREDIT_AGREEMENT [
    governing law clause,
    events of default clause,
    indemnification clause,
    representations and warranties
  ],
  LEGAL_CONTRACT [
    force majeure clause,
    limitation of liability,
    dispute resolution clause
  ],
  REGULATORY_FILING [
    material disclosure statement,
    risk factor disclosures,
    auditor certification
  ]
}
```

---

### Step 6 — `backendagentsrouter_agent.py`

- Loads `promptsrouter_v1.0.0.json`
- Calls `ChatOllama(model=gemma4e2b)` with the system prompt
- Extracts `doc_type` from response
- Appends log entry `[Router] Classified as {doc_type}`
- Returns partial `AgentState`

---

### Step 7 — `backendagentscompliance_agent.py` (FR-02 Tool)

- Loads `promptscompliance_v1.0.0.json`
- Tool function `query_regulatory_db(doc_type) - list[str]` reads `regulatory_db.json`
- Passes required clauses into prompt context
- Calls `ChatOllama` to check if document contains each clause
- Appends log `[Compliance Tool] Required [...], Found [...]`
- Sets `final_decision` to `APPROVED` or `REJECTED` based on clause coverage

---

### Step 8 — `backendagentseval_judge.py` (FR-05)

- Loads `promptsevaluator_v1.0.0.json`
- Receives the compliance agent's output + original document text
- Sends to `ChatOllama` with scoring rubric
- Parses JSON response for `faithfulness` score (0.0–1.0)
- Appends log `[Evaluator] Score {score}  Risk {hallucination_risk}`
- Sets `evaluation_score` on state

---

### Step 9 — `backendagentsgraph.py` (FR-01 State Machine)

```python
from langgraph.graph import StateGraph, END
from .state import AgentState

builder = StateGraph(AgentState)
builder.add_node(guardrail, guardrail_node)
builder.add_node(router, router_node)
builder.add_node(compliance, compliance_node)
builder.add_node(evaluator, eval_node)

builder.set_entry_point(guardrail)
builder.add_edge(guardrail, router)
builder.add_edge(router, compliance)
builder.add_edge(compliance, evaluator)

# Feedback loop if score  0.7 and retry_count  2, re-run compliance
builder.add_conditional_edges(evaluator, route_after_eval, {
    retry compliance,
    done END
})

graph = builder.compile()
```

`route_after_eval` checks `evaluation_score  0.7 AND retry_count  2` → `retry`, else `done`.

---

### Step 10 — `backendapiroutes.py` (FR-06 SSE)

```python
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import asyncio, json

router = APIRouter()

@router.post(analyze)
async def analyze_document(file UploadFile)
    text = (await file.read()).decode()
    
    async def event_generator()
        initial_state = { raw_text text, logs [], retry_count 0, ... }
        async for event in graph.astream(initial_state)
            # Each node completion emits logs
            for node_name, node_state in event.items()
                for log_entry in node_state.get(logs, [])
                    yield fdata {json.dumps({'log' log_entry})}nn
        yield fdata {json.dumps({'done' True, 'decision' final_state['final_decision']})}nn
    
    return StreamingResponse(event_generator(), media_type=textevent-stream)
```

---

### Step 11 — `backendmain.py`

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import router

app = FastAPI(title=Project Sentinel)
app.add_middleware(CORSMiddleware, allow_origins=[httplocalhost5173], ...)
app.include_router(router, prefix=api)
```

---

### Step 12 — React Frontend (`frontendsentinel-ui`)

Bootstrap `npm create vite@latest sentinel-ui -- --template react-ts`

`WorkflowStream.tsx` — key component
```tsx
const [logs, setLogs] = useStatestring[]([]);
const logRef = useRefHTMLDivElement(null);

const startAnalysis = (file File) = {
  const formData = new FormData();
  formData.append(file, file);
  
  fetch(httplocalhost8000apianalyze, { method POST, body formData })
    .then(res = {
      const reader = res.body!.getReader();
       Read SSE stream token-by-token, parse JSON, append to logs
    });
};

return (
  div aria-live=polite aria-atomic=false ref={logRef}
    {logs.map((log, i) = p key={i}{log}p)}
  div
);
```

`DocumentUpload.tsx` — drag-and-drop file input, triggers `startAnalysis`.

`StatusBadge.tsx` — displays `APPROVED` (green)  `REJECTED` (red)  `RE-ROUTE` (amber)  `IN PROGRESS` (blue).

---

### Step 13 — Sample Documents (`sample_docs`)

`contract_missing_clause.txt` A 200-word mock legal contract deliberately missing force majeure clause and limitation of liability — triggers REJECTED path.

`credit_agreement_valid.txt` Contains all four required clauses — triggers APPROVED path.

---

### Step 14 — `backenddataembeddings.py` (FR-03 RAG)

```python
from langchain_ollama import OllamaEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter

def build_index(texts list[str]) - FAISS
    splitter = RecursiveCharacterTextSplitter(chunk_size=512, chunk_overlap=64)
    chunks = splitter.create_documents(texts)
    embeddings = OllamaEmbeddings(model=gemma4e2b)
    return FAISS.from_documents(chunks, embeddings)

def semantic_search(index FAISS, query str, k int = 3) - list[str]
    return [doc.page_content for doc in index.similarity_search(query, k=k)]
```

The compliance agent uses `semantic_search` to find the most relevant document sections before running its clause check — this wires FR-03 into FR-02.

---

## Implementation Order (Weekend Schedule)

 Hour  Task 
------------
 0–1   pip installs + project scaffold + `state.py` + prompt JSON files 
 1–2   `guardrails.py` + `regulatory_db.json` + `router_agent.py` 
 2–3   `compliance_agent.py` (with tool) + `eval_judge.py` 
 3–4   `graph.py` (LangGraph state machine + feedback loop) 
 4–5   `routes.py` (FastAPI SSE endpoint) + `main.py` + test with curl 
 5–7   React frontend scaffold → `WorkflowStream.tsx` → `DocumentUpload.tsx` → `StatusBadge.tsx` 
 7–8   End-to-end test with both sample docs, README 

---

## Verification Checklist (MVP Success Criteria)

1. Feedback loop Upload `contract_missing_clause.txt` → terminal shows `[Compliance Tool]` clause missing → evaluator scores low → state transitions to `RE-ROUTE` then `REJECTED` without exceptions.

2. No-code prompt change Edit `promptsrouter_v1.0.0.json` system string, re-run — router behavior changes without touching any `.py` file.

3. End-to-end log stream React dashboard OR terminal shows sequential log lines
   ```
   [Guardrail] Input sanitized OK
   [Router] Classified as LEGAL_CONTRACT
   [Compliance Tool] Required [force majeure, limitation of liability, dispute resolution]
   [Compliance Tool] Missing [force majeure, limitation of liability]
   [Evaluator] Score 0.42  Risk medium
   [Decision] Final REJECTED
   ```

Run commands
```powershell
# Backend
cd backend && uvicorn mainapp --reload --port 8000

# Frontend (separate terminal)
cd frontendsentinel-ui && npm run dev
```

Then open `httplocalhost5173`, upload a sample doc, watch the stream.