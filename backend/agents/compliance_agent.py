import json
import re
from datetime import date
from pathlib import Path

import structlog
from langchain_core.messages import HumanMessage, SystemMessage

from .state import AgentState
from .llm_factory import create_llm
from .router_agent import VALID_CATEGORIES
from data.embeddings import build_index_async, semantic_search

_log = structlog.get_logger("sentinel.compliance")

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "compliance_v1.0.0.json"
_prompt_cfg: dict = json.loads(_PROMPT_PATH.read_text())

_FEW_SHOT_PATH = Path(__file__).parent.parent / "data" / "few_shot_examples.jsonl"


def _load_few_shot_examples(doc_type: str) -> list[dict]:
    """Return approved comprehension corrections for a given doc_type."""
    if not _FEW_SHOT_PATH.exists():
        return []
    examples = []
    for line in _FEW_SHOT_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
            if entry.get("doc_type") == doc_type:
                examples.append(entry)
        except json.JSONDecodeError:
            pass
    return examples


def _build_few_shot_section(examples: list[dict]) -> str:
    """Format few-shot examples as a 'Known Phrasings' prompt section."""
    if not examples:
        return ""
    lines = ["\n\nKNOWN PHRASINGS (approved corrections from prior analyses):"]
    for e in examples:
        phrase = e.get("failed_phrase", "")
        clause = e.get("clause", "")
        correction = e.get("correction", "")
        if phrase and clause:
            lines.append(f'  - "{phrase}" → satisfies: {clause}. {correction}')
    return "\n".join(lines)

_REG_DB_PATH = Path(__file__).parent.parent / "data" / "regulatory_db.json"


_VALID_RISK_LEVELS = {"HIGH", "MEDIUM", "LOW"}


def _load_and_validate_regulatory_db(path: Path) -> dict:
    """Load regulatory_db.json and validate its structure.

    The expected structure is: {tenant_id: {doc_type: [{name, risk_level}, ...]}}

    Invalid top-level entries (e.g. a doc_type key written at the wrong level by
    a previous bug) are silently dropped so the service can still start up.
    Only well-formed tenant → doc_type → clause entries are returned.
    """
    raw = json.loads(path.read_text())
    if not isinstance(raw, dict):
        raise ValueError(f"regulatory_db.json must be a JSON object, got {type(raw).__name__}")
    clean: dict = {}
    for tenant, tenant_data in raw.items():
        if not isinstance(tenant_data, dict):
            # Malformed entry (e.g. doc_type key at wrong nesting level) — skip it
            _log.warning(
                "regulatory_db_invalid_entry_skipped",
                key=tenant,
                got=type(tenant_data).__name__,
            )
            continue
        clean[tenant] = {}
        for doc_type, clauses in tenant_data.items():
            if not isinstance(clauses, list):
                _log.warning("regulatory_db_invalid_clauses_skipped", tenant=tenant, doc_type=doc_type)
                continue
            valid_clauses = []
            for i, clause in enumerate(clauses):
                if not isinstance(clause, dict) or not clause.get("name", "").strip():
                    _log.warning("regulatory_db_invalid_clause_skipped", tenant=tenant, doc_type=doc_type, index=i)
                    continue
                if clause.get("risk_level") not in _VALID_RISK_LEVELS:
                    _log.warning("regulatory_db_invalid_risk_level", tenant=tenant, doc_type=doc_type, index=i, risk_level=clause.get("risk_level"))
                    continue
                valid_clauses.append(clause)
            clean[tenant][doc_type] = valid_clauses
    return clean


_regulatory_db: dict = _load_and_validate_regulatory_db(_REG_DB_PATH)


def reload_regulatory_db() -> None:
    """Re-read regulatory_db.json from disk and update the compliance agent's in-memory cache.

    Called by routes.reload_reg_db() after any write to regulatory_db.json so that
    subsequent analyses immediately see the updated clause list without a service restart.
    """
    global _regulatory_db
    _regulatory_db = _load_and_validate_regulatory_db(_REG_DB_PATH)
    _log.info("compliance_regulatory_db_reloaded", doc_types=list(_regulatory_db.keys()))


_llm = create_llm(temperature=0)
_VERSION = _prompt_cfg.get("version", "1.0.0")

_EXPIRY_EXPLICIT_RE = re.compile(
    r"(?:this\s+(?:facility|agreement|credit\s+facility)\s+expired|expired\s+on\s+\w+\s+\d{1,2},?\s+(\d{4}))",
    re.IGNORECASE,
)
_YEAR_IN_EXPIRY_RE = re.compile(
    r"expired\s+on\s+\w+\s+\d{1,2},?\s+(\d{4})",
    re.IGNORECASE,
)


def _is_document_expired(text: str) -> bool:
    """Return True if text explicitly states the facility/agreement has expired with a past date."""
    current_year = date.today().year
    # Explicit "THIS FACILITY EXPIRED" style markers
    if re.search(r"THIS\s+(?:FACILITY|AGREEMENT|CREDIT\s+FACILITY)\s+EXPIRED", text, re.IGNORECASE):
        return True
    # "expired on [Month] [Day], [Year]" where Year is in the past
    for m in _YEAR_IN_EXPIRY_RE.finditer(text):
        if int(m.group(1)) < current_year:
            return True
    return False


def query_regulatory_db(doc_type: str, tenant_id: str = "default") -> list[dict]:
    """FR-02 Tool: Returns required clauses (with risk_level) for a doc type and tenant profile."""
    tenant_db = (
        _regulatory_db.get(tenant_id)
        or _regulatory_db.get(tenant_id.upper())
        or _regulatory_db.get("default", {})
    )
    return tenant_db.get(doc_type, [])


async def compliance_node(state: AgentState) -> dict:
    raw_doc_type = state.get("doc_type", "UNKNOWN")
    doc_type = raw_doc_type if raw_doc_type in VALID_CATEGORIES else "UNKNOWN"
    retry = state.get("retry_count", 0)

    required_clauses = query_regulatory_db(doc_type, tenant_id=state.get("tenant_id", "default"))
    clause_names = [c["name"] for c in required_clauses]
    tool_log = f"[Compliance Tool] Queried regulatory DB for {doc_type} → Required: {clause_names}"

    if doc_type == "UNKNOWN":
        return {
            "required_clauses": [],
            "compliance_output": (
                "Unrecognized document type — this document does not match any "
                "supported category, so no automated compliance verdict can be issued."
            ),
            "final_decision": "ESCALATE",
            "retry_count": retry,
            "logs": [tool_log, "[Compliance] Unrecognized document type — ESCALATED for human review."],
        }

    if not required_clauses:
        return {
            "required_clauses": [],
            "compliance_output": "No regulatory clauses defined for this document type.",
            "final_decision": "APPROVED",
            "retry_count": retry,
            "logs": [tool_log, "[Compliance] No clauses required — auto-APPROVED."],
        }

    index = await build_index_async(state["raw_text"])
    relevant_chunks = []
    for name in clause_names:
        chunks = semantic_search(index, name, k=3)
        relevant_chunks.extend(chunks)
    context = "\n---\n".join(dict.fromkeys(relevant_chunks))

    few_shot_examples = _load_few_shot_examples(doc_type)
    few_shot_section = _build_few_shot_section(few_shot_examples)
    if few_shot_examples:
        _log.info("few_shot_injected", doc_type=doc_type, count=len(few_shot_examples))

    system_msg = _prompt_cfg["system"].format(doc_type=doc_type) + few_shot_section
    user_msg = _prompt_cfg["check_instruction"].format(
        required_clauses="\n".join(f"- {n}" for n in clause_names),
        document=context[:6000],
    )

    _MAX_LLM_RESPONSE_CHARS = 20_000
    response = _llm.invoke([SystemMessage(content=system_msg), HumanMessage(content=user_msg)])
    compliance_output = response.content[:_MAX_LLM_RESPONSE_CHARS].strip()

    clause_results = _parse_clause_results(
        compliance_output, required_clauses, index, raw_text=state["raw_text"]
    )

    # Derive verdict from structured clause results
    all_present = clause_results and all(r["status"] == "PRESENT" for r in clause_results)
    any_high_missing = any(
        r["status"] == "MISSING" and r.get("risk_level") == "HIGH"
        for r in clause_results
    )
    if all_present:
        verdict = "APPROVED"
    elif any_high_missing:
        verdict = "ESCALATE"
    else:
        verdict = "REJECTED"

    history = state.get("clause_results_history", []) + [clause_results]

    # Expiry override: if doc text explicitly says the facility has expired, reject regardless of clauses
    if verdict == "APPROVED" and _is_document_expired(state["raw_text"]):
        verdict = "REJECTED"

    retry_label = f" [retry #{retry}]" if retry > 0 else ""
    check_log = f"[Compliance v{_VERSION}{retry_label}] Verdict: {verdict}"

    return {
        "required_clauses": required_clauses,
        "compliance_output": compliance_output,
        "compliance_context": context,
        "clause_results": clause_results,
        "clause_results_history": history,
        "final_decision": verdict,
        "retry_count": retry,
        "logs": [tool_log, check_log],
    }


def _find_citation(evidence: str, raw_text: str) -> int:
    """Locate evidence inside the source document, tolerating whitespace
    differences introduced by PDF/OCR extraction. Returns the character
    offset in raw_text, or -1 if the evidence cannot be found verbatim."""
    if not evidence or not raw_text:
        return -1
    tokens = evidence.split()
    if not tokens:
        return -1
    pattern = re.compile(r"\s+".join(re.escape(tok) for tok in tokens), re.IGNORECASE)
    match = pattern.search(raw_text)
    return match.start() if match else -1


def _parse_clause_results(
    output: str, required_clauses: list[dict], index=None, raw_text: str = ""
) -> list[dict]:
    """Extract per-clause PRESENT/MISSING status, evidence, and risk_level.
    Each evidence chunk is verified against the source document so the UI can
    prove the citation is real rather than trusting the LLM's word."""
    results = []
    for clause in required_clauses:
        name = clause["name"]
        risk_level = clause.get("risk_level", "MEDIUM")
        pattern = re.compile(
            rf"(?:^|\n|-)[ \t]*{re.escape(name)}[ \t]*:[ \t]*(PRESENT|MISSING)",
            re.IGNORECASE,
        )
        match = pattern.search(output)
        status = match.group(1).upper() if match else "MISSING"
        evidence = ""
        if status == "PRESENT" and index is not None:
            chunks = semantic_search(index, name, k=1)
            evidence = chunks[0][:300] if chunks else ""
        citation_offset = _find_citation(evidence, raw_text)
        results.append({
            "clause": name,
            "status": status,
            "evidence": evidence,
            "risk_level": risk_level,
            "citation_verified": citation_offset >= 0,
            "citation_offset": citation_offset,
        })
    return results
