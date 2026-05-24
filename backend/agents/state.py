from typing import TypedDict, Annotated
import operator


class AgentState(TypedDict):
    raw_text: str
    sanitized: bool
    doc_type: str
    required_clauses: list
    compliance_output: str
    evaluation_score: float
    hallucination_risk: str
    final_decision: str
    retry_count: int
    trace_id: str
    tenant_id: str
    routing_confidence: float
    clause_results: list
    clause_results_history: list
    expiry_date: str
    language: str
    compliance_context: str
    logs: Annotated[list, operator.add]
