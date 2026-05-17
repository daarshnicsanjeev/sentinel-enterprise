import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

_DB_PATH = os.environ.get(
    "SENTINEL_DB_PATH",
    str(Path(__file__).parent.parent / "sentinel_history.db"),
)

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


async def init_db() -> None:
    async with aiosqlite.connect(_DB_PATH) as db:
        await db.execute(_CREATE_TABLE)
        await db.execute(_CREATE_FAILURES_TABLE)
        await db.execute(_CREATE_DOC_CACHE_TABLE)
        await db.commit()


async def insert_doc_cache(doc_hash: str, payload: dict) -> None:
    async with aiosqlite.connect(_DB_PATH) as db:
        await db.execute(_CREATE_DOC_CACHE_TABLE)
        await db.execute(
            "INSERT OR REPLACE INTO doc_cache (doc_hash, payload, cached_at) VALUES (?, ?, ?)",
            (doc_hash, json.dumps(payload), datetime.now(timezone.utc).isoformat()),
        )
        await db.commit()


async def get_doc_cache(doc_hash: str) -> dict | None:
    try:
        async with aiosqlite.connect(_DB_PATH) as db:
            cursor = await db.execute(
                "SELECT payload FROM doc_cache WHERE doc_hash = ?", (doc_hash,)
            )
            row = await cursor.fetchone()
            return json.loads(row[0]) if row else None
    except Exception:
        return None


async def insert(record: dict) -> None:
    async with aiosqlite.connect(_DB_PATH) as db:
        await db.execute(
            """
            INSERT OR REPLACE INTO analyses
                (id, trace_id, filename, doc_type, decision, faithfulness, risk, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.get("id", record.get("trace_id")),
                record.get("trace_id", ""),
                record.get("filename", ""),
                record.get("doc_type", ""),
                record.get("decision", ""),
                record.get("faithfulness", 0.0),
                record.get("risk", ""),
                record.get("created_at", datetime.now(timezone.utc).isoformat()),
            ),
        )
        await db.commit()


async def get_history_csv(limit: int = 1000) -> str:
    records = await get_history(limit=limit)
    header = "trace_id,filename,doc_type,decision,faithfulness,risk,created_at"
    rows = [header] + [
        f"{r.get('trace_id','')},{r.get('filename','')},{r.get('doc_type','')},{r.get('decision','')},{r.get('faithfulness',0.0)},{r.get('risk','')},{r.get('created_at','')}"
        for r in records
    ]
    return "\n".join(rows)


async def insert_failure(record: dict) -> None:
    import uuid
    async with aiosqlite.connect(_DB_PATH) as db:
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
        async with aiosqlite.connect(_DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM failed_analyses ORDER BY failed_at DESC LIMIT ?", (limit,)
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception:
        return []


async def get_history(limit: int = 50) -> list[dict]:
    async with aiosqlite.connect(_DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM analyses ORDER BY created_at DESC LIMIT ?", (limit,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
