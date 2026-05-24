import json
import re
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from .state import AgentState
from .llm_factory import create_llm

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "evaluator_v1.0.0.json"
_prompt_cfg: dict = json.loads(_PROMPT_PATH.read_text())

_llm = create_llm(temperature=0, format="json")
_VERSION = _prompt_cfg.get("version", "1.0.0")

_JSON_RE = re.compile(r"\{[^{}]+\}", re.DOTALL)


_MAX_LLM_RESPONSE_CHARS = 10_000
_VALID_RISKS = {"low", "medium", "high"}


def _parse_eval(raw: str) -> tuple[float, str, str]:
    """Extract faithfulness score, hallucination_risk, and rationale from LLM output."""
    match = _JSON_RE.search(raw)
    if match:
        try:
            data = json.loads(match.group())
            raw_score = float(data.get("faithfulness", 0.5))
            score = max(0.0, min(1.0, raw_score))  # clamp to [0, 1]
            risk = str(data.get("hallucination_risk", "medium")).lower()
            if risk not in _VALID_RISKS:
                risk = "medium"
            rationale = str(data.get("rationale", ""))[:500]
            return score, risk, rationale
        except (json.JSONDecodeError, ValueError):
            pass
    return 0.5, "medium", "Could not parse evaluator response."


def eval_node(state: AgentState) -> dict:
    system_msg = _prompt_cfg["system"]
    rubric = _prompt_cfg["scoring_rubric"]
    # Use the FAISS-retrieved context the compliance agent actually saw.
    # Falls back to the first 2000 chars of raw_text for guardrail-blocked
    # or expiry-only runs where compliance_context is not populated.
    source_context = state.get("compliance_context") or state["raw_text"][:2000]
    user_msg = (
        f"Relevant Document Context (retrieved excerpts):\n{source_context}\n\n"
        f"Compliance Agent Report:\n{state.get('compliance_output', '')}\n\n"
        f"{rubric}"
    )

    response = _llm.invoke([SystemMessage(content=system_msg), HumanMessage(content=user_msg)])
    score, risk, rationale = _parse_eval(response.content[:_MAX_LLM_RESPONSE_CHARS])

    log = f"[Evaluator v{_VERSION}] Faithfulness: {score:.0%} | Hallucination Risk: {risk} | {rationale}"
    return {
        "evaluation_score": score,
        "hallucination_risk": risk,
        "logs": [log],
    }
