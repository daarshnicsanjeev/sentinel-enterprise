# Known Issues & Limitations — Project Sentinel

> This is a living document. Add issues as they are discovered. Mark resolved issues rather than deleting them (for audit trail).

---

## Open Issues

### KI-001: FAISS + OllamaEmbeddings replaced with keyword search *(resolved — see KI-R003)*
- **Was:** `OllamaEmbeddings(model="gemma4:e2b")` returned HTTP 501 (model does not support embeddings API)
- **Fixed:** `backend/data/embeddings.py` now uses `SimpleIndex` — keyword-overlap scoring, no embedding model required
- **Production note:** For production, replace `SimpleIndex` with `FAISS` + `nomic-embed-text` or `sentence-transformers/all-MiniLM-L6-v2`

### KI-002: Eval judge JSON output — resolved with gemma4:31b-cloud + format="json" *(resolved 2026-05-16)*
- **Was:** `gemma4:e2b` sometimes added markdown fences or preamble around the JSON response, requiring best-effort regex extraction with a fallback score.
- **Fix:** Switched to `gemma4:31b-cloud` and added `format="json"` to the evaluator's `ChatOllama` instance. The model now always returns bare JSON — regex extractor still in place as a belt-and-suspenders fallback.
- **Verified:** Both sample docs return `faithfulness: 1.0` with correctly structured JSON on every run.

### KI-003: Global TypeScript binary broken on this system
- **Severity:** Low (workaround in place)
- **Root cause:** `C:\typescript\bin\tsc` exists on PATH but is not functional.
- **Workaround:** `package.json` build script uses `node_modules\.bin\tsc` explicitly. The `dev` script (`vite`) is unaffected. TypeScript type-checking runs correctly via the local binary.
- **Do not:** Change `"build": "node_modules\\.bin\\tsc -b && vite build"` back to `"build": "tsc -b && vite build"`.

### KI-004: RE-ROUTE now emitted as distinct final_decision *(resolved 2026-05-16)*
- **Was:** `_increment_retry` only bumped `retry_count`, so `final_decision` stayed `REJECTED` even mid-retry
- **Fix:** `_increment_retry` now returns `{"retry_count": n+1, "final_decision": "RE-ROUTE"}`. The next compliance run overwrites with `APPROVED` or `REJECTED`.
- **Test added:** `TestIncrementRetry::test_sets_re_route_as_final_decision`

### KI-005: CORS is permissive (localhost only)
- **Severity:** Low (intentional for PoC)
- **Root cause:** `main.py` allows `http://localhost:5173` and `http://127.0.0.1:5173`. No other origins accepted.
- **This is intentional** for a local PoC. Do not open CORS to `*` for a production deployment.

---

## Resolved Issues

### KI-R001: `operator.add` reducer not applied to `logs` field *(resolved before first commit)*
- **Was:** `logs: list` caused each node to overwrite prior nodes' log entries
- **Fix:** Changed to `logs: Annotated[list, operator.add]` in `state.py`
- **Verified by:** SSE stream correctly shows all nodes' logs sequentially

### KI-R003: `gemma4:e2b` returns 501 for embedding requests *(resolved 2026-05-16)*
- **Was:** `OllamaEmbeddings(model="gemma4:e2b")` crashed compliance node with `ResponseError: this model does not support embeddings (status code: 501)`
- **Was:** `ChatOllama` / `OllamaEmbeddings` defaulted to `localhost:11434` which resolved to `::1` (IPv6) on Windows — Ollama not bound to IPv6 → `httpx.ConnectError: [WinError 10049]`
- **Fix 1:** All `ChatOllama` and `OllamaEmbeddings` instances now use `base_url="http://127.0.0.1:11434"`
- **Fix 2:** `embeddings.py` replaced with `SimpleIndex` keyword-search (same API, no embedding model required)
- **Verified by:** Full E2E test — both sample docs produce correct REJECTED/APPROVED decisions

### KI-R002: `EventSource` API incompatible with POST file upload *(resolved before first commit)*
- **Was:** Initial plan used `EventSource` for SSE consumption
- **Fix:** Switched to `fetch()` + `ReadableStream` reader in `App.tsx`
- **See:** ADR-005 in `context/architecture.md`

---

## Technical Debt (not bugs, but worth tracking)

| ID | Item | Impact | Effort |
|----|------|--------|--------|
| TD-001 | ~~No unit tests~~ — 164 tests now cover all layers | ✅ Resolved in Session 2 | — |
| TD-002 | LLM instances created at module level (not injected) | Hard to swap models without restarting | Low |
| TD-003 | No request timeout on the SSE endpoint | A hung Ollama call will block the connection indefinitely | Medium |
| TD-004 | `compliance_agent.py` builds keyword index synchronously inside async endpoint | Negligible for keyword search, was high for FAISS | Low (resolved by keyword switch) |
| TD-005 | No logging framework (uses `logs` list for agent events only) | Hard to debug server errors in production | Medium |
