"""
Review Agent — LLM-assisted meta-analysis of user feedback.

Reads correction_examples.jsonl, groups by doc_type, calls the LLM with a
structured meta-prompt, classifies patterns as missing_rule or
comprehension_failure, and writes recommendations to the DB.

Yields SSE-formatted log lines so the frontend can stream the agent's reasoning
in real time — identical pattern to the document analysis pipeline.
"""
import json
import os
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator

import structlog

import data.history_store as history_store
from agents.llm_factory import create_llm

_log = structlog.get_logger("sentinel.review_agent")

_DATA_DIR = Path(__file__).parent.parent / "data"
_CORRECTION_JSONL_PATH = _DATA_DIR / "correction_examples.jsonl"
_REG_DB_PATH = _DATA_DIR / "regulatory_db.json"

_META_SYSTEM_PROMPT = """\
You are an AI system architect analysing feedback patterns in an automated
compliance engine. Your job is to identify recurring problems and propose fixes.

Each feedback entry has a RATING (positive/negative) and a DECISION (what the
system decided). The combination tells you what went wrong:

  👎 negative + APPROVED  → system approved a doc it should have rejected
                             → likely a MISSING RULE (clause not in required list)
  👎 negative + REJECTED  → system rejected a doc it should have approved
                             → likely a COMPREHENSION FAILURE (clause present but missed)
  👍 positive + REJECTED  → user agrees the doc should have passed
                             → likely a COMPREHENSION FAILURE (over-strict detection)
  👍 positive + APPROVED  → confirmed correct decision — not included in this prompt

Respond ONLY with valid JSON — no prose, no markdown fences.
"""

_META_USER_TEMPLATE = """\
DOC_TYPE: {doc_type}

CURRENT REQUIRED CLAUSES:
{current_clauses}

USER FEEDBACK ({n} entries):
{complaints}

Analyse the feedback using the direction rules above and return a JSON object
with this exact structure:
{{
  "recommendations": [
    {{
      "rec_type": "missing_rule",
      "proposed": "<exact clause name to add>",
      "evidence_count": <int>,
      "confidence": "high" | "medium" | "low",
      "rationale": "<one concise sentence>"
    }},
    {{
      "rec_type": "comprehension_failure",
      "proposed": {{
        "clause": "<existing clause name>",
        "failed_phrase": "<phrase the LLM missed>",
        "correction": "<one sentence explaining the mapping>"
      }},
      "evidence_count": <int>,
      "confidence": "high" | "medium" | "low",
      "rationale": "<one concise sentence>"
    }}
  ]
}}

Rules:
- "missing_rule": the clause does not appear in CURRENT REQUIRED CLAUSES at all.
  Only propose for 👎+APPROVED patterns.
- "comprehension_failure": the clause IS in CURRENT REQUIRED CLAUSES but was
  missed because of unusual phrasing. Propose for 👎+REJECTED or 👍+REJECTED.
- Omit recommendation types not supported by the evidence.
- Output an empty recommendations list if no clear pattern exists.
- Never invent clause names. Base every recommendation on the feedback.
"""


def _load_corrections() -> list[dict]:
    """Read all entries from correction_examples.jsonl."""
    if not _CORRECTION_JSONL_PATH.exists():
        return []
    entries = []
    for line in _CORRECTION_JSONL_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return entries


def _group_by_doc_type(entries: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for e in entries:
        doc_type = (e.get("doc_type") or "").strip()
        if doc_type:
            grouped[doc_type].append(e)
    return dict(grouped)


def _current_clauses_for(doc_type: str) -> list[str]:
    """Return required clause names for doc_type from the active regulatory DB.

    The file is structured as {tenant_id: {doc_type: [clauses]}}.
    Searches all tenants and returns the first match (default tenant first).
    """
    try:
        db = json.loads(_REG_DB_PATH.read_text())
        # Prefer "default" tenant, then fall back to any tenant that has it
        for tenant_key in (["default"] + [k for k in db if k != "default"]):
            tenant_data = db.get(tenant_key, {})
            if isinstance(tenant_data, dict):
                clauses = tenant_data.get(doc_type) or tenant_data.get(doc_type.upper())
                if clauses:
                    return [c.get("name", "") for c in clauses if isinstance(c, dict)]
        return []
    except Exception:
        return []


def _direction_label(rating: str, decision: str) -> str:
    """Human-readable label for the feedback direction shown in the LLM prompt."""
    rating = (rating or "").lower()
    decision = (decision or "").upper()
    if rating == "negative" and decision == "APPROVED":
        return "👎 APPROVED (system should have rejected)"
    if rating == "negative" and decision in ("REJECTED", "ESCALATE"):
        return "👎 REJECTED (system should have approved)"
    if rating == "positive" and decision in ("REJECTED", "ESCALATE"):
        return "👍 REJECTED (user agrees: should have been approved)"
    return f"{rating.upper()} {decision}"


def _sse(msg: str, event: str = "log") -> str:
    return f"data: {json.dumps({'type': event, 'message': msg})}\n\n"


async def run_review(min_evidence: int = 1) -> AsyncGenerator[str, None]:
    """
    Async generator that streams SSE log messages while running the review.
    Yields lines that can be consumed directly by a StreamingResponse.
    """
    yield _sse("Starting review agent…")

    entries = _load_corrections()
    if not entries:
        yield _sse("No correction examples found. Submit some 👎 feedback first.")
        yield _sse("Review complete — 0 recommendations generated.", event="done")
        return

    yield _sse(f"Loaded {len(entries)} feedback entr{'y' if len(entries) == 1 else 'ies'} from feedback log.")
    grouped = _group_by_doc_type(entries)
    yield _sse(f"Found {len(grouped)} doc type(s) with actionable feedback.")

    total_new = 0
    llm = None  # lazy — only created if at least one doc_type meets min_evidence

    for doc_type, doc_entries in grouped.items():
        n = len(doc_entries)
        if n < min_evidence:
            yield _sse(f"Skipping {doc_type} — only {n} entr{'y' if n == 1 else 'ies'} (min: {min_evidence}).")
            continue
        if llm is None:
            llm = create_llm(temperature=0.0)

        yield _sse(f"Analysing {doc_type} — {n} feedback entr{'y' if n == 1 else 'ies'}…")

        current_clauses = _current_clauses_for(doc_type)
        clauses_text = "\n".join(f"  - {c}" for c in current_clauses) or "  (none defined)"

        complaints_text = "\n".join(
            f"  {i+1}. [{_direction_label(e.get('rating','negative'), e.get('decision',''))}]"
            f" {e.get('comment','(no comment)') or '(no comment)'}"
            for i, e in enumerate(doc_entries)
        )

        prompt = _META_USER_TEMPLATE.format(
            doc_type=doc_type,
            current_clauses=clauses_text,
            n=n,
            complaints=complaints_text,
        )

        # Call LLM with retry on JSON parse failure
        raw_response = ""
        for attempt in range(2):
            try:
                response = await llm.ainvoke([
                    {"role": "system", "content": _META_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ])
                raw_response = response.content.strip()
                # Strip markdown fences if model adds them
                if raw_response.startswith("```"):
                    raw_response = "\n".join(
                        line for line in raw_response.splitlines()
                        if not line.startswith("```")
                    ).strip()
                parsed = json.loads(raw_response)
                break
            except json.JSONDecodeError:
                if attempt == 0:
                    yield _sse(f"  JSON parse failed for {doc_type}, retrying…")
                    parsed = None
                else:
                    yield _sse(f"  Could not parse LLM response for {doc_type} — skipping.")
                    parsed = None
            except Exception as exc:
                yield _sse(f"  LLM call failed for {doc_type}: {exc}")
                parsed = None
                break

        if not parsed:
            continue

        recs = parsed.get("recommendations", [])
        if not recs:
            yield _sse(f"  No clear pattern identified for {doc_type}.")
            continue

        for r in recs:
            rec_type = r.get("rec_type", "")
            if rec_type not in ("missing_rule", "comprehension_failure"):
                continue

            proposed_raw = r.get("proposed", "")
            proposed_str = (
                proposed_raw if isinstance(proposed_raw, str)
                else json.dumps(proposed_raw)
            )
            confidence = r.get("confidence", "medium")
            if confidence not in ("high", "medium", "low"):
                confidence = "medium"
            evidence_count = int(r.get("evidence_count", n))
            rationale = str(r.get("rationale", ""))[:500]

            # Skip blacklisted pairs
            if await history_store.is_blacklisted(doc_type, proposed_str):
                yield _sse(f"  Skipping '{proposed_str}' for {doc_type} — previously rejected.")
                continue

            # Skip duplicates already pending
            if await history_store.has_pending_recommendation(doc_type, proposed_str):
                yield _sse(f"  Skipping '{proposed_str}' for {doc_type} — already pending.")
                continue

            rec_id = f"rec-{uuid.uuid4()}"
            await history_store.create_recommendation({
                "rec_id": rec_id,
                "doc_type": doc_type,
                "rec_type": rec_type,
                "proposed": proposed_str,
                "evidence_count": evidence_count,
                "confidence": confidence,
                "rationale": rationale,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })

            label = proposed_str if isinstance(proposed_raw, str) else proposed_raw.get("clause", proposed_str)
            yield _sse(
                f"  → {rec_type.replace('_', ' ').title()}: '{label}' "
                f"(confidence: {confidence}, evidence: {evidence_count})"
            )
            total_new += 1

    yield _sse(
        f"Review complete — {total_new} new recommendation{'s' if total_new != 1 else ''} generated.",
        event="done",
    )
