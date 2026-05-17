import json
import re
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from .state import AgentState
from .llm_factory import create_llm
from data.embeddings import build_index_async, semantic_search

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "compliance_v1.0.0.json"
_prompt_cfg: dict = json.loads(_PROMPT_PATH.read_text())

_REG_DB_PATH = Path(__file__).parent.parent / "data" / "regulatory_db.json"
_regulatory_db: dict = json.loads(_REG_DB_PATH.read_text())

_llm = create_llm(temperature=0)
_VERSION = _prompt_cfg.get("version", "1.0.0")


def query_regulatory_db(doc_type: str, tenant_id: str = "default") -> list[str]:
    """FR-02 Tool: Retrieves required clauses for a given document type and tenant profile."""
    tenant_db = _regulatory_db.get(tenant_id) or _regulatory_db.get("default", {})
    return tenant_db.get(doc_type, [])


async def compliance_node(state: AgentState) -> dict:
    doc_type = state.get("doc_type", "UNKNOWN")
    retry = state.get("retry_count", 0)

    required_clauses = query_regulatory_db(doc_type, tenant_id=state.get("tenant_id", "default"))
    tool_log = f"[Compliance Tool] Queried regulatory DB for {doc_type} → Required: {required_clauses}"

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
    for clause in required_clauses:
        chunks = semantic_search(index, clause, k=2)
        relevant_chunks.extend(chunks)
    context = "\n---\n".join(dict.fromkeys(relevant_chunks))

    system_msg = _prompt_cfg["system"].format(doc_type=doc_type)
    user_msg = _prompt_cfg["check_instruction"].format(
        required_clauses="\n".join(f"- {c}" for c in required_clauses),
        document=context[:3000],
    )

    response = _llm.invoke([SystemMessage(content=system_msg), HumanMessage(content=user_msg)])
    compliance_output = response.content.strip()

    verdict = "REJECTED"
    if "VERDICT: COMPLIANT" in compliance_output.upper():
        verdict = "APPROVED"

    clause_results = _parse_clause_results(compliance_output, required_clauses, index)

    history = state.get("clause_results_history", []) + [clause_results]

    retry_label = f" [retry #{retry}]" if retry > 0 else ""
    check_log = f"[Compliance v{_VERSION}{retry_label}] Verdict: {verdict}"

    return {
        "required_clauses": required_clauses,
        "compliance_output": compliance_output,
        "clause_results": clause_results,
        "clause_results_history": history,
        "final_decision": verdict,
        "retry_count": retry,
        "logs": [tool_log, check_log],
    }


def _parse_clause_results(output: str, required_clauses: list[str], index=None) -> list[dict]:
    """Extract per-clause PRESENT/MISSING status and evidence from compliance LLM output."""
    results = []
    for clause in required_clauses:
        pattern = re.compile(
            rf"-\s*{re.escape(clause)}\s*:\s*(PRESENT|MISSING)",
            re.IGNORECASE,
        )
        match = pattern.search(output)
        status = match.group(1).upper() if match else "MISSING"
        evidence = ""
        if status == "PRESENT" and index is not None:
            chunks = semantic_search(index, clause, k=1)
            evidence = chunks[0][:300] if chunks else ""
        results.append({"clause": clause, "status": status, "evidence": evidence})
    return results
