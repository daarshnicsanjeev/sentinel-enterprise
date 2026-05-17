import asyncio
import hashlib
import json
import os
import time
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator, Literal

import structlog

import httpx
from fastapi import APIRouter, BackgroundTasks, Request, UploadFile, File, Form, HTTPException, Header
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from agents.graph import graph
from agents.state import AgentState
from data.file_extractor import extract_text as extract_file_text
from data.language_detector import detect_language
import data.history_store as history_store
import data.metrics as metrics

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)
_log = structlog.get_logger("sentinel.routes")

_MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB
_API_KEY = os.environ.get("SENTINEL_API_KEY", "")
_pending_overrides: dict[str, asyncio.Event] = {}
_override_decisions: dict[str, str] = {}


class OverrideRequest(BaseModel):
    decision: Literal["APPROVED", "REJECTED"]


async def _insert_failure(trace_id: str, filename: str, error_msg: str) -> None:
    try:
        await history_store.init_db()
        await history_store.insert_failure({
            "trace_id": trace_id,
            "filename": filename,
            "error_msg": error_msg,
            "failed_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        pass


async def _fire_webhook(url: str, payload: dict) -> None:
    if not url:
        return
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(url, json=payload)
    except Exception:
        pass


async def _save_to_history(trace_id: str, filename: str, final_state: dict) -> None:
    try:
        from datetime import datetime, timezone
        await history_store.init_db()
        await history_store.insert({
            "trace_id": trace_id,
            "filename": filename,
            "doc_type": final_state.get("doc_type", ""),
            "decision": final_state.get("final_decision", ""),
            "faithfulness": final_state.get("evaluation_score", 0.0),
            "risk": final_state.get("hallucination_risk", ""),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        pass  # history persistence must never crash the main pipeline


def _check_api_key(x_api_key: str = Header(default="")) -> None:
    if _API_KEY and x_api_key != _API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key.")


async def _stream_graph(
    text: str,
    trace_id: str,
    _filename: str = "",
    tenant_id: str = "default",
    callback_url: str = "",
    doc_hash: str = "",
) -> AsyncGenerator[str, None]:
    language = detect_language(text)
    initial_state: AgentState = {
        "raw_text": text,
        "sanitized": True,
        "doc_type": "",
        "required_clauses": [],
        "compliance_output": "",
        "evaluation_score": 0.0,
        "hallucination_risk": "",
        "final_decision": "PENDING",
        "retry_count": 0,
        "trace_id": trace_id,
        "tenant_id": tenant_id,
        "routing_confidence": 0.0,
        "clause_results": [],
        "clause_results_history": [],
        "expiry_date": "",
        "language": language,
        "logs": [],
    }

    if language != "en" and language != "unknown":
        yield f"data: {json.dumps({'type': 'log', 'node': 'language', 'message': f'[Language] Non-English document detected: {language}. LLM accuracy may be reduced.'})}\n\n"

    final_state = initial_state.copy()
    _t0 = time.monotonic()

    try:
        async for event in graph.astream(initial_state, stream_mode="updates"):
            for node_name, node_output in event.items():
                for log_entry in node_output.get("logs", []):
                    payload = json.dumps({"type": "log", "node": node_name, "message": log_entry})
                    yield f"data: {payload}\n\n"
                    await asyncio.sleep(0.05)
                final_state.update({k: v for k, v in node_output.items() if k != "logs"})
    except Exception as exc:
        await _insert_failure(trace_id, _filename, str(exc))
        _log.error("pipeline_failed", trace_id=trace_id, filename=_filename, error=str(exc))
        error_payload = json.dumps({"type": "error", "message": str(exc)})
        yield f"data: {error_payload}\n\n"
        return

    decision = final_state.get("final_decision", "UNKNOWN")
    duration = time.monotonic() - _t0
    metrics.increment("sentinel_analyses_total", labels={"decision": decision})
    metrics.increment("sentinel_pipeline_duration_seconds", value=duration)

    _log.info(
        "analysis_complete",
        trace_id=trace_id,
        filename=_filename,
        decision=decision,
        doc_type=final_state.get("doc_type", ""),
        duration_s=round(duration, 3),
    )
    await _save_to_history(trace_id, _filename, final_state)

    done_payload_dict = {
        "type": "done",
        "final_decision": decision,
        "doc_type": final_state.get("doc_type", ""),
        "evaluation_score": final_state.get("evaluation_score", 0.0),
        "hallucination_risk": final_state.get("hallucination_risk", ""),
        "clause_results": final_state.get("clause_results", []),
        "clause_results_history": final_state.get("clause_results_history", []),
        "routing_confidence": final_state.get("routing_confidence", 0.0),
        "language": final_state.get("language", language),
        "trace_id": trace_id,
    }
    yield f"data: {json.dumps(done_payload_dict)}\n\n"

    if doc_hash:
        await history_store.insert_doc_cache(doc_hash, done_payload_dict)

    if callback_url:
        asyncio.create_task(_fire_webhook(callback_url, done_payload_dict))


@router.post("/analyze")
@limiter.limit("10/minute")
async def analyze_document(
    request: Request,
    file: UploadFile = File(...),
    tenant_id: str = Form(default="default"),
    callback_url: str = Form(default=""),
    x_api_key: str = Header(default=""),
):
    _check_api_key(x_api_key)

    if callback_url and not (callback_url.startswith("http://") or callback_url.startswith("https://")):
        raise HTTPException(status_code=400, detail="callback_url must use http:// or https:// scheme.")

    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided.")

    content = await file.read()

    if len(content) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 5 MB limit.")
    filename = file.filename or "untitled"

    try:
        text = extract_file_text(filename, content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    doc_hash = hashlib.sha256(content).hexdigest()
    await history_store.init_db()
    cached = await history_store.get_doc_cache(doc_hash)
    if cached is not None:
        async def _cached_stream() -> AsyncGenerator[str, None]:
            yield f"data: {json.dumps(cached)}\n\n"
        return StreamingResponse(
            _cached_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    trace_id = str(uuid.uuid4())
    return StreamingResponse(
        _stream_graph(text, trace_id, _filename=file.filename or "", tenant_id=tenant_id, callback_url=callback_url, doc_hash=doc_hash),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/override/{trace_id}")
async def override_decision(trace_id: str, body: OverrideRequest):
    if trace_id not in _pending_overrides:
        raise HTTPException(status_code=404, detail=f"No pending analysis found for trace_id: {trace_id}")
    _override_decisions[trace_id] = body.decision
    _pending_overrides[trace_id].set()
    return {"trace_id": trace_id, "override_applied": body.decision}


@router.get("/history")
async def get_history():
    await history_store.init_db()
    records = await history_store.get_history(limit=50)
    return records


@router.get("/history/export")
async def export_history():
    await history_store.init_db()
    csv_content = await history_store.get_history_csv()
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=sentinel_history.csv"},
    )


@router.get("/metrics")
async def get_metrics():
    return Response(
        content=metrics.render_prometheus(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@router.get("/failures")
async def get_failures():
    await history_store.init_db()
    records = await history_store.get_failures(limit=50)
    return records


@router.get("/health")
async def health():
    checks: dict[str, bool] = {}

    # Database check
    try:
        await history_store.init_db()
        checks["database"] = True
    except Exception:
        checks["database"] = False

    # Embeddings module check
    try:
        from data.embeddings import build_index_async  # noqa: F401
        checks["embeddings"] = True
    except Exception:
        checks["embeddings"] = False

    status = "ok" if all(checks.values()) else "degraded"
    return {"status": status, "service": "Project Sentinel", "checks": checks}
