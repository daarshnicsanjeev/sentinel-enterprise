import os
from langgraph.graph import StateGraph, END

from .state import AgentState
from .router_agent import guardrail_node, router_node
from .compliance_agent import compliance_node
from .eval_judge import eval_node
from .expiry_agent import expiry_node

_SCORE_THRESHOLD = 0.65
_MAX_RETRIES = 2
_EVAL_THRESHOLD = float(os.environ.get("EVAL_THRESHOLD", str(_SCORE_THRESHOLD)))


def _guardrail_route(state: AgentState) -> str:
    """After guardrail: skip to END immediately if injection was blocked."""
    if not state.get("sanitized", True):
        return "blocked"
    return "continue"


def _eval_route(state: AgentState) -> str:
    """
    Feedback loop: if faithfulness score is low and retries remain,
    re-route back to compliance for another attempt.
    """
    score = state.get("evaluation_score", 1.0)
    retries = state.get("retry_count", 0)
    if score < _EVAL_THRESHOLD and retries < _MAX_RETRIES:
        return "retry"
    return "done"


def _route_after_router(state: AgentState) -> str:
    """After router: send EXPIRY_CLAUSE_SCAN to expiry node, everything else to compliance."""
    if state.get("doc_type") == "EXPIRY_CLAUSE_SCAN":
        return "expiry"
    return "compliance"


def _increment_retry(state: AgentState) -> dict:
    """Injected before re-running compliance to bump the retry counter."""
    return {"retry_count": state.get("retry_count", 0) + 1, "final_decision": "RE-ROUTE"}


def build_graph() -> StateGraph:
    builder = StateGraph(AgentState)

    builder.add_node("guardrail", guardrail_node)
    builder.add_node("router", router_node)
    builder.add_node("compliance", compliance_node)
    builder.add_node("evaluator", eval_node)
    builder.add_node("increment_retry", _increment_retry)
    builder.add_node("expiry", expiry_node)

    builder.set_entry_point("guardrail")

    builder.add_conditional_edges(
        "guardrail",
        _guardrail_route,
        {"blocked": END, "continue": "router"},
    )

    builder.add_conditional_edges(
        "router",
        _route_after_router,
        {"expiry": "expiry", "compliance": "compliance"},
    )
    builder.add_edge("expiry", END)
    builder.add_edge("compliance", "evaluator")

    builder.add_conditional_edges(
        "evaluator",
        _eval_route,
        {"retry": "increment_retry", "done": END},
    )

    builder.add_edge("increment_retry", "compliance")

    return builder.compile()


graph = build_graph()
