# Architecture Decision Record — Project Sentinel

> Read this before refactoring any core module. Each decision records the reasoning so future agents don't unknowingly revert intentional choices.

---

## ADR-001: LangGraph over raw LangChain chains

**Decision:** Use `langgraph.StateGraph` as the orchestration primitive rather than LangChain `RunnableSequence` or a custom async loop.

**Reason:** LangGraph models the workflow as a Directed Cyclic Graph (DCG), which is the only way to implement a genuine feedback loop (evaluator → compliance retry). A `RunnableSequence` is a DAG — you can't send flow backwards. The interview context specifically values "workflow/state management" and "iterative feedback loops."

**Trade-off:** LangGraph has more boilerplate than a simple chain. For a purely linear pipeline, a `RunnableSequence` would be simpler. We need the DCG.

**Files:** `backend/agents/graph.py`, `backend/agents/state.py`

---

## ADR-002: AgentState as a TypedDict with a list reducer on `logs`

**Decision:** `AgentState` is a `TypedDict` (not a Pydantic model). The `logs` field uses `Annotated[list, operator.add]` — a LangGraph reducer that appends rather than overwrites.

**Reason:** Without the reducer, each node's returned dict would overwrite the `logs` field set by earlier nodes. The reducer merges: `existing_logs + new_logs`. This is essential for the SSE stream, which reads `logs` from every node's output incrementally.

**Trade-off:** Reducers require LangGraph's specific `Annotated` syntax. Pydantic models would give validation but don't support LangGraph reducers natively without adapters.

**Files:** `backend/agents/state.py`

---

## ADR-003: External JSON prompt files with semantic versioning

**Decision:** All LLM system prompts and templates live in `backend/prompts/*.json` files named with a semantic version (e.g., `router_v1.0.0.json`). Agents load them at module init time via `Path.read_text()`.

**Reason:** MVP Success Criterion #2 requires that changing an agent's behaviour must be achievable by editing an external file with zero Python changes. This is also a real enterprise pattern — prompt templates are configuration, not code.

**Trade-off:** Agents hold a module-level reference to the parsed prompt dict. If you update a prompt file, you must restart the server. For hot-reload without restart, use a watch-and-reload pattern.

**How to version up:** Copy `router_v1.0.0.json` → `router_v1.1.0.json`, edit it, then update the `_PROMPT_PATH` reference in `router_agent.py`. The old version is preserved.

**Files:** `backend/prompts/`, `backend/agents/router_agent.py`, `backend/agents/compliance_agent.py`, `backend/agents/eval_judge.py`

---

## ADR-004: FAISS index built per-request, not persisted

**Decision:** `build_index(text)` in `compliance_agent.py` creates a fresh FAISS index for each incoming document, processes it, and discards it.

**Reason:** This is a PoC with single-document workloads. Pre-building an index requires a document corpus, which we don't have. The goal is to demonstrate the RAG pipeline exists, not to optimise it.

**Trade-off:** Embedding a medium document (~1000 tokens) via `OllamaEmbeddings(model="gemma4:e2b")` takes 10–30 seconds on a local machine. This is the dominant latency in the system. Acceptable for demo; not for production.

**Production path:** Build the FAISS index once at startup over a corpus of reference documents, load it into a singleton, and use `semantic_search()` at request time.

**Files:** `backend/data/embeddings.py`, `backend/agents/compliance_agent.py`

---

## ADR-005: SSE via `fetch()` + `ReadableStream`, not `EventSource`

**Decision:** `App.tsx` uses `fetch()` with a `ReadableStream` reader to consume the SSE stream, rather than the browser's native `EventSource` API.

**Reason:** `EventSource` is GET-only. Our `/api/analyze` endpoint requires a multipart POST (file upload). There is no way to send a file via `EventSource`. The `fetch()` + stream pattern gives identical behaviour for consuming `text/event-stream` responses.

**Trade-off:** The manual buffer/split logic (`buffer.split("\n\n")`) is more verbose than `EventSource`'s event handling. It must handle partial chunks carefully. The implementation in `App.tsx` is correct — do not simplify it.

**Files:** `frontend/sentinel-ui/src/App.tsx`

---

## ADR-006: `ChatOllama` instead of `OllamaLLM` / `Ollama`

**Decision:** All LLM calls use `ChatOllama` from `langchain_ollama` (the newer package), not `langchain_community.llms.Ollama`.

**Reason:** `langchain_ollama.ChatOllama` is the actively maintained integration with `langchain-core`'s `ChatModel` interface. It supports structured output, tool calling, and the `langchain-core` `messages` protocol (`SystemMessage`, `HumanMessage`). `langchain_community.llms.Ollama` is a legacy text completion interface that doesn't support message roles.

**Files:** `backend/agents/router_agent.py`, `backend/agents/compliance_agent.py`, `backend/agents/eval_judge.py`

---

## ADR-007: Compliance node uses RAG before LLM

**Decision:** Before calling the LLM, `compliance_agent.py` runs each required clause through `semantic_search()` to retrieve the most relevant document chunks. Only these chunks are passed to the LLM prompt — not the full document.

**Reason:** `gemma4:e2b` has a limited effective context window for reliable output. Passing a full 5-page contract verbatim risks the LLM ignoring later sections. Retrieving the top-2 chunks per clause ensures the most relevant text is in the prompt.

**Trade-off:** The RAG step adds latency (FAISS build + embedding queries). It also means the LLM only sees excerpts — if a clause spans multiple sections, the RAG might not capture all of it. For PoC use with short sample docs, this is acceptable.

**Files:** `backend/agents/compliance_agent.py`, `backend/data/embeddings.py`

---

## ADR-008: Eval judge uses regex JSON extraction with fallback

**Decision:** `eval_judge.py` uses `re.compile(r"\{[^{}]+\}", re.DOTALL)` to extract a JSON object from the LLM response, with a fallback to `(0.5, "medium", "Could not parse...")` if extraction fails.

**Reason:** Local LLMs (especially smaller models like `gemma4:e2b`) frequently wrap JSON responses in markdown code fences or add preamble text despite instructions to return bare JSON. The regex finds the first JSON-like object in the response regardless of surrounding text.

**Trade-off:** The regex will miss nested JSON objects (e.g., `{"key": {"nested": 1}}`). Our expected response schema is flat, so this is safe. If the schema ever becomes nested, switch to `re.findall` + `json.loads` with recursion.

**Files:** `backend/agents/eval_judge.py`
