# HANDOVER.md — Project Sentinel
## Agent Briefing Document (Read This First)

> **Purpose:** This file is the single source of truth for any agent (Claude Code, Codex, human developer) picking up this project mid-flight. Read this entirely before touching any code or running any command.

> **Development Methodology: TDD.** All code changes follow Red → Green → Refactor. Tests live in `backend/tests/` (pytest) and `frontend/sentinel-ui/src/__tests__/` (vitest). Both suites must pass before any commit.

---

## 1. What This Project Is

**Project Sentinel** is a local proof-of-concept (PoC) demonstrating enterprise-grade agentic AI patterns for a JPMorgan CIB interview context. It routes and compliance-checks financial/legal documents through a LangGraph multi-agent state machine, streams results to a React dashboard via Server-Sent Events, and runs entirely on-device using Ollama.

**Interview framing:** This PoC maps directly to the FR matrix in `README.md` — each feature (FR-01 through FR-06) aligns to a stated capability in the JPMorgan "Full-Stack AI Engineer" job description.

---

## 2. Test Suite — Run This First

Before touching any code, verify the test suites are green:

```powershell
# Backend — 130 tests, ~10s, NO Ollama required
cd "C:\Sentinel Enterprise Agentic Document Routing & Compliance Engine\backend"
python -m pytest tests/ -v

# Frontend — 34 tests, ~3s
cd "C:\Sentinel Enterprise Agentic Document Routing & Compliance Engine\frontend\sentinel-ui"
node_modules\.bin\vitest run
```

### Test Architecture

| Layer | Location | Count | What's mocked |
|-------|----------|-------|---------------|
| Unit | `backend/tests/unit/` | 83 tests | Nothing — pure functions only |
| Integration nodes | `backend/tests/integration/test_agent_nodes.py` | 23 tests | `_llm`, `build_index`, `semantic_search` |
| Integration graph | `backend/tests/integration/test_graph_flow.py` | 15 tests | All three `_llm` instances + FAISS |
| Integration API | `backend/tests/integration/test_routes.py` | 9 tests | `graph.astream` |
| Frontend | `frontend/.../src/__tests__/` | 34 tests | `scrollIntoView` (jsdom gap) |

### TDD Rule for Future Work

```
1. RED   — Write a failing test that defines expected behaviour (no production code yet)
2. GREEN — Write minimum code to pass the test
3. REFACTOR — Clean up while keeping tests green
```

Never write implementation code before its test. A change to `regulatory_db.json` must be preceded by a failing test in `test_regulatory_db.py`.

### Bug Caught by TDD

The integration tests caught a production bug on first run: `evaluator_v1.0.0.json` contained `{"faithfulness"...}` as a literal string in `user_template`. Python's `.format()` interpreted this as a format placeholder and raised `KeyError`. Fixed by escaping: `{{"faithfulness"...}}`. This would have crashed every live Ollama inference run at the evaluator node.

---

## 3. Current Execution State

See [`STATUS.md`](STATUS.md) for the living state of the project. As of handover:

| Component | State |
|-----------|-------|
| Backend Python code | ✅ Written, imports verified |
| Prompt JSON files | ✅ Written (all 3 versioned files) |
| Regulatory DB tool | ✅ Written (`data/regulatory_db.json`) |
| Guardrails | ✅ Written and tested — injection blocking confirmed |
| LangGraph graph | ✅ Written with feedback loop |
| FastAPI SSE server | ✅ Written |
| React/TS frontend | ✅ Written, production build passes (20 modules) |
| End-to-end integration test | ⏳ Not yet run (Ollama must be running) |
| pip packages installed | ✅ fastapi, uvicorn, faiss-cpu, langchain-ollama |
| npm packages installed | ✅ node_modules present |

---

## 3. System Requirements (verify before starting)

```powershell
# Python version (need 3.10+)
python --version          # → 3.12.10 ✅

# Node version (need 18+)
node --version            # → v24.11.0 ✅

# Ollama running with gemma4:e2b pulled
ollama list               # must show gemma4:e2b
ollama serve              # start if not running
```

**Critical:** The backend calls `ChatOllama(model="gemma4:31b-cloud")`. If Ollama is not running, all agent nodes will fail with a connection error. Start Ollama first. `gemma4:31b-cloud` is a cloud-hosted model routed via the local Ollama daemon — it requires internet access but no local GPU.

### ⚠ Python Environment Note

The system has **two Python installations**:
- `C:\sanjeev\job-search\.python312\python.exe` — the **active venv** (used when you run `python`)
- `C:\Users\daars\AppData\Local\Programs\Python\Python312\` — the system Python (used by bare `pip`)

All backend packages are installed in the **venv**. Always use `python -m pip install` (not bare `pip`) to add new packages, or they will go into the wrong Python and imports will fail.

---

## 4. How to Start Everything

### Option A — Use the scripts (recommended)

```powershell
# Terminal 1: backend
.\scripts\start_backend.ps1

# Terminal 2: frontend
.\scripts\start_frontend.ps1

# Terminal 3: smoke test (optional, run after both servers are up)
.\scripts\verify.ps1
```

### Option B — Manual

```powershell
# Backend (from project root)
cd backend
uvicorn main:app --reload --port 8000

# Frontend (from project root)
cd frontend\sentinel-ui
npm run dev
```

Then open `http://localhost:5173` and upload a file from `sample_docs/`.

---

## 5. File Map (every file, what it does, what to change)

```
SENTINEL ROOT
├── HANDOVER.md              ← YOU ARE HERE
├── STATUS.md                ← Living state — update this when you make progress
├── README.md                ← Public-facing overview + FR coverage table
│
├── context/
│   ├── architecture.md      ← Why decisions were made (read before refactoring)
│   ├── known_issues.md      ← Bugs, TODOs, limitations
│   └── agent_state.json     ← Machine-readable state for programmatic agents
│
├── scripts/
│   ├── start_backend.ps1    ← Starts uvicorn on port 8000
│   ├── start_frontend.ps1   ← Starts Vite dev server on port 5173
│   └── verify.ps1           ← End-to-end smoke test (curl the API)
│
├── backend/
│   │
│   ├── main.py              ← FastAPI app entry point. Add new routers here.
│   ├── requirements.txt     ← pip dependencies
│   │
│   ├── agents/
│   │   ├── state.py         ← AgentState TypedDict. ADD fields here if state grows.
│   │   ├── graph.py         ← LangGraph StateGraph. CHANGE routing logic here.
│   │   ├── router_agent.py  ← guardrail_node + router_node. Loads router_v1.0.0.json.
│   │   ├── compliance_agent.py ← compliance_node + query_regulatory_db tool. Loads compliance_v1.0.0.json.
│   │   └── eval_judge.py    ← eval_node. Loads evaluator_v1.0.0.json.
│   │
│   ├── api/
│   │   └── routes.py        ← POST /api/analyze (SSE stream) + GET /api/health
│   │
│   ├── data/
│   │   ├── guardrails.py    ← sanitize(text) → (bool, reason). Add patterns here.
│   │   ├── embeddings.py    ← build_index(text) + semantic_search(index, query)
│   │   └── regulatory_db.json ← EDIT THIS to change required clauses per doc type.
│   │                           No Python changes needed — just edit the JSON.
│   │
│   └── prompts/             ← ⚠ CRITICAL: Edit these JSON files to change agent behaviour.
│       │                       Never hardcode prompts in Python files (PRD NFR).
│       ├── router_v1.0.0.json    ← System prompt + categories for Router agent
│       ├── compliance_v1.0.0.json ← System prompt + check template for Compliance agent
│       └── evaluator_v1.0.0.json  ← System prompt + scoring rubric for Eval Judge
│
├── frontend/
│   └── sentinel-ui/
│       └── src/
│           ├── App.tsx              ← Root component. SSE fetch logic lives here.
│           └── components/
│               ├── WorkflowStream.tsx ← Dark terminal log viewer. aria-live="polite"
│               ├── DocumentUpload.tsx ← Drag-and-drop file input
│               └── StatusBadge.tsx   ← APPROVED/REJECTED/RE-ROUTE colour pill
│
└── sample_docs/
    ├── credit_agreement_valid.txt    ← Should → APPROVED (all 4 clauses present)
    └── contract_missing_clause.txt   ← Should → REJECTED (missing force majeure + LoL)
```

---

## 6. Key Design Decisions (don't break these)

### 6a. Prompt files are sacrosanct
Agent prompts live in `backend/prompts/*.json` ONLY. MVP Success Criterion #2 requires that an agent's behaviour changes by editing a JSON file with zero Python changes. Do not move prompts inline.

### 6b. The feedback loop in graph.py
`graph.py` has a conditional edge: if `evaluation_score < 0.65 AND retry_count < 2`, the evaluator routes back to compliance. This demonstrates a Directed Cyclic Graph (DCG) — a key architectural talking point for the interview. Do not flatten it to a linear DAG.

### 6c. FAISS embeddings are per-request
`build_index()` in `compliance_agent.py` is called on every document. This is intentional for the PoC (no persistence needed). For production, you'd pre-index a corpus and load it once.

### 6d. `logs` field uses a LangGraph reducer
In `state.py`, `logs: Annotated[list, operator.add]` uses LangGraph's built-in list reducer so each node appends its log entries without overwriting previous nodes' logs. Don't change this to a plain `list` — it will break the SSE stream.

### 6e. SSE uses fetch + ReadableStream, not EventSource
`App.tsx` uses `fetch()` + `ReadableStream` reader instead of the `EventSource` API. This is required because `EventSource` only supports GET requests, and our `/api/analyze` endpoint is a POST (file upload). Don't refactor to EventSource.

---

## 7. How to Extend This Project

### Add a new document type
1. Add a new key to `backend/data/regulatory_db.json` with required clauses
2. Add the new category string to `backend/prompts/router_v1.0.0.json` → `"categories"` array
3. No Python changes needed

### Add a new agent node
1. Create `backend/agents/new_agent.py` with a function `(state: AgentState) -> dict`
2. Add the node to `backend/agents/graph.py` via `builder.add_node(...)`
3. Wire edges appropriately
4. Add a prompt file to `backend/prompts/`

### Add a new API endpoint
1. Add a route function to `backend/api/routes.py`
2. The router is already mounted at `/api` prefix in `main.py`

### Change the LLM model
Change `model=` in:
- `backend/agents/router_agent.py` (line: `_llm = ChatOllama(...)`)
- `backend/agents/compliance_agent.py`
- `backend/agents/eval_judge.py` (also has `format="json"` — keep it)

Current model: `gemma4:31b-cloud` (cloud-hosted via Ollama, requires internet)
Available local fallbacks: `gemma4:e2b` (7.2 GB), `gemma4:e4b` (9.6 GB)
Note: embeddings use keyword search (`SimpleIndex`) — no embedding model required.

---

## 8. Known Issues & Limitations

See [`context/known_issues.md`](context/known_issues.md) for the full list. Critical ones:

1. **FAISS embedding call is slow** — `OllamaEmbeddings` on `gemma4:e2b` for a medium document takes ~10–30 seconds. This is normal for a local PoC. Do not add a timeout on the SSE endpoint.

2. **LLM JSON parsing is best-effort** — `eval_judge.py` uses a regex to extract JSON from the LLM response. If the model hallucinates non-JSON output, it falls back to `(0.5, "medium", "Could not parse...")`. This is intentional defensive coding.

3. **No persistent vector store** — FAISS index is built per-request. Acceptable for PoC; use a persistent Chroma or Weaviate store for production.

4. **Global broken tsc** — The system has a broken global TypeScript at `C:\typescript\bin\tsc`. The `package.json` build script uses `node_modules\.bin\tsc` explicitly to work around this. Don't change the build script back to `tsc -b`.

---

## 9. Interview Talking Points (for the human handing over)

When demoing or discussing this project:

- **"How does the state machine work?"** → Point to `graph.py`. The `AgentState` is a shared TypedDict. Each node receives the full state and returns a partial dict of fields it changed. LangGraph merges them via reducers.

- **"What's the feedback loop?"** → `route_after_eval()` in `graph.py`. If the evaluator gives a low faithfulness score and we haven't retried twice yet, we increment `retry_count` and send the document back to the compliance node with more context.

- **"How do you prevent hallucination?"** → FR-05: The evaluator node is a separate LLM call that acts as a judge on the compliance agent's output — checking whether its PRESENT/MISSING claims are actually supported by the source document text.

- **"How is this different from a simple LLM call?"** → The multi-agent pattern separates concerns: the router specialises in classification, the compliance agent has access to an external tool (the regulatory DB), and the evaluator checks the compliance agent's work. Each has a focused, versioned prompt.

- **"How do you handle prompt injection?"** → `guardrails.py` runs before any LLM call. It pattern-matches against known injection phrases and PII regexes, and blocks at the API boundary before the document ever enters the state machine.

---

## 10. Next Steps (if picking up from here)

Priority order if continuing development:

1. **Run end-to-end test** — start Ollama + backend + frontend, upload `sample_docs/contract_missing_clause.txt`, verify REJECTED with log stream
2. **Tune eval threshold** — if the feedback loop fires too aggressively, raise `_SCORE_THRESHOLD` in `graph.py` from `0.65` to `0.75`
3. **Add a PDF ingestion path** — extract text from PDF via `pdfminer` before passing to guardrails
4. **Persist FAISS index** — call `build_index()` once at startup over a document corpus, then use `semantic_search()` for retrieval
5. **Add structured logging** — replace the `logs: list` pattern with `structlog` for production observability

---

*Last updated by: Claude Sonnet 4.6 (claude-sonnet-4-6) | 2026-05-16*
*Update this file whenever you make a significant change. The STATUS.md should be updated after every working session.*
