import asyncio
import csv
import hashlib
import html as html_mod
import io
import ipaddress
import json
import os
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator, Literal
from urllib.parse import urlparse

import structlog

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, UploadFile, File, Form, HTTPException, Header
from fastapi.responses import FileResponse, HTMLResponse, Response, StreamingResponse
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from agents.graph import graph
from agents.state import AgentState
from data.file_extractor import extract_text as extract_file_text
from data.language_detector import detect_language
import data.history_store as history_store
import data.metrics as metrics
from api.auth import get_current_user, require_admin
from api.email_ingestor import strip_html
from data.report_generator import generate_pdf

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)
_log = structlog.get_logger("sentinel.routes")

# Feedback loop paths
_DATA_DIR = Path(__file__).parent.parent / "data"
_CORRECTION_JSONL_PATH = _DATA_DIR / "correction_examples.jsonl"
_FEW_SHOT_PATH = _DATA_DIR / "few_shot_examples.jsonl"
_REVIEW_MIN_EVIDENCE = int(os.environ.get("REVIEW_MIN_EVIDENCE", "1"))

# Sample documents directory (two levels up from backend/api/)
_SAMPLE_DOCS_DIR = (Path(__file__).parent.parent.parent / "sample_docs").resolve()
_SAMPLE_ALLOWED_EXT = {".txt", ".pdf", ".docx", ".xlsx", ".pptx", ".html", ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".zip"}

_MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB
_API_KEY = os.environ.get("SENTINEL_API_KEY", "")
_pending_overrides: dict[str, asyncio.Event] = {}
_override_decisions: dict[str, str] = {}
_override_lock = asyncio.Lock()

# tenant_id: alphanumeric, hyphens, underscores, 1-64 chars
_VALID_TENANT_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

# Internal hostnames/TLDs that must not receive webhook callbacks (SSRF protection)
_BLOCKED_CALLBACK_SUFFIXES = (".local", ".internal", ".localhost", ".docker", ".cluster.local")
_BLOCKED_CALLBACK_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}


_UUID_RE = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')


class OverrideRequest(BaseModel):
    decision: Literal["APPROVED", "REJECTED"]


class SetDecisionRequest(BaseModel):
    decision: Literal["APPROVED", "REJECTED", "ESCALATE"]


class FeedbackRequest(BaseModel):
    rating: Literal["positive", "negative"]
    comment: str = ""


def _validate_tenant_id(tenant_id: str) -> None:
    if not _VALID_TENANT_RE.match(tenant_id):
        raise HTTPException(
            status_code=400,
            detail="tenant_id must be 1-64 alphanumeric characters, underscores, or hyphens.",
        )


_EU_KEYWORDS = re.compile(
    r'\b(gdpr|solvency\s+ii|mifid|mifir|european\s+union|emir|idd|priip|aifmd|ucits|'
    r'general\s+data\s+protection|data\s+protection\s+regulation|eu\s+regulation)\b',
    re.IGNORECASE,
)
_US_KEYWORDS = re.compile(
    r'\b(dodd.frank|sarbanes.oxley|\bsox\b|sec\s+filing|finra|securities\s+exchange\s+act|'
    r'investment\s+advisers\s+act|volcker\s+rule|cftc|occ\s+guidance|us\s+gaap)\b',
    re.IGNORECASE,
)


def _infer_tenant(text: str) -> str:
    """Auto-detect EU vs US regulatory context from document keywords."""
    sample = text[:8000]
    eu_hits = len(_EU_KEYWORDS.findall(sample))
    us_hits = len(_US_KEYWORDS.findall(sample))
    if eu_hits > us_hits:
        return "EU"
    if us_hits > eu_hits:
        return "US"
    return "default"


_MAX_CALLBACK_URL_LEN = 2048


def _validate_callback_url(url: str) -> None:
    """Block callback URLs that point to internal/private resources (SSRF protection)."""
    if not url:
        return
    if len(url) > _MAX_CALLBACK_URL_LEN:
        raise HTTPException(status_code=400, detail="callback_url exceeds maximum allowed length.")
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise HTTPException(status_code=400, detail="callback_url must use http:// or https:// scheme.")
        hostname = (parsed.hostname or "").lower()
        if not hostname:
            raise HTTPException(status_code=400, detail="callback_url has no valid hostname.")
        if hostname in _BLOCKED_CALLBACK_HOSTS:
            raise HTTPException(status_code=400, detail="callback_url must not point to localhost.")
        if any(hostname.endswith(s) for s in _BLOCKED_CALLBACK_SUFFIXES):
            raise HTTPException(status_code=400, detail="callback_url must not point to internal hosts.")
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                raise HTTPException(status_code=400, detail="callback_url must not use private IP ranges.")
        except ValueError:
            pass  # hostname is not a bare IP — allow it
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid callback_url.")


async def _insert_failure(trace_id: str, filename: str, error_msg: str) -> None:
    try:
        await history_store.insert_failure({
            "trace_id": trace_id,
            "filename": filename,
            "error_msg": error_msg,
            "failed_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as exc:
        _log.error("history_insert_failure_error", trace_id=trace_id, error=str(exc))


async def _fire_webhook(url: str, payload: dict) -> None:
    if not url:
        return
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
            await client.post(url, json=payload)
    except httpx.TimeoutException:
        _log.warning("webhook_timeout", url=url)
    except httpx.HTTPError as exc:
        _log.warning("webhook_failed", url=url, error=str(exc))
    except Exception as exc:
        _log.error("webhook_unexpected_error", url=url, error=str(exc))


async def _save_to_history(trace_id: str, filename: str, final_state: dict, raw_text: str = "") -> None:
    try:
        await history_store.insert({
            "trace_id": trace_id,
            "filename": filename,
            "doc_type": final_state.get("doc_type", ""),
            "decision": final_state.get("final_decision", ""),
            "faithfulness": final_state.get("evaluation_score", 0.0),
            "risk": final_state.get("hallucination_risk", ""),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "raw_text": raw_text[:50_000] if raw_text else None,
        })
    except Exception as exc:
        _log.error("history_save_error", trace_id=trace_id, error=str(exc))


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
        "compliance_context": "",
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
        # Return a generic message — full error is in server logs, not exposed to caller
        error_payload = json.dumps({
            "type": "error",
            "message": "Document analysis failed. Contact support.",
            "trace_id": trace_id,
        })
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
    await _save_to_history(trace_id, _filename, final_state, raw_text=text)

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
        "from_cache": False,
        "sanitized": final_state.get("sanitized", True),
    }
    yield f"data: {json.dumps(done_payload_dict)}\n\n"

    if doc_hash:
        await history_store.insert_doc_cache(doc_hash, done_payload_dict)

    if callback_url:
        asyncio.create_task(_fire_webhook(callback_url, done_payload_dict))


_RATE_LIMIT      = os.environ.get("RATE_LIMIT", "20/minute")
_READ_RATE_LIMIT = os.environ.get("READ_RATE_LIMIT", "30/minute")


@router.post("/analyze")
@limiter.limit(_RATE_LIMIT)
async def analyze_document(
    request: Request,
    file: UploadFile = File(...),
    callback_url: str = Form(default=""),
    force_refresh: bool = Form(default=False),
):
    _validate_callback_url(callback_url)

    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided.")

    _ext = Path(file.filename).suffix.lower()
    if _ext not in _SINGLE_FILE_ALLOWED_EXT:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{_ext or file.filename}'. "
                   f"Allowed: PDF, TXT, DOCX, XLSX, PPTX, HTML, PNG, JPG, JPEG, TIFF.",
        )

    content = await file.read()

    if len(content) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 5 MB limit.")
    filename = file.filename or "untitled"

    try:
        text = extract_file_text(filename, content)
    except ValueError as exc:
        msg = str(exc)
        _log.warning("file_extraction_failed", filename=filename, error=msg)
        # Return user-friendly message; suppress internal library details
        if any(kw in msg for kw in ("no extractable text", "File must be", "exceeds", "magic bytes")):
            detail = msg
        else:
            detail = "File could not be processed. Ensure it is a valid, non-corrupted document."
        raise HTTPException(status_code=400, detail=detail)

    doc_hash = hashlib.sha256(content).hexdigest()

    if force_refresh:
        await history_store.delete_doc_cache(doc_hash)
        cached = None
    else:
        cached = await history_store.get_doc_cache(doc_hash)

    if cached is not None:
        # Back-fill sanitized for entries cached before this field was added.
        # A guardrail block leaves doc_type empty and clause_results empty;
        # everything else was a compliance/router decision (sanitized=True).
        if "sanitized" not in cached:
            is_guardrail_block = (
                not cached.get("doc_type") and
                not cached.get("clause_results") and
                cached.get("final_decision") in ("REJECTED", "BLOCKED", "UNKNOWN")
            )
            if is_guardrail_block:
                cached = {**cached, "sanitized": False, "final_decision": "BLOCKED"}
            else:
                cached = {**cached, "sanitized": True}
        cached_with_flag = {**cached, "from_cache": True}
        async def _cached_stream() -> AsyncGenerator[str, None]:
            yield f"data: {json.dumps(cached_with_flag)}\n\n"
        return StreamingResponse(
            _cached_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    tenant_id = _infer_tenant(text)
    trace_id = str(uuid.uuid4())
    return StreamingResponse(
        _stream_graph(text, trace_id, _filename=file.filename or "", tenant_id=tenant_id, callback_url=callback_url, doc_hash=doc_hash),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


_MAX_EMAIL_BODY_CHARS = 1_000_000


class EmailIngestionRequest(BaseModel):
    subject: str
    body: str
    tenant_id: str = "default"

    def validate_body_length(self) -> None:
        if not self.body:
            raise ValueError("body must not be empty")
        if len(self.body) > _MAX_EMAIL_BODY_CHARS:
            raise ValueError(f"body exceeds {_MAX_EMAIL_BODY_CHARS} character limit")


@router.post("/ingest/email")
@limiter.limit(_RATE_LIMIT)
async def ingest_email(request: Request, body: EmailIngestionRequest):
    if not body.body:
        raise HTTPException(status_code=422, detail="body must not be empty.")
    if len(body.body) > _MAX_EMAIL_BODY_CHARS:
        raise HTTPException(status_code=422, detail=f"body exceeds {_MAX_EMAIL_BODY_CHARS} character limit.")
    _validate_tenant_id(body.tenant_id)
    plain_body = strip_html(body.body)
    text = f"Subject: {body.subject}\n\n{plain_body}"
    trace_id = str(uuid.uuid4())
    return StreamingResponse(
        _stream_graph(text, trace_id, _filename=f"email:{body.subject[:80]}", tenant_id=body.tenant_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


_CUSTOM_CLAUSES_DIR = Path(__file__).parent.parent / "data" / "custom_clauses"
_CUSTOM_CLAUSES_DIR.mkdir(exist_ok=True)
_VALID_RISK_LEVELS = {"HIGH", "MEDIUM", "LOW"}

_REG_DB_PATH = Path(__file__).parent.parent / "data" / "regulatory_db.json"
# Loaded once at import time — disk read on every request eliminated
_REG_DB: dict = json.loads(_REG_DB_PATH.read_text())


def reload_reg_db() -> None:
    """Re-read regulatory_db.json from disk and update all in-memory caches.

    Updates both routes._REG_DB (used by the /clauses API endpoints) AND
    compliance_agent._regulatory_db (used by the compliance pipeline), so that
    subsequent analyses immediately pick up approved/undone recommendations
    without requiring a service restart.
    """
    global _REG_DB
    _REG_DB = json.loads(_REG_DB_PATH.read_text())
    _log.info("regulatory_db_reloaded", doc_types=list(_REG_DB.keys()))
    try:
        from agents.compliance_agent import reload_regulatory_db
        reload_regulatory_db()
    except Exception as exc:  # pragma: no cover
        _log.error("compliance_agent_reload_failed", error=str(exc))


def _remove_clause_from_reg_db(doc_type: str, clause_name: str) -> None:
    """Remove a previously approved clause from regulatory_db.json by name match.

    The file is structured as {tenant_id: {doc_type: [clauses]}}.
    Removes the clause from every tenant that contains it.
    """
    data = json.loads(_REG_DB_PATH.read_text())
    for tenant_data in data.values():
        if isinstance(tenant_data, dict) and doc_type in tenant_data:
            tenant_data[doc_type] = [
                c for c in tenant_data[doc_type]
                if c.get("name", "").lower().strip() != clause_name.lower().strip()
            ]
    _REG_DB_PATH.write_text(json.dumps(data, indent=2))
    reload_reg_db()


def _remove_few_shot_example(rec_id: str) -> None:
    """Remove an entry from few_shot_examples.jsonl by rec_id."""
    if not _FEW_SHOT_PATH.exists():
        return
    lines = _FEW_SHOT_PATH.read_text().splitlines()
    kept = []
    for line in lines:
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
            if entry.get("rec_id") != rec_id:
                kept.append(line)
        except json.JSONDecodeError:
            kept.append(line)
    _FEW_SHOT_PATH.write_text("\n".join(kept) + ("\n" if kept else ""))


def _append_correction_jsonl(entry: dict) -> None:
    """Sync write — called via BackgroundTask so it never blocks the HTTP response."""
    try:
        with open(_CORRECTION_JSONL_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as exc:
        _log.error("correction_jsonl_write_failed", error=str(exc))


def _remove_correction_jsonl_entries(trace_id: str) -> int:
    """Remove all correction-JSONL entries for a given trace_id.

    Returns the number of lines removed.  Called when a compliance officer
    ignores a specific feedback entry so the review agent won't process it.
    """
    if not _CORRECTION_JSONL_PATH.exists():
        return 0
    lines = _CORRECTION_JSONL_PATH.read_text(encoding="utf-8").splitlines()
    kept, removed = [], 0
    for line in lines:
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
            if entry.get("trace_id") == trace_id:
                removed += 1
            else:
                kept.append(line)
        except json.JSONDecodeError:
            kept.append(line)
    _CORRECTION_JSONL_PATH.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")
    return removed


def _load_tenant_clauses(tenant_id: str) -> dict | None:
    """Return clauses for tenant_id. Custom file overrides built-in DB. None = tenant not found."""
    custom_file = _CUSTOM_CLAUSES_DIR / f"{tenant_id}.json"
    if custom_file.exists():
        return json.loads(custom_file.read_text())
    # Built-in DB: try exact, then uppercase
    data = _REG_DB.get(tenant_id) or _REG_DB.get(tenant_id.upper())
    return data  # None if not in DB


def _validate_clauses_payload(payload: dict) -> None:
    """Raise HTTPException 422 if payload is not a valid clause dict."""
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="Payload must be a JSON object mapping doc_type → clauses list.")
    for doc_type, clauses in payload.items():
        if not isinstance(clauses, list):
            raise HTTPException(status_code=422, detail=f"{doc_type}: value must be a list of clause objects.")
        for i, clause in enumerate(clauses):
            if not isinstance(clause, dict) or not clause.get("name", "").strip():
                raise HTTPException(status_code=422, detail=f"{doc_type}[{i}]: each clause must be a dict with a non-empty 'name'.")
            if clause.get("risk_level") not in _VALID_RISK_LEVELS:
                raise HTTPException(
                    status_code=422,
                    detail=f"{doc_type}[{i}]: 'risk_level' must be HIGH, MEDIUM, or LOW (got {clause.get('risk_level')!r}).",
                )


@router.get("/clauses/{tenant_id}")
async def get_clauses(tenant_id: str):
    _validate_tenant_id(tenant_id)
    data = _load_tenant_clauses(tenant_id)
    if data is None:
        raise HTTPException(status_code=404, detail=f"No clause library found for tenant '{tenant_id}'.")
    return data


@router.get("/clauses/{tenant_id}/{doc_type}")
async def get_clauses_by_doc_type(tenant_id: str, doc_type: str):
    _validate_tenant_id(tenant_id)
    data = _load_tenant_clauses(tenant_id)
    if data is None:
        raise HTTPException(status_code=404, detail=f"No clause library found for tenant '{tenant_id}'.")
    return data.get(doc_type, [])


@router.post("/clauses/{tenant_id}", status_code=200)
async def post_clauses(
    tenant_id: str,
    payload: dict,
    current_user: dict = Depends(require_admin),
):
    _validate_tenant_id(tenant_id)
    _validate_clauses_payload(payload)
    custom_file = _CUSTOM_CLAUSES_DIR / f"{tenant_id}.json"
    custom_file.write_text(json.dumps(payload, indent=2))
    _log.info("custom_clauses_saved", tenant_id=tenant_id, doc_types=list(payload.keys()))
    return {"tenant_id": tenant_id, "doc_types": list(payload.keys())}


_MAX_BATCH_FILES = 50
_MAX_BATCH_ZIP_BYTES = 50 * 1024 * 1024        # 50 MB compressed
_MAX_BATCH_UNCOMPRESSED_BYTES = 200 * 1024 * 1024  # 200 MB total uncompressed (ZIP bomb guard)
_BATCH_ALLOWED_EXT = {".pdf", ".txt", ".docx", ".xlsx", ".pptx", ".html", ".htm",
                      ".png", ".jpg", ".jpeg", ".tiff", ".tif"}
_SINGLE_FILE_ALLOWED_EXT = _BATCH_ALLOWED_EXT  # same allowlist for single-file uploads
_BATCH_RATE_LIMIT = os.environ.get("BATCH_RATE_LIMIT", "2/minute")
# Limit concurrent LLM calls to avoid OOM on t2.micro (1 GB RAM)
_BATCH_CONCURRENCY = int(os.environ.get("BATCH_CONCURRENCY", "3"))
_batch_semaphore = asyncio.Semaphore(_BATCH_CONCURRENCY)
# Browsers report varying MIME types for ZIP files
_ZIP_CONTENT_TYPES = {
    "application/zip",
    "application/x-zip",
    "application/x-zip-compressed",
    "application/octet-stream",
    "application/x-compressed",
    "multipart/x-zip",
}


async def _run_graph_once(text: str, trace_id: str, filename: str, tenant_id: str) -> dict:
    """Run the LangGraph pipeline once and return the final state dict."""
    import time as _time
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
        "compliance_context": "",
        "logs": [],
    }
    final_state = initial_state.copy()
    try:
        async for event in graph.astream(initial_state, stream_mode="updates"):
            for _, node_output in event.items():
                final_state.update({k: v for k, v in node_output.items() if k != "logs"})
    except Exception as exc:
        _log.error("batch_item_failed", trace_id=trace_id, filename=filename, error=str(exc))
        final_state["final_decision"] = "UNKNOWN"
    return final_state


async def _process_batch(
    job_id: str, zf_bytes: bytes, names: list[str], force_refresh: bool = False
) -> None:
    import zipfile, io as _io
    zf = zipfile.ZipFile(_io.BytesIO(zf_bytes))
    results: list[dict] = []

    async def _run_one(name: str) -> dict:
        raw = zf.read(name)
        doc_hash = hashlib.sha256(raw).hexdigest()

        if force_refresh:
            await history_store.delete_doc_cache(doc_hash)
        else:
            cached = await history_store.get_doc_cache(doc_hash)
            if cached is not None:
                # ------------------------------------------------------------------
                # Back-fill 1: sanitized field (for entries cached before this field
                # was added).  A guardrail block has empty doc_type + clause_results
                # and a non-APPROVED terminal decision; everything else is sanitized.
                # ------------------------------------------------------------------
                if "sanitized" not in cached:
                    _is_guardrail = (
                        not cached.get("doc_type")
                        and not cached.get("clause_results")
                        and cached.get("final_decision") in ("REJECTED", "BLOCKED", "UNKNOWN")
                    )
                    if _is_guardrail:
                        cached = {**cached, "sanitized": False, "final_decision": "BLOCKED"}
                        # Persist the corrected payload so future hits are clean
                        await history_store.insert_doc_cache(doc_hash, cached)
                    else:
                        cached = {**cached, "sanitized": True}

                cache_trace_id = cached.get("trace_id", "")
                # ------------------------------------------------------------------
                # Back-fill 2: raw_text (for entries where it was never stored).
                # Extract text from the ZIP bytes already in hand so re-analysis
                # becomes available without requiring the user to re-upload.
                # ------------------------------------------------------------------
                can_reanalyze = False
                if cache_trace_id:
                    hist = await history_store.get_by_trace_id(cache_trace_id)
                    can_reanalyze = bool(hist and hist.get("raw_text"))
                if not can_reanalyze and cache_trace_id:
                    try:
                        text_for_backfill = extract_file_text(name, raw)
                    except ValueError:
                        text_for_backfill = raw.decode("utf-8", errors="replace")[:10000]
                    await history_store.update_raw_text(cache_trace_id, text_for_backfill)
                    can_reanalyze = True

                return {
                    "filename": name,
                    "trace_id": cache_trace_id,
                    "final_decision": cached.get("final_decision", "UNKNOWN"),
                    "evaluation_score": cached.get("evaluation_score", 0.0),
                    "sanitized": cached.get("sanitized", True),
                    "doc_hash": doc_hash,
                    "from_cache": True,
                    "can_reanalyze": can_reanalyze,
                }

        try:
            text = extract_file_text(name, raw)
        except ValueError:
            text = raw.decode("utf-8", errors="replace")[:10000]

        inferred_tenant = _infer_tenant(text)
        trace_id = str(uuid.uuid4())
        async with _batch_semaphore:  # max _BATCH_CONCURRENCY LLM calls at once
            final_state = await _run_graph_once(text, trace_id, name, inferred_tenant)
        await _save_to_history(trace_id, name, final_state, raw_text=text)

        done_payload = {
            "type": "done",
            "final_decision": final_state.get("final_decision", "UNKNOWN"),
            "doc_type": final_state.get("doc_type", ""),
            "evaluation_score": final_state.get("evaluation_score", 0.0),
            "hallucination_risk": final_state.get("hallucination_risk", ""),
            "routing_confidence": final_state.get("routing_confidence", 0.0),
            "clause_results": final_state.get("clause_results", []),
            "clause_results_history": [],
            "language": final_state.get("language", "en"),
            "trace_id": trace_id,
            "sanitized": final_state.get("sanitized", True),
        }
        await history_store.insert_doc_cache(doc_hash, done_payload)

        return {
            "filename": name,
            "trace_id": trace_id,
            "final_decision": final_state.get("final_decision", "UNKNOWN"),
            "evaluation_score": final_state.get("evaluation_score", 0.0),
            "sanitized": final_state.get("sanitized", True),
            "doc_hash": doc_hash,
            "from_cache": False,
            "can_reanalyze": True,  # raw_text was just stored above
        }

    tasks = [asyncio.ensure_future(_run_one(n)) for n in names]
    for i, fut in enumerate(asyncio.as_completed(tasks)):
        try:
            result = await fut
        except Exception as exc:
            result = {"filename": names[i] if i < len(names) else "unknown", "error": str(exc), "from_cache": False}
        results.append(result)
        status = "running" if i + 1 < len(names) else "completed"
        await history_store.update_batch_job(job_id, i + 1, results, status)


@router.post("/analyze/batch", status_code=202)
@limiter.limit(_BATCH_RATE_LIMIT)
async def analyze_batch(
    request: Request,
    file: UploadFile = File(...),
    force_refresh: bool = Form(default=False),
):
    import zipfile, io as _io

    content_type = (file.content_type or "").lower().split(";")[0].strip()
    if content_type not in _ZIP_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="Only ZIP files accepted.")

    content = await file.read()
    if len(content) > _MAX_BATCH_ZIP_BYTES:
        raise HTTPException(status_code=413, detail="ZIP exceeds 50 MB limit.")

    try:
        zf = zipfile.ZipFile(_io.BytesIO(content))
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Invalid or corrupted ZIP file.")

    # ZIP bomb protection — total uncompressed size
    total_uncompressed = sum(info.file_size for info in zf.infolist())
    if total_uncompressed > _MAX_BATCH_UNCOMPRESSED_BYTES:
        mb = total_uncompressed // (1024 * 1024)
        raise HTTPException(
            status_code=422,
            detail=f"ZIP would decompress to {mb} MB, exceeding the 200 MB limit.",
        )

    names = [n for n in zf.namelist() if not n.endswith("/")]

    # ZIP slip + unsafe path protection
    import stat as _stat
    for info in zf.infolist():
        name = info.filename
        if name.endswith("/"):
            continue
        # Null byte in filename
        if "\x00" in name:
            raise HTTPException(status_code=422, detail=f"Unsafe path in ZIP: {name!r}")
        # Path traversal (..)
        if ".." in name:
            raise HTTPException(status_code=422, detail=f"Unsafe path in ZIP: {name}")
        # Unix/Windows absolute path
        if name.startswith("/") or name.startswith("\\"):
            raise HTTPException(status_code=422, detail=f"Unsafe path in ZIP: {name}")
        # Windows drive-letter absolute path (e.g. C:\file.txt or C:/file.txt)
        if len(name) >= 2 and name[1] == ":":
            raise HTTPException(status_code=422, detail=f"Unsafe path in ZIP: {name}")
        # Symlink entries (Unix mode S_IFLNK = 0o120000)
        unix_mode = (info.external_attr >> 16) & 0o170000
        if unix_mode == 0o120000:
            raise HTTPException(status_code=422, detail=f"Symlink entry rejected: {name}")

    if len(names) > _MAX_BATCH_FILES:
        raise HTTPException(
            status_code=422,
            detail=f"ZIP contains {len(names)} files; maximum is {_MAX_BATCH_FILES}.",
        )

    for name in names:
        ext = Path(name).suffix.lower()
        if ext not in _BATCH_ALLOWED_EXT:
            raise HTTPException(status_code=422, detail=f"Unsupported file type in ZIP: {ext or name!r}")

    job_id = str(uuid.uuid4())
    await history_store.create_batch_job(job_id, len(names))
    asyncio.create_task(_process_batch(job_id, content, names, force_refresh=force_refresh))

    return {"job_id": job_id, "total": len(names)}


# ---------------------------------------------------------------------------
# Batch re-analyse by trace IDs (no file upload — uses stored raw_text)
# ---------------------------------------------------------------------------

class BatchReanalyzeRequest(BaseModel):
    trace_ids: list[str]


async def _process_batch_reanalyze(job_id: str, trace_ids: list[str]) -> None:
    results: list[dict] = []
    for i, trace_id in enumerate(trace_ids):
        try:
            record = await history_store.get_by_trace_id(trace_id)
            if not record or not record.get("raw_text"):
                filename = record.get("filename", trace_id) if record else trace_id
                result: dict = {"filename": filename, "error": "Original text not stored — re-upload the ZIP to re-analyse.", "from_cache": False, "can_reanalyze": False}
            else:
                raw_text: str = record["raw_text"]
                filename = record.get("filename", "document")
                inferred_tenant = _infer_tenant(raw_text)
                new_trace_id = str(uuid.uuid4())
                async with _batch_semaphore:
                    final_state = await _run_graph_once(raw_text, new_trace_id, filename, inferred_tenant)
                await _save_to_history(new_trace_id, filename, final_state, raw_text=raw_text)
                result = {
                    "filename": filename,
                    "trace_id": new_trace_id,
                    "final_decision": final_state.get("final_decision", "UNKNOWN"),
                    "evaluation_score": final_state.get("evaluation_score", 0.0),
                    "sanitized": final_state.get("sanitized", True),
                    "from_cache": False,
                    "can_reanalyze": True,
                }
        except Exception as exc:
            result = {"filename": trace_id, "error": str(exc), "from_cache": False}
        results.append(result)
        status = "running" if i + 1 < len(trace_ids) else "completed"
        await history_store.update_batch_job(job_id, i + 1, results, status)


@router.post("/analyze/batch-reanalyze", status_code=202)
@limiter.limit(_BATCH_RATE_LIMIT)
async def batch_reanalyze(request: Request, body: BatchReanalyzeRequest):
    if not body.trace_ids:
        raise HTTPException(status_code=422, detail="trace_ids must not be empty.")
    if len(body.trace_ids) > _MAX_BATCH_FILES:
        raise HTTPException(status_code=422, detail=f"Maximum {_MAX_BATCH_FILES} trace IDs per request.")
    for tid in body.trace_ids:
        if not _UUID_RE.match(tid):
            raise HTTPException(status_code=422, detail=f"Invalid trace_id format: {tid!r}")
    job_id = str(uuid.uuid4())
    await history_store.create_batch_job(job_id, len(body.trace_ids))
    asyncio.create_task(_process_batch_reanalyze(job_id, body.trace_ids))
    return {"job_id": job_id, "total": len(body.trace_ids)}


@router.get("/jobs/{job_id}")
@limiter.limit(_READ_RATE_LIMIT)
async def get_job_status(request: Request, job_id: str):
    if not _UUID_RE.match(job_id):
        raise HTTPException(status_code=422, detail="job_id must be a valid UUID.")
    job = await history_store.get_batch_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job


@router.post("/feedback/{trace_id}", status_code=201)
@limiter.limit("10/minute")
async def submit_feedback(
    request: Request,
    trace_id: str,
    body: FeedbackRequest,
    background_tasks: BackgroundTasks,
):
    if not _UUID_RE.match(trace_id):
        raise HTTPException(status_code=422, detail="trace_id must be a valid UUID.")
    comment = body.comment.strip()[:500]
    await history_store.insert_feedback(trace_id, body.rating, comment)

    # Log actionable feedback to JSONL for the review agent (non-blocking).
    # Direction matters:
    #   👎 always logged — could be missing rule or comprehension failure
    #   👍 on REJECTED/ESCALATE logged — indicates over-strict detection
    #   👍 on APPROVED skipped — pure confirmation, nothing to fix
    #   👍 on unknown decision skipped — can't infer direction
    record = await history_store.get_history_record(trace_id)
    doc_decision = (record.get("decision", "") if record else "").upper()
    _OVER_STRICT_DECISIONS = {"REJECTED", "ESCALATE"}
    _log_this_feedback = (
        body.rating == "negative"
        or (body.rating == "positive" and doc_decision in _OVER_STRICT_DECISIONS)
    )
    if _log_this_feedback:
        entry = {
            "trace_id": trace_id,
            "filename": record.get("filename", "") if record else "",
            "decision": doc_decision,
            "doc_type": record.get("doc_type", "") if record else "",
            "faithfulness": record.get("faithfulness", 0.0) if record else 0.0,
            "comment": comment,
            "rating": body.rating,
            "logged_at": datetime.now(timezone.utc).isoformat(),
        }
        background_tasks.add_task(_append_correction_jsonl, entry)

    return {"status": "recorded"}


@router.post("/feedback/{trace_id}/ignore", status_code=200)
@limiter.limit("30/minute")
async def ignore_feedback(
    request: Request,
    trace_id: str,
    background_tasks: BackgroundTasks,
):
    """Ignore all feedback for a trace_id.

    Removes the entry from both the SQLite feedback table and the correction
    JSONL file so the AI review agent won't include it in future recommendations.
    """
    if not _UUID_RE.match(trace_id):
        raise HTTPException(status_code=422, detail="trace_id must be a valid UUID.")
    deleted = await history_store.delete_feedback_by_trace_id(trace_id)
    if deleted == 0:
        raise HTTPException(status_code=404, detail="No feedback found for this trace_id.")
    background_tasks.add_task(_remove_correction_jsonl_entries, trace_id)
    _log.info("feedback_ignored", trace_id=trace_id, rows_deleted=deleted)
    return {"status": "ignored", "trace_id": trace_id, "rows_deleted": deleted}


@router.post("/history/{trace_id}/set-decision", status_code=200)
@limiter.limit("10/minute")
async def set_decision_override(request: Request, trace_id: str, body: SetDecisionRequest):
    """Persist a compliance officer decision override (used by the HTML report page)."""
    if not _UUID_RE.match(trace_id):
        raise HTTPException(status_code=422, detail="trace_id must be a valid UUID.")
    await history_store.update_decision(trace_id, body.decision)
    _log.info("decision_override", trace_id=trace_id, decision=body.decision)
    return {"trace_id": trace_id, "decision": body.decision}


@router.get("/feedback/summary")
@limiter.limit(_READ_RATE_LIMIT)
async def feedback_summary(request: Request):
    """Last 100 feedback entries joined with their analysis record."""
    data = await history_store.get_feedback_summary(limit=100)
    return data


@router.get("/feedback/export")
@limiter.limit(_READ_RATE_LIMIT)
async def export_feedback(request: Request):
    """CSV download of all feedback joined with analysis data."""
    rows = await history_store.get_feedback_summary(limit=1000)
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_ALL, lineterminator="\n")
    writer.writerow(["trace_id", "rating", "comment", "created_at", "filename", "decision", "doc_type", "faithfulness"])
    for r in rows:
        writer.writerow([
            r.get("trace_id", ""), r.get("rating", ""), r.get("comment", ""),
            r.get("created_at", ""), r.get("filename", ""), r.get("decision", ""),
            r.get("doc_type", ""), r.get("faithfulness", 0.0),
        ])
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=sentinel_feedback.csv"},
    )


@router.post("/override/{trace_id}")
async def override_decision(
    trace_id: str,
    body: OverrideRequest,
    current_user: dict = Depends(require_admin),
):
    async with _override_lock:
        if trace_id not in _pending_overrides:
            raise HTTPException(status_code=404, detail="No pending analysis found for the given trace_id.")
        _override_decisions[trace_id] = body.decision
        _pending_overrides[trace_id].set()
    return {"trace_id": trace_id, "override_applied": body.decision}


@router.get("/history")
@limiter.limit(_READ_RATE_LIMIT)
async def get_history(request: Request):
    records = await history_store.get_history(limit=50)
    return records


@router.get("/history/export")
@limiter.limit(_READ_RATE_LIMIT)
async def export_history(
    request: Request,
    current_user: dict = Depends(require_admin),
):
    csv_content = await history_store.get_history_csv()
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=sentinel_history.csv"},
    )


@router.get("/metrics/summary")
@limiter.limit(_READ_RATE_LIMIT)
async def get_metrics_summary(request: Request):
    from collections import defaultdict
    from datetime import timedelta

    rows = await history_store.get_all_history()

    total = len(rows)
    by_decision: dict[str, int] = {}
    faithfulness_sum = 0.0
    risk_counts: dict[str, int] = {"low": 0, "medium": 0, "high": 0}

    for r in rows:
        decision = r.get("decision", "UNKNOWN") or "UNKNOWN"
        by_decision[decision] = by_decision.get(decision, 0) + 1
        faithfulness_sum += float(r.get("faithfulness") or 0.0)
        risk = (r.get("risk") or "").lower()
        if risk in risk_counts:
            risk_counts[risk] += 1

    avg_faithfulness = round(faithfulness_sum / total, 3) if total else 0.0

    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    daily: dict[str, int] = defaultdict(int)
    for r in rows:
        try:
            dt = datetime.fromisoformat(r["created_at"])
            if dt >= cutoff:
                daily[dt.strftime("%Y-%m-%d")] += 1
        except (KeyError, ValueError, TypeError):
            pass

    feedback_stats = await history_store.get_feedback_stats()

    return {
        "total": total,
        "by_decision": by_decision,
        "avg_faithfulness": avg_faithfulness,
        "risk_distribution": risk_counts,
        "daily_last_7_days": dict(sorted(daily.items())),
        "feedback": feedback_stats,
    }


@router.get("/metrics")
@limiter.limit(_READ_RATE_LIMIT)
async def get_metrics(request: Request):
    return Response(
        content=metrics.render_prometheus(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )


@router.get("/failures")
@limiter.limit(_READ_RATE_LIMIT)
async def get_failures(request: Request):
    records = await history_store.get_failures(limit=50)
    return records


@router.get("/samples")
@limiter.limit(_READ_RATE_LIMIT)
async def list_samples(request: Request):
    """Return a list of downloadable sample documents."""
    if not _SAMPLE_DOCS_DIR.exists():
        return []
    files = []
    for f in sorted(_SAMPLE_DOCS_DIR.iterdir()):
        if f.is_file() and f.suffix.lower() in _SAMPLE_ALLOWED_EXT:
            files.append({
                "filename": f.name,
                "size_bytes": f.stat().st_size,
                "extension": f.suffix.lower(),
            })
    return files


@router.get("/samples/{filename}")
@limiter.limit(_READ_RATE_LIMIT)
async def download_sample(filename: str, request: Request):
    """Serve a single sample document for download."""
    safe_name = Path(filename).name  # strip any path traversal
    if not safe_name or safe_name in (".", ".."):
        raise HTTPException(status_code=400, detail="Invalid filename.")
    target = (_SAMPLE_DOCS_DIR / safe_name).resolve()
    # Ensure the resolved path stays inside _SAMPLE_DOCS_DIR
    if not str(target).startswith(str(_SAMPLE_DOCS_DIR)):
        raise HTTPException(status_code=400, detail="Invalid filename.")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="Sample document not found.")
    if target.suffix.lower() not in _SAMPLE_ALLOWED_EXT:
        raise HTTPException(status_code=400, detail="File type not permitted.")
    return FileResponse(
        path=str(target),
        filename=safe_name,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
    )


@router.get("/history/{trace_id}/report")
async def download_report(trace_id: str):
    if not _UUID_RE.match(trace_id):
        raise HTTPException(status_code=422, detail="Invalid trace_id format.")
    record = await history_store.get_history_record(trace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Analysis record not found.")
    pdf_bytes = generate_pdf(record)
    filename = f"sentinel_report_{trace_id[:8]}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


_DECISION_COLORS = {
    "APPROVED": "#15803d", "REJECTED": "#b91c1c",
    "ESCALATE": "#d97706", "BLOCKED": "#7c3aed",
    "PENDING": "#2563eb", "UNKNOWN": "#475569",
}


def _fmt_doc_type(raw: str) -> str:
    return " ".join(w.capitalize() for w in raw.split("_")) if raw else "—"


def _build_report_html(record: dict, can_reanalyze: bool, cache: dict | None = None) -> str:
    """Render a full standalone HTML compliance report matching the single-file upload result view."""
    e = html_mod.escape

    # ── core fields ─────────────────────────────────────────────────────────
    trace_id = e(record.get("trace_id", ""))
    filename = e(record.get("filename", "—"))
    created  = e(record.get("created_at", "—"))

    # cache payload is more authoritative for compliance fields
    c = cache or {}
    sanitized    = c.get("sanitized", True)
    raw_decision = c.get("final_decision") or record.get("decision", "UNKNOWN") or "UNKNOWN"
    decision     = "BLOCKED" if sanitized is False else raw_decision
    decision_esc = e(decision)

    raw_doc_type = c.get("doc_type") or record.get("doc_type", "")
    doc_type     = e(_fmt_doc_type(raw_doc_type))

    faithfulness     = float(c.get("evaluation_score") or record.get("faithfulness") or 0)
    faith_pct        = f"{faithfulness * 100:.0f}%"
    risk             = e(((c.get("hallucination_risk") or record.get("risk") or "—")).capitalize())
    routing_conf     = float(c.get("routing_confidence") or 0)
    language         = (c.get("language") or "en").lower()
    clause_results   = c.get("clause_results") or []

    badge_bg = _DECISION_COLORS.get(decision, "#475569")

    # ── optional grid cards ──────────────────────────────────────────────────
    conf_card = ""
    if routing_conf > 0:
        conf_card = f"""
        <div class="card">
          <dt>Routing Confidence</dt>
          <dd>{routing_conf * 100:.0f}%</dd>
        </div>"""

    score_cards = ""
    if sanitized is not False:
        score_cards = f"""
        <div class="card">
          <dt>Faithfulness Score</dt>
          <dd>{faith_pct}</dd>
        </div>
        <div class="card">
          <dt>Hallucination Risk</dt>
          <dd>{risk}</dd>
        </div>"""

    # Language card intentionally omitted — App.tsx does not show language in the result grid

    # ── ESCALATE notice ──────────────────────────────────────────────────────
    escalate_html = ""
    if decision == "ESCALATE":
        escalate_html = """
    <div role="note" aria-label="Escalation notice"
         style="margin-top:16px;padding:12px 16px;border-radius:8px;
                background:#1c1407;border:1px solid #d97706;color:#fbbf24;font-size:.85rem">
      <strong>⚠ Escalated for manual review.</strong>
      The compliance pipeline could not reach a confident decision.
      Clause statuses marked <strong>⚠ UNVERIFIED</strong> were claimed PRESENT
      but could not be independently confirmed. A compliance officer should
      review this document before routing.
    </div>"""

    # ── guardrail warning ────────────────────────────────────────────────────
    guardrail_html = ""
    if sanitized is False:
        guardrail_html = """
    <div role="note" aria-label="Document blocked by security guardrail"
         style="margin-top:16px;padding:12px 16px;border-radius:8px;
                background:#2e1065;border:1px solid #7c3aed;color:#ddd6fe;font-size:.85rem">
      <strong>⛔ Blocked by security guardrail.</strong>
      The document contained content matching a prompt-injection or disallowed-input pattern.
      No compliance analysis was performed. Review the document and re-upload if you believe
      this is a false positive.
    </div>"""

    # ── clause breakdown table ───────────────────────────────────────────────
    clause_html = ""
    if clause_results:
        rows = ""
        is_escalate = decision == "ESCALATE"
        for c_item in clause_results:
            cname    = e(str(c_item.get("clause", ""))[:200])
            status   = str(c_item.get("status", "")).upper()
            evidence = e(str(c_item.get("evidence", ""))[:200])
            # Mirror App.tsx clauseDisplayLabel: PRESENT under ESCALATE → ⚠ UNVERIFIED
            if is_escalate and status == "PRESENT":
                label      = "⚠ UNVERIFIED"
                sbg        = "#fef3c7"
                stxt       = "#92400e"
                sborder    = "1px solid #d97706"
            elif status == "PRESENT":
                label, sbg, stxt, sborder = "PRESENT", "#15803d", "#fff", "none"
            else:
                label, sbg, stxt, sborder = (status or "—"), "#b91c1c", "#fff", "none"
            rows += f"""
          <tr style="border-top:1px solid #1e293b">
            <td style="padding:6px 8px;color:#e2e8f0">{cname}</td>
            <td style="padding:6px 8px">
              <span style="background:{sbg};color:{stxt};border:{sborder};padding:2px 8px;
                           border-radius:4px;font-weight:700;font-size:.72rem">{label}</span>
            </td>
            <td style="padding:6px 8px;color:#94a3b8;font-size:.78rem">{evidence}</td>
          </tr>"""
        clause_html = f"""
    <section aria-labelledby="clauses-hd" style="margin-top:24px">
      <h2 id="clauses-hd">Clause Breakdown</h2>
      <div style="overflow-x:auto">
        <table style="width:100%;border-collapse:collapse;font-size:.82rem">
          <thead>
            <tr>
              <th scope="col" style="text-align:left;color:#64748b;padding:4px 8px;font-size:.72rem;text-transform:uppercase;letter-spacing:.05em">Clause</th>
              <th scope="col" style="text-align:left;color:#64748b;padding:4px 8px;font-size:.72rem;text-transform:uppercase;letter-spacing:.05em">Status</th>
              <th scope="col" style="text-align:left;color:#64748b;padding:4px 8px;font-size:.72rem;text-transform:uppercase;letter-spacing:.05em">Evidence</th>
            </tr>
          </thead>
          <tbody>{rows}
          </tbody>
        </table>
      </div>
    </section>"""

    # ── override & approve section (REJECTED, not BLOCKED) ──────────────────
    override_section = ""
    if decision == "REJECTED" and sanitized is not False:
        override_section = f"""
    <section aria-labelledby="override-hd"
             style="background:#1e293b;border-radius:10px;padding:20px;margin-top:24px">
      <h2 id="override-hd">Compliance Officer Override</h2>
      <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap">
        <span style="color:#94a3b8;font-size:.85rem">Compliance Officer Override:</span>
        <button id="override-btn"
                onclick="handleOverride()"
                style="background:#15803d;padding:7px 18px;font-size:.85rem">
          Override &amp; Approve
        </button>
      </div>
      <div id="override-status" role="status" aria-live="polite"
           style="margin-top:10px;font-size:.82rem"></div>
    </section>"""

    # ── feedback widget (non-BLOCKED) ────────────────────────────────────────
    feedback_section = ""
    if sanitized is not False:
        feedback_section = f"""
    <section aria-labelledby="feedback-hd" role="group" aria-label="Rate this analysis"
             style="background:#1e293b;border-radius:10px;padding:20px;margin-top:24px">
      <h2 id="feedback-hd">Feedback</h2>
      <p style="color:#94a3b8;font-size:.85rem;margin:0 0 12px">
        Was this analysis helpful?
      </p>
      <div id="fb-buttons" style="display:flex;gap:10px">
        <button id="fb-pos"
                aria-label="Mark analysis as helpful"
                onclick="onThumbsUp()"
                style="background:#1e3a5f;border:1px solid #2563eb;color:#93c5fd;
                       padding:7px 18px;font-size:1rem;font-weight:600">
          &#128077;
        </button>
        <button id="fb-neg"
                aria-label="Mark analysis as unhelpful"
                onclick="onThumbsDown()"
                style="background:#3b1f1f;border:1px solid #b91c1c;color:#fca5a5;
                       padding:7px 18px;font-size:1rem;font-weight:600">
          &#128078;
        </button>
      </div>
      <!-- comment step (hidden until 👎 clicked) -->
      <div id="fb-comment-box" style="display:none;margin-top:14px">
        <label for="fb-comment"
               style="display:block;color:#94a3b8;font-size:.82rem;margin-bottom:6px">
          What was wrong with this analysis? (optional)
        </label>
        <textarea id="fb-comment" maxlength="500"
                  aria-label="What was wrong"
                  style="width:100%;background:#0f172a;border:1px solid #334155;
                         border-radius:6px;color:#e2e8f0;padding:8px 10px;
                         font-size:.82rem;resize:vertical;min-height:72px"></textarea>
        <div style="display:flex;gap:8px;margin-top:8px">
          <button id="fb-submit" onclick="submitNegative()"
                  style="background:#b91c1c;border:none;color:#fff;padding:6px 18px;
                         border-radius:6px;font-weight:700;font-size:.82rem">
            Submit Feedback
          </button>
          <button onclick="cancelFeedback()"
                  style="background:none;border:1px solid #334155;color:#64748b;
                         padding:6px 14px;border-radius:6px;font-size:.82rem;cursor:pointer">
            Cancel
          </button>
        </div>
      </div>
      <div id="fb-status" role="status" aria-live="polite"
           style="margin-top:10px;font-size:.82rem"></div>
    </section>"""

    # ── fresh analysis section ───────────────────────────────────────────────
    fresh_section = ""
    if can_reanalyze:
        fresh_section = f"""
    <section aria-labelledby="fresh-hd"
             style="background:#1e293b;border-radius:10px;padding:20px;margin-top:24px">
      <h2 id="fresh-hd">Fresh Analysis</h2>
      <p style="color:#94a3b8;font-size:.85rem;margin:0 0 14px">
        Run the full compliance pipeline again on the stored document text — bypasses the cache.
      </p>
      <button id="fresh-btn" onclick="runFreshAnalysis()">&#8635; Re-analyse (clear cache)</button>
      <div id="fresh-status" role="status" aria-live="polite" style="margin-top:14px;font-size:.85rem"></div>
    </section>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Sentinel Report — {filename}</title>
  <style>
    *,*::before,*::after{{box-sizing:border-box}}
    body{{margin:0;font-family:'Segoe UI',system-ui,sans-serif;background:#0f172a;color:#e2e8f0;padding:32px 20px;line-height:1.6}}
    .wrap{{max-width:800px;margin:0 auto}}
    .header-row{{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;flex-wrap:wrap;margin-bottom:24px}}
    .logo{{font-size:1.1rem;font-weight:700;color:#60a5fa;letter-spacing:.03em;margin-bottom:6px}}
    h1{{margin:0 0 4px;font-size:1.5rem;color:#f1f5f9}}
    .subtitle{{color:#64748b;font-size:.85rem;margin:0}}
    h2{{color:#94a3b8;font-size:.85rem;margin:0 0 10px;font-weight:600;text-transform:uppercase;letter-spacing:.05em}}
    .close-btn{{padding:7px 16px;border-radius:6px;border:1px solid #334155;background:#1e293b;color:#94a3b8;font-size:.82rem;font-weight:600;cursor:pointer;flex-shrink:0;transition:background .15s,color .15s}}
    .close-btn:hover{{background:#334155;color:#e2e8f0}}
    .grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:0}}
    @media(max-width:520px){{.grid{{grid-template-columns:1fr}}}}
    .card{{background:#1e293b;border-radius:10px;padding:14px 16px}}
    dt{{font-size:.72rem;text-transform:uppercase;letter-spacing:.06em;color:#64748b;margin-bottom:4px;font-weight:600}}
    dd{{margin:0;font-size:.9rem;font-weight:600}}
    .badge{{display:inline-block;padding:3px 12px;border-radius:5px;font-size:.78rem;font-weight:700;color:#fff;background:{badge_bg}}}
    .mono{{font-family:'Courier New',monospace;font-size:.78rem;color:#94a3b8;word-break:break-all;font-weight:400}}
    button{{padding:9px 22px;border-radius:8px;border:none;background:#2563eb;color:#fff;font-weight:700;font-size:.88rem;cursor:pointer;transition:background .2s}}
    button:hover:not(:disabled){{background:#1d4ed8}}
    button:disabled{{background:#1e3a5f;color:#475569;cursor:not-allowed}}
    .log{{list-style:none;margin:8px 0 0;padding:10px;font-family:'Courier New',monospace;font-size:.78rem;color:#64748b;max-height:200px;overflow-y:auto;background:#0f172a;border-radius:6px}}
    .rg{{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:12px}}
    .rg dt{{font-size:.72rem;text-transform:uppercase;color:#64748b;letter-spacing:.06em}}
    .rg dd{{margin:0;font-weight:600}}
    .ok{{color:#4ade80;font-weight:600}}
    .err{{color:#f87171}}
    .inf{{color:#94a3b8}}
    footer{{margin-top:32px;color:#334155;font-size:.75rem;text-align:center;padding-top:16px;border-top:1px solid #1e293b}}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="header-row">
      <div>
        <div class="logo">⚡ Project Sentinel</div>
        <h1>Compliance Report</h1>
        <p class="subtitle">{filename}</p>
      </div>
      <button class="close-btn" onclick="window.close()" aria-label="Close this report tab">✕ Close</button>
    </div>

    <section aria-label="Analysis results" style="margin-bottom:24px">
      <div class="grid">
        <div class="card">
          <dt>Final Decision</dt>
          <dd><span class="badge">{decision_esc}</span></dd>
        </div>
        <div class="card">
          <dt>Document Type</dt>
          <dd>{doc_type}</dd>
        </div>{conf_card}{score_cards}
        <div class="card">
          <dt>Analysed</dt>
          <dd style="font-size:.82rem;font-weight:400">{created}</dd>
        </div>
        <div class="card" style="grid-column:span 1">
          <dt>Trace ID</dt>
          <dd class="mono">{trace_id}</dd>
        </div>
      </div>
    </section>
    {escalate_html}
    {guardrail_html}
    {clause_html}
    {override_section}
    {feedback_section}
    {fresh_section}
    <footer>Generated by Project Sentinel</footer>
  </div>

  <script>
    const TRACE_ID = "{trace_id}";

    async function handleOverride() {{
      const btn = document.getElementById('override-btn');
      const statusEl = document.getElementById('override-status');
      btn.disabled = true; btn.textContent = 'Applying…';
      try {{
        const res = await fetch('/api/history/' + TRACE_ID + '/set-decision', {{
          method: 'POST',
          headers: {{'Content-Type': 'application/json'}},
          body: JSON.stringify({{decision: 'APPROVED'}}),
        }});
        if (!res.ok) throw new Error('Server error ' + res.status);
        // Update the decision badge in the results grid
        const badge = document.querySelector('.badge');
        if (badge) {{ badge.textContent = 'APPROVED'; badge.style.background = '#15803d'; }}
        btn.remove();
        statusEl.innerHTML = '<p style="color:#4ade80">&#10003; Override applied — decision updated to APPROVED</p>';
      }} catch(e) {{
        btn.disabled = false; btn.textContent = 'Override & Approve';
        statusEl.innerHTML = '<p style="color:#f87171">Error: ' + e.message + '</p>';
      }}
    }}

    function onThumbsUp() {{
      // Positive: submit immediately (no comment needed)
      submitFeedback('positive', '');
    }}

    function onThumbsDown() {{
      // Negative: show comment box first
      document.getElementById('fb-buttons').style.display = 'none';
      document.getElementById('fb-comment-box').style.display = 'block';
      document.getElementById('fb-comment').focus();
    }}

    function cancelFeedback() {{
      document.getElementById('fb-comment-box').style.display = 'none';
      document.getElementById('fb-buttons').style.display = 'flex';
      document.getElementById('fb-comment').value = '';
    }}

    async function submitNegative() {{
      const comment = document.getElementById('fb-comment').value.trim();
      await submitFeedback('negative', comment);
    }}

    async function submitFeedback(rating, comment) {{
      const statusEl = document.getElementById('fb-status');
      const posBtn = document.getElementById('fb-pos');
      const negBtn = document.getElementById('fb-neg');
      const submitBtn = document.getElementById('fb-submit');
      if (posBtn) posBtn.disabled = true;
      if (negBtn) negBtn.disabled = true;
      if (submitBtn) submitBtn.disabled = true;
      try {{
        const body = {{rating: rating}};
        if (comment) body.comment = comment;
        const res = await fetch('/api/feedback/' + TRACE_ID, {{
          method: 'POST',
          headers: {{'Content-Type': 'application/json'}},
          body: JSON.stringify(body),
        }});
        if (!res.ok) throw new Error('Server error ' + res.status);
        document.getElementById('fb-buttons').style.display = 'none';
        document.getElementById('fb-comment-box').style.display = 'none';
        statusEl.innerHTML = rating === 'positive'
          ? '<p aria-live="polite" style="color:#4ade80">&#10003; Thanks for the positive feedback!</p>'
          : '<p aria-live="polite" style="color:#4ade80">&#10003; Thanks — we\'ll review this result.</p>';
      }} catch(e) {{
        if (posBtn) posBtn.disabled = false;
        if (negBtn) negBtn.disabled = false;
        if (submitBtn) submitBtn.disabled = false;
        statusEl.innerHTML = '<div role="alert" style="color:#f87171">Could not submit feedback: ' + e.message + '</div>';
      }}
    }}

    async function runFreshAnalysis() {{
      const btn = document.getElementById('fresh-btn');
      const statusEl = document.getElementById('fresh-status');
      btn.disabled = true; btn.textContent = 'Running…';
      statusEl.innerHTML = '<p class="inf">Connecting to analysis pipeline…</p>';
      let res;
      try {{
        res = await fetch('/api/history/' + TRACE_ID + '/reanalyze', {{method:'POST'}});
      }} catch(err) {{
        statusEl.innerHTML = '<p class="err">Network error: ' + err.message + '</p>';
        btn.disabled = false; btn.textContent = '↺ Re-analyse (clear cache)';
        return;
      }}
      if (!res.ok) {{
        statusEl.innerHTML = '<p class="err">Server error ' + res.status + '</p>';
        btn.disabled = false; btn.textContent = '↺ Re-analyse (clear cache)';
        return;
      }}
      const logList = document.createElement('ul');
      logList.className = 'log';
      logList.setAttribute('aria-label','Analysis log');
      statusEl.innerHTML = '<p class="inf">Analysis running…</p>';
      statusEl.appendChild(logList);
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let buf = '';
      try {{
        while (true) {{
          const {{done, value}} = await reader.read();
          if (done) break;
          buf += dec.decode(value, {{stream:true}});
          const parts = buf.split('\\n\\n'); buf = parts.pop() || '';
          for (const part of parts) {{
            const line = part.replace(/^data:\\s*/,'').trim();
            if (!line) continue;
            try {{
              const p = JSON.parse(line);
              if (p.type === 'log') {{
                const li = document.createElement('li');
                li.textContent = '[' + p.node + '] ' + p.message;
                logList.appendChild(li); logList.scrollTop = logList.scrollHeight;
              }} else if (p.type === 'done') {{
                const d = (p.sanitized === false) ? 'BLOCKED' : (p.final_decision || 'UNKNOWN');
                const col = {{"APPROVED":"#15803d","REJECTED":"#b91c1c","ESCALATE":"#d97706","BLOCKED":"#7c3aed","UNKNOWN":"#475569"}};
                const bg = col[d] || '#475569';
                statusEl.innerHTML =
                  '<p class="ok">&#10003; Fresh analysis complete — <a href="" onclick="location.reload();return false">reload page</a> to see updated report</p>'
                  + '<dl class="rg">'
                  + '<dt>Decision</dt><dd><span class="badge" style="background:' + bg + '">' + d + '</span></dd>'
                  + '<dt>Faithfulness</dt><dd>' + (p.evaluation_score * 100).toFixed(0) + '%</dd>'
                  + '<dt>New Trace ID</dt><dd class="mono" style="grid-column:span 2">' + (p.trace_id || '—') + '</dd>'
                  + '</dl>';
              }}
            }} catch(_) {{}}
          }}
        }}
      }} catch(err) {{
        statusEl.innerHTML += '<p class="err">Stream error: ' + err.message + '</p>';
      }}
    }}
  </script>
</body>
</html>"""


@router.get("/history/{trace_id}/report/html")
async def view_report_html(trace_id: str):
    if not _UUID_RE.match(trace_id):
        raise HTTPException(status_code=422, detail="Invalid trace_id format.")
    record = await history_store.get_history_record(trace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Analysis record not found.")
    raw = await history_store.get_by_trace_id(trace_id)
    can_reanalyze = bool(raw and raw.get("raw_text"))
    # Fetch full cache payload for clause_results, routing_confidence, language, sanitized
    cache = await history_store.get_cache_by_trace_id(trace_id)
    return HTMLResponse(content=_build_report_html(record, can_reanalyze, cache))


@router.post("/history/{trace_id}/reanalyze")
@limiter.limit(_RATE_LIMIT)
async def reanalyze_document(
    request: Request,
    trace_id: str,
    tenant_id: str = Query(default="default"),
):
    """Re-run the full analysis pipeline on a previously analysed document using its stored text."""
    if not _UUID_RE.match(trace_id):
        raise HTTPException(status_code=422, detail="Invalid trace_id format.")

    record = await history_store.get_by_trace_id(trace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Analysis record not found.")

    raw_text = record.get("raw_text")
    if not raw_text:
        raise HTTPException(
            status_code=422,
            detail="No stored text for this document. Re-upload the file to get a fresh analysis.",
        )

    _validate_tenant_id(tenant_id)
    new_trace_id = str(uuid.uuid4())
    filename = record.get("filename", "document")

    return StreamingResponse(
        _stream_graph(raw_text, new_trace_id, filename, tenant_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# Insights — AI review loop (on-demand, no scheduling)
# ---------------------------------------------------------------------------

@router.post("/admin/insights/run-review")
@limiter.limit("5/minute")
async def run_review_agent(
    request: Request,
    min_evidence: int = Query(default=1, ge=1, le=50),
):
    """Stream SSE logs from the review agent. Reads correction_examples.jsonl,
    calls the LLM meta-agent, and writes recommendations to DB."""
    from agents.review_agent import run_review
    return StreamingResponse(
        run_review(min_evidence=min_evidence),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/admin/insights/recommendations")
@limiter.limit(_READ_RATE_LIMIT)
async def get_recommendations(
    request: Request,
    status: str = Query(default="all"),
):
    """Return recommendations filtered by status (pending|approved|rejected|undone|all)."""
    valid = {"pending", "approved", "rejected", "undone", "all"}
    if status not in valid:
        raise HTTPException(status_code=422, detail=f"status must be one of: {', '.join(sorted(valid))}")
    recs = await history_store.get_recommendations(status=None if status == "all" else status)
    return recs


@router.post("/admin/insights/{rec_id}/approve", status_code=200)
@limiter.limit("20/minute")
async def approve_recommendation(request: Request, rec_id: str):
    """Apply a pending recommendation: patch regulatory_db.json or append few-shot example."""
    rec = await history_store.get_recommendation(rec_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found.")
    if rec["status"] != "pending":
        raise HTTPException(status_code=400, detail=f"Cannot approve a '{rec['status']}' recommendation.")

    now = datetime.now(timezone.utc).isoformat()

    if rec["rec_type"] == "missing_rule":
        # Parse proposed: may be plain string or JSON object
        try:
            proposed_obj = json.loads(rec["proposed"])
            clause_name = proposed_obj.get("name", rec["proposed"])
            risk_level = proposed_obj.get("risk_level", "MEDIUM")
        except (json.JSONDecodeError, TypeError):
            clause_name = rec["proposed"]
            risk_level = "MEDIUM"

        data = json.loads(_REG_DB_PATH.read_text())
        doc_type = rec["doc_type"]
        # The file is structured as {tenant_id: {doc_type: [clauses]}}.
        # Recommendations are generated from the "default" tenant pipeline.
        tenant_key = "default"
        if tenant_key not in data:
            data[tenant_key] = {}
        if doc_type not in data[tenant_key]:
            data[tenant_key][doc_type] = []
        # Reject duplicate — clause already exists in DB
        existing_names = [c.get("name", "").lower() for c in data[tenant_key][doc_type]]
        if clause_name.lower() in existing_names:
            raise HTTPException(
                status_code=409,
                detail=f"Clause '{clause_name}' already exists in the regulatory database for {doc_type}. No change was made.",
            )
        data[tenant_key][doc_type].append({"name": clause_name, "risk_level": risk_level})
        _REG_DB_PATH.write_text(json.dumps(data, indent=2))
        reload_reg_db()
        _log.info("recommendation_approved_missing_rule", rec_id=rec_id, clause=clause_name, doc_type=doc_type)

    elif rec["rec_type"] == "comprehension_failure":
        try:
            entry = json.loads(rec["proposed"])
        except (json.JSONDecodeError, TypeError):
            entry = {"correction": rec["proposed"]}
        entry["rec_id"] = rec_id
        entry["doc_type"] = rec["doc_type"]
        entry["locked_at"] = now
        with open(_FEW_SHOT_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        _log.info("recommendation_approved_comprehension", rec_id=rec_id, doc_type=rec["doc_type"])

    await history_store.set_recommendation_status(rec_id, "approved", resolved_at=now)
    return {"rec_id": rec_id, "status": "approved", "rec_type": rec["rec_type"]}


@router.post("/admin/insights/{rec_id}/reject", status_code=200)
@limiter.limit("20/minute")
async def reject_recommendation(request: Request, rec_id: str):
    """Reject a pending recommendation and blacklist the (doc_type, proposed) pair."""
    rec = await history_store.get_recommendation(rec_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found.")
    if rec["status"] != "pending":
        raise HTTPException(status_code=400, detail=f"Cannot reject a '{rec['status']}' recommendation.")

    now = datetime.now(timezone.utc).isoformat()
    await history_store.set_recommendation_status(rec_id, "rejected", resolved_at=now)
    await history_store.add_to_blacklist(rec["doc_type"], rec["proposed"])
    _log.info("recommendation_rejected", rec_id=rec_id, doc_type=rec["doc_type"])
    return {"rec_id": rec_id, "status": "rejected"}


@router.post("/admin/insights/{rec_id}/undo", status_code=200)
@limiter.limit("20/minute")
async def undo_recommendation(request: Request, rec_id: str):
    """Reverse an approved recommendation or re-open a rejected one."""
    rec = await history_store.get_recommendation(rec_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found.")
    if rec["status"] == "pending":
        raise HTTPException(status_code=400, detail="Nothing to undo on a pending recommendation.")
    if rec["status"] == "undone":
        raise HTTPException(status_code=400, detail="Recommendation is already undone.")

    now = datetime.now(timezone.utc).isoformat()

    if rec["status"] == "approved":
        if rec["rec_type"] == "missing_rule":
            try:
                proposed_obj = json.loads(rec["proposed"])
                clause_name = proposed_obj.get("name", rec["proposed"])
            except (json.JSONDecodeError, TypeError):
                clause_name = rec["proposed"]
            _remove_clause_from_reg_db(rec["doc_type"], clause_name)
            _log.info("recommendation_undone_missing_rule", rec_id=rec_id, clause=clause_name)
        elif rec["rec_type"] == "comprehension_failure":
            _remove_few_shot_example(rec_id)
            _log.info("recommendation_undone_comprehension", rec_id=rec_id)
        await history_store.set_recommendation_status(rec_id, "undone", resolved_at=now)
        return {"rec_id": rec_id, "action": "undone", "rec_type": rec["rec_type"], "status": "undone"}

    if rec["status"] == "rejected":
        # Re-open: revert to pending, remove from blacklist
        await history_store.set_recommendation_status(rec_id, "pending", resolved_at=None)
        await history_store.remove_from_blacklist(rec["doc_type"], rec["proposed"])
        _log.info("recommendation_reopened", rec_id=rec_id)
        return {"rec_id": rec_id, "action": "reopened", "rec_type": rec["rec_type"], "status": "pending"}


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

    # OpenSearch check (only when VECTOR_STORE=opensearch)
    import os as _os2
    if _os2.getenv("VECTOR_STORE", "faiss").lower() == "opensearch":
        import os as _os3
        llm_info["opensearch_host"] = _os3.getenv("OPENSEARCH_HOST", "localhost")
        llm_info["opensearch_port"] = _os3.getenv("OPENSEARCH_PORT", "9200")
        llm_info["opensearch_ssl"] = _os3.getenv("OPENSEARCH_USE_SSL", "false")
        try:
            from opensearchpy import OpenSearch as _OS
            _osc = _OS(
                hosts=[{"host": _os3.getenv("OPENSEARCH_HOST", "localhost"),
                        "port": int(_os3.getenv("OPENSEARCH_PORT", "9200"))}],
                http_auth=(_os3.getenv("OPENSEARCH_USER", "admin"),
                           _os3.getenv("OPENSEARCH_PASSWORD", "admin")),
                use_ssl=_os3.getenv("OPENSEARCH_USE_SSL", "false").lower() == "true",
                verify_certs=False,
                ssl_assert_hostname=False,
                timeout=5,
            )
            _osc.info()
            checks["opensearch"] = True
        except Exception as _exc:
            checks["opensearch"] = False
            llm_info["opensearch_error"] = str(_exc)[:300]
    else:
        checks["vector_store"] = True  # FAISS — always available

    # LLM connectivity check — quick ping with a tiny prompt (5 s timeout)
    import os as _os
    llm_info: dict = {
        "provider": _os.getenv("LLM_PROVIDER", "ollama"),
        "model": _os.getenv("OLLAMA_MODEL", "gemma4:31b-cloud"),
        "base_url": _os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
    }
    try:
        from agents.llm_factory import create_llm
        import asyncio as _asyncio
        _llm = create_llm(temperature=0.0)
        from langchain_core.messages import HumanMessage
        await _asyncio.wait_for(
            _asyncio.get_event_loop().run_in_executor(
                None,
                lambda: _llm.invoke([HumanMessage(content="Reply with one word: OK")])
            ),
            timeout=10.0,
        )
        checks["llm"] = True
    except Exception as _exc:
        checks["llm"] = False
        llm_info["error"] = str(_exc)[:200]

    status = "ok" if all(checks.values()) else "degraded"
    return {"status": status, "service": "Project Sentinel", "checks": checks, "llm": llm_info}
