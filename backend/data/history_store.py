import asyncio
import csv
import io
import json
import os
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

import aiosqlite
from contextlib import asynccontextmanager

_DB_PATH = os.environ.get(
    "SENTINEL_DB_PATH",
    str(Path(__file__).parent.parent / "sentinel_history.db"),
)

# SQLite busy timeout in milliseconds.  When multiple coroutines write
# concurrently the default timeout (5 s in Python's sqlite3) is too short
# under batch load.  30 s gives writers plenty of room to queue.
_SQLITE_TIMEOUT = 30


@asynccontextmanager
async def _connect():
    """Open a DB connection with WAL mode and a generous busy timeout."""
    async with aiosqlite.connect(_DB_PATH, timeout=_SQLITE_TIMEOUT) as db:
        # WAL allows concurrent reads while a write is in progress, and
        # serialises concurrent writes without raising "database is locked".
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute(f"PRAGMA busy_timeout={_SQLITE_TIMEOUT * 1000}")
        yield db

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS analyses (
    id          TEXT PRIMARY KEY,
    trace_id    TEXT NOT NULL,
    filename    TEXT,
    doc_type    TEXT,
    decision    TEXT,
    faithfulness REAL,
    risk        TEXT,
    created_at  TEXT
)
"""

_CREATE_FAILURES_TABLE = """
CREATE TABLE IF NOT EXISTS failed_analyses (
    id          TEXT PRIMARY KEY,
    trace_id    TEXT NOT NULL,
    filename    TEXT,
    error_msg   TEXT,
    failed_at   TEXT
)
"""

_CREATE_DOC_CACHE_TABLE = """
CREATE TABLE IF NOT EXISTS doc_cache (
    doc_hash    TEXT PRIMARY KEY,
    payload     TEXT NOT NULL,
    cached_at   TEXT NOT NULL
)
"""

_CREATE_BATCH_JOBS_TABLE = """
CREATE TABLE IF NOT EXISTS batch_jobs (
    job_id      TEXT PRIMARY KEY,
    status      TEXT NOT NULL DEFAULT 'pending',
    total       INTEGER NOT NULL,
    completed   INTEGER NOT NULL DEFAULT 0,
    results     TEXT NOT NULL DEFAULT '[]',
    created_at  TEXT NOT NULL
)
"""

_CREATE_FEEDBACK_TABLE = """
CREATE TABLE IF NOT EXISTS feedback (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    trace_id    TEXT NOT NULL,
    rating      TEXT NOT NULL CHECK(rating IN ('positive', 'negative')),
    comment     TEXT,
    created_at  TEXT NOT NULL
)
"""

_CREATE_RECOMMENDATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS recommendations (
    rec_id         TEXT PRIMARY KEY,
    doc_type       TEXT NOT NULL,
    rec_type       TEXT NOT NULL CHECK(rec_type IN ('missing_rule','comprehension_failure')),
    proposed       TEXT NOT NULL,
    evidence_count INTEGER NOT NULL DEFAULT 1,
    confidence     TEXT NOT NULL CHECK(confidence IN ('high','medium','low')),
    rationale      TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'pending'
                       CHECK(status IN ('pending','approved','rejected','undone')),
    created_at     TEXT NOT NULL,
    resolved_at    TEXT
)
"""

_CREATE_BLACKLIST_TABLE = """
CREATE TABLE IF NOT EXISTS recommendation_blacklist (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_type    TEXT NOT NULL,
    proposed    TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    UNIQUE(doc_type, proposed)
)
"""

_CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_analyses_trace_id  ON analyses  (trace_id)",
    "CREATE INDEX IF NOT EXISTS idx_analyses_created_at ON analyses (created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_failures_trace_id  ON failed_analyses (trace_id)",
    "CREATE INDEX IF NOT EXISTS idx_feedback_trace_id  ON feedback (trace_id)",
]


async def init_db() -> None:
    async with _connect() as db:
        await db.execute(_CREATE_TABLE)
        await db.execute(_CREATE_FAILURES_TABLE)
        await db.execute(_CREATE_DOC_CACHE_TABLE)
        await db.execute(_CREATE_BATCH_JOBS_TABLE)
        await db.execute(_CREATE_FEEDBACK_TABLE)
        await db.execute(_CREATE_RECOMMENDATIONS_TABLE)
        await db.execute(_CREATE_BLACKLIST_TABLE)
        for idx_sql in _CREATE_INDEXES:
            await db.execute(idx_sql)
        # Additive migrations (no-op if column already exists)
        try:
            await db.execute("ALTER TABLE analyses ADD COLUMN raw_text TEXT")
        except Exception:
            pass
        await db.commit()


_VALID_DECISIONS = {"APPROVED", "REJECTED", "PENDING", "ESCALATE", "UNKNOWN", "RE-ROUTE", "BLOCKED"}
_VALID_RISKS = {"low", "medium", "high", "unknown"}


def _sanitize_cache_payload(payload: dict) -> dict:
    """Ensure LLM-produced fields are safe before caching and re-serving to other users."""
    decision = str(payload.get("final_decision", "UNKNOWN"))
    if decision not in _VALID_DECISIONS:
        decision = "UNKNOWN"

    risk = str(payload.get("hallucination_risk", "medium")).lower()
    if risk not in _VALID_RISKS:
        risk = "medium"

    clause_results = []
    for c in payload.get("clause_results", []):
        if isinstance(c, dict):
            clause_results.append({
                "clause": str(c.get("clause", ""))[:200],
                "status": "PRESENT" if str(c.get("status", "")).upper() == "PRESENT" else "MISSING",
                "evidence": str(c.get("evidence", ""))[:300],
            })

    return {
        "type": "done",
        "final_decision": decision,
        "doc_type": str(payload.get("doc_type", ""))[:100],
        "evaluation_score": _clamp_score(payload.get("evaluation_score", 0.0)),
        "hallucination_risk": risk,
        "routing_confidence": _clamp_score(payload.get("routing_confidence", 0.0)),
        "clause_results": clause_results,
        "clause_results_history": [],
        "language": str(payload.get("language", "en"))[:10],
        "trace_id": str(payload.get("trace_id", ""))[:36],
        # Only persist sanitized when explicitly set in the payload.
        # Absence of this field allows the /analyze endpoint to back-fill it
        # using guardrail-block heuristics for entries created before this field existed.
        **( {"sanitized": bool(payload["sanitized"])} if "sanitized" in payload else {} ),
    }


async def insert_doc_cache(doc_hash: str, payload: dict) -> None:
    sanitized = _sanitize_cache_payload(payload)
    async with _connect() as db:
        await db.execute(_CREATE_DOC_CACHE_TABLE)
        await db.execute(
            "INSERT OR REPLACE INTO doc_cache (doc_hash, payload, cached_at) VALUES (?, ?, ?)",
            (doc_hash, json.dumps(sanitized), datetime.now(timezone.utc).isoformat()),
        )
        await db.commit()


async def get_doc_cache(doc_hash: str) -> dict | None:
    try:
        async with _connect() as db:
            cursor = await db.execute(
                "SELECT payload FROM doc_cache WHERE doc_hash = ?", (doc_hash,)
            )
            row = await cursor.fetchone()
            return json.loads(row[0]) if row else None
    except Exception:
        return None


async def delete_doc_cache(doc_hash: str) -> None:
    async with _connect() as db:
        await db.execute(_CREATE_DOC_CACHE_TABLE)
        await db.execute("DELETE FROM doc_cache WHERE doc_hash = ?", (doc_hash,))
        await db.commit()


def _safe_store_filename(filename: str) -> str:
    """Strip any path components and cap length before storing."""
    return Path(filename).name[:255]


def _clamp_score(value) -> float:
    """Clamp faithfulness/evaluation scores to [0.0, 1.0]."""
    import math
    try:
        f = float(value)
        if math.isnan(f) or math.isinf(f):
            return 0.0
        return max(0.0, min(1.0, f))
    except (TypeError, ValueError):
        return 0.0


async def insert(record: dict) -> None:
    async with _connect() as db:
        await db.execute(
            """
            INSERT OR REPLACE INTO analyses
                (id, trace_id, filename, doc_type, decision, faithfulness, risk, created_at, raw_text)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.get("id", record.get("trace_id")),
                record.get("trace_id", ""),
                _safe_store_filename(record.get("filename", "")),
                record.get("doc_type", ""),
                record.get("decision", ""),
                _clamp_score(record.get("faithfulness", 0.0)),
                record.get("risk", ""),
                record.get("created_at", datetime.now(timezone.utc).isoformat()),
                record.get("raw_text"),
            ),
        )
        await db.commit()


async def get_by_trace_id(trace_id: str) -> dict | None:
    """Return the stored analysis record including raw_text, or None if not found."""
    try:
        async with _connect() as db:
            cursor = await db.execute(
                "SELECT trace_id, filename, raw_text FROM analyses WHERE trace_id = ? LIMIT 1",
                (trace_id,),
            )
            row = await cursor.fetchone()
            if not row:
                return None
            return {"trace_id": row[0], "filename": row[1], "raw_text": row[2]}
    except Exception:
        return None


async def get_cache_by_trace_id(trace_id: str) -> dict | None:
    """Return the doc_cache payload whose trace_id matches, using SQLite json_extract."""
    try:
        async with _connect() as db:
            cursor = await db.execute(
                "SELECT payload FROM doc_cache WHERE json_extract(payload, '$.trace_id') = ?",
                (trace_id,),
            )
            row = await cursor.fetchone()
            return json.loads(row[0]) if row else None
    except Exception:
        return None


async def update_raw_text(trace_id: str, raw_text: str) -> None:
    """Back-fill raw_text for an existing analysis record (e.g. when a cached result lacked it)."""
    async with _connect() as db:
        await db.execute(
            "UPDATE analyses SET raw_text = ? WHERE trace_id = ?",
            (raw_text[:50_000], trace_id),
        )
        await db.commit()


def _safe_csv_field(value: str) -> str:
    """Prefix formula-starting characters to prevent CSV injection in spreadsheet apps."""
    if value and value[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


async def get_history_csv(limit: int = 1000) -> str:
    records = await get_history(limit=limit)
    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_ALL, lineterminator="\n")
    writer.writerow(["trace_id", "filename", "doc_type", "decision", "faithfulness", "risk", "created_at"])
    for r in records:
        writer.writerow([
            _safe_csv_field(r.get("trace_id", "")),
            _safe_csv_field(r.get("filename", "")),
            _safe_csv_field(r.get("doc_type", "")),
            _safe_csv_field(r.get("decision", "")),
            r.get("faithfulness", 0.0),
            _safe_csv_field(r.get("risk", "")),
            _safe_csv_field(r.get("created_at", "")),
        ])
    return output.getvalue()


async def insert_failure(record: dict) -> None:
    import uuid
    async with _connect() as db:
        await db.execute(_CREATE_FAILURES_TABLE)
        await db.execute(
            """
            INSERT OR REPLACE INTO failed_analyses (id, trace_id, filename, error_msg, failed_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                record.get("id", str(uuid.uuid4())),
                record.get("trace_id", ""),
                record.get("filename", ""),
                record.get("error_msg", ""),
                record.get("failed_at", datetime.now(timezone.utc).isoformat()),
            ),
        )
        await db.commit()


async def get_failures(limit: int = 50) -> list[dict]:
    try:
        async with _connect() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM failed_analyses ORDER BY failed_at DESC LIMIT ?", (limit,)
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception:
        return []


async def get_history(limit: int = 50) -> list[dict]:
    """Return recent analyses with the latest feedback rating joined in (Option B)."""
    limit = max(1, min(int(limit), 1000))
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT a.*,
                   (SELECT rating FROM feedback
                    WHERE trace_id = a.trace_id
                    ORDER BY id DESC LIMIT 1) AS feedback_rating
            FROM analyses a
            ORDER BY a.created_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_feedback_stats() -> dict:
    """Return aggregate counts: total, positive, negative, negative_rate_pct."""
    try:
        async with _connect() as db:
            cursor = await db.execute(
                "SELECT rating, COUNT(*) as cnt FROM feedback GROUP BY rating"
            )
            rows = await cursor.fetchall()
        counts = {"positive": 0, "negative": 0}
        for row in rows:
            rating, cnt = row[0], row[1]
            if rating in counts:
                counts[rating] = cnt
        total = counts["positive"] + counts["negative"]
        rate = round(counts["negative"] / total * 100, 1) if total else 0.0
        return {
            "total": total,
            "positive": counts["positive"],
            "negative": counts["negative"],
            "negative_rate_pct": rate,
        }
    except Exception:
        return {"total": 0, "positive": 0, "negative": 0, "negative_rate_pct": 0.0}


async def get_feedback_summary(limit: int = 100) -> list[dict]:
    """Return last N feedback entries joined with their analysis record."""
    try:
        limit = max(1, min(int(limit), 100))
        async with _connect() as db:
            cursor = await db.execute(
                """
                SELECT f.trace_id, f.rating, f.comment, f.created_at,
                       a.filename, a.decision, a.doc_type, a.faithfulness
                FROM feedback f
                LEFT JOIN analyses a ON f.trace_id = a.trace_id
                ORDER BY f.created_at DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = await cursor.fetchall()
            return [
                {
                    "trace_id": row[0],
                    "rating": row[1],
                    "comment": row[2] or "",
                    "created_at": row[3],
                    "filename": row[4],
                    "decision": row[5],
                    "doc_type": row[6],
                    "faithfulness": row[7],
                }
                for row in rows
            ]
    except Exception:
        return []


async def create_batch_job(job_id: str, total: int) -> None:
    async with _connect() as db:
        await db.execute(_CREATE_BATCH_JOBS_TABLE)
        await db.execute(
            "INSERT INTO batch_jobs (job_id, status, total, completed, results, created_at) VALUES (?, 'pending', ?, 0, '[]', ?)",
            (job_id, total, datetime.now(timezone.utc).isoformat()),
        )
        await db.commit()


async def update_batch_job(job_id: str, completed: int, results: list, status: str) -> None:
    async with _connect() as db:
        await db.execute(_CREATE_BATCH_JOBS_TABLE)
        await db.execute(
            "UPDATE batch_jobs SET completed = ?, results = ?, status = ? WHERE job_id = ?",
            (completed, json.dumps(results), status, job_id),
        )
        await db.commit()


async def get_batch_job(job_id: str) -> dict | None:
    try:
        async with _connect() as db:
            await db.execute(_CREATE_BATCH_JOBS_TABLE)
            cursor = await db.execute(
                "SELECT job_id, status, total, completed, results, created_at FROM batch_jobs WHERE job_id = ?",
                (job_id,),
            )
            row = await cursor.fetchone()
            if not row:
                return None
            return {
                "job_id": row[0],
                "status": row[1],
                "total": row[2],
                "completed": row[3],
                "results": json.loads(row[4]),
                "created_at": row[5],
            }
    except Exception:
        return None


async def get_all_history() -> list[dict]:
    """Return all rows from analyses table (used by metrics summary)."""
    try:
        async with _connect() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM analyses ORDER BY created_at DESC")
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception:
        return []


async def get_history_record(trace_id: str) -> dict | None:
    """Return a single analyses row by trace_id, or None if not found."""
    try:
        async with _connect() as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM analyses WHERE trace_id = ? LIMIT 1", (trace_id,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None
    except Exception:
        return None


async def insert_feedback(trace_id: str, rating: str, comment: str = "") -> None:
    async with _connect() as db:
        await db.execute(_CREATE_FEEDBACK_TABLE)
        await db.execute(
            "INSERT INTO feedback (trace_id, rating, comment, created_at) VALUES (?, ?, ?, ?)",
            (trace_id, rating, comment[:500], datetime.now(timezone.utc).isoformat()),
        )
        await db.commit()


async def update_decision(trace_id: str, decision: str) -> None:
    """Persist a compliance officer decision override to the analyses table."""
    async with _connect() as db:
        await db.execute(
            "UPDATE analyses SET decision = ? WHERE trace_id = ?",
            (decision, trace_id),
        )
        await db.commit()


async def create_recommendation(rec: dict) -> None:
    """Insert a new recommendation (status defaults to pending)."""
    async with _connect() as db:
        await db.execute(_CREATE_RECOMMENDATIONS_TABLE)
        await db.execute(
            """
            INSERT OR IGNORE INTO recommendations
                (rec_id, doc_type, rec_type, proposed, evidence_count,
                 confidence, rationale, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)
            """,
            (
                rec["rec_id"],
                rec["doc_type"],
                rec["rec_type"],
                rec["proposed"],
                int(rec.get("evidence_count", 1)),
                rec.get("confidence", "medium"),
                rec.get("rationale", ""),
                rec.get("created_at", datetime.now(timezone.utc).isoformat()),
            ),
        )
        await db.commit()


async def get_recommendations(status: str | None = None) -> list[dict]:
    """Return recommendations, optionally filtered by status."""
    try:
        async with _connect() as db:
            await db.execute(_CREATE_RECOMMENDATIONS_TABLE)
            db.row_factory = aiosqlite.Row
            if status:
                cursor = await db.execute(
                    "SELECT * FROM recommendations WHERE status = ? ORDER BY created_at DESC",
                    (status,),
                )
            else:
                cursor = await db.execute(
                    "SELECT * FROM recommendations ORDER BY created_at DESC"
                )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception:
        return []


async def get_recommendation(rec_id: str) -> dict | None:
    """Return a single recommendation by rec_id."""
    try:
        async with _connect() as db:
            await db.execute(_CREATE_RECOMMENDATIONS_TABLE)
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM recommendations WHERE rec_id = ? LIMIT 1", (rec_id,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None
    except Exception:
        return None


async def set_recommendation_status(
    rec_id: str, status: str, resolved_at: str | None = None
) -> None:
    """Update the status (and optionally resolved_at) of a recommendation."""
    async with _connect() as db:
        await db.execute(_CREATE_RECOMMENDATIONS_TABLE)
        await db.execute(
            "UPDATE recommendations SET status = ?, resolved_at = ? WHERE rec_id = ?",
            (status, resolved_at, rec_id),
        )
        await db.commit()


async def has_pending_recommendation(doc_type: str, proposed: str) -> bool:
    """True if a pending recommendation with the same doc_type+proposed already exists."""
    try:
        async with _connect() as db:
            await db.execute(_CREATE_RECOMMENDATIONS_TABLE)
            cursor = await db.execute(
                """SELECT 1 FROM recommendations
                   WHERE doc_type = ? AND proposed = ? AND status = 'pending'
                   LIMIT 1""",
                (doc_type, proposed),
            )
            row = await cursor.fetchone()
            return row is not None
    except Exception:
        return False


async def is_blacklisted(doc_type: str, proposed: str) -> bool:
    """True if (doc_type, proposed) was rejected and blacklisted."""
    try:
        async with _connect() as db:
            await db.execute(_CREATE_BLACKLIST_TABLE)
            cursor = await db.execute(
                "SELECT 1 FROM recommendation_blacklist WHERE doc_type = ? AND proposed = ? LIMIT 1",
                (doc_type, proposed),
            )
            row = await cursor.fetchone()
            return row is not None
    except Exception:
        return False


async def add_to_blacklist(doc_type: str, proposed: str) -> None:
    """Blacklist a (doc_type, proposed) pair so the review agent skips it."""
    async with _connect() as db:
        await db.execute(_CREATE_BLACKLIST_TABLE)
        await db.execute(
            "INSERT OR IGNORE INTO recommendation_blacklist (doc_type, proposed, created_at) VALUES (?, ?, ?)",
            (doc_type, proposed, datetime.now(timezone.utc).isoformat()),
        )
        await db.commit()


async def remove_from_blacklist(doc_type: str, proposed: str) -> None:
    """Remove a blacklist entry (called when a rejected recommendation is re-opened)."""
    async with _connect() as db:
        await db.execute(_CREATE_BLACKLIST_TABLE)
        await db.execute(
            "DELETE FROM recommendation_blacklist WHERE doc_type = ? AND proposed = ?",
            (doc_type, proposed),
        )
        await db.commit()


async def get_feedback(trace_id: str) -> dict | None:
    try:
        async with _connect() as db:
            await db.execute(_CREATE_FEEDBACK_TABLE)
            cursor = await db.execute(
                "SELECT rating, comment, created_at FROM feedback WHERE trace_id = ? ORDER BY id DESC LIMIT 1",
                (trace_id,),
            )
            row = await cursor.fetchone()
            if row:
                return {"rating": row[0], "comment": row[1], "created_at": row[2]}
            return None
    except Exception:
        return None
