import json
import re
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from .state import AgentState
from .llm_factory import create_llm
from data.guardrails import sanitize

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "router_v1.0.0.json"
_prompt_cfg: dict = json.loads(_PROMPT_PATH.read_text())

_llm = create_llm(temperature=0)

VALID_CATEGORIES = set(_prompt_cfg["categories"])
_VERSION = _prompt_cfg.get("version", "1.0.0")


def _parse_router_response(raw: str) -> tuple[str, float]:
    """Parse 'LABEL: CONFIDENCE' or bare 'LABEL'. Returns (doc_type, confidence 0-1)."""
    upper = raw.strip().upper()
    for cat in VALID_CATEGORIES:
        if cat in upper:
            match = re.search(rf"{cat}[:\s]+(\d+)", upper)
            # If the LLM omitted the confidence number despite instructions, default to 0.75
            confidence = float(match.group(1)) / 100.0 if match else 0.75
            return cat, max(0.0, min(1.0, confidence))
    return "UNKNOWN", 0.0


def guardrail_node(state: AgentState) -> dict:
    is_clean, reason = sanitize(state["raw_text"])
    log = f"[Guardrail] {'Input sanitized: OK' if is_clean else f'BLOCKED — {reason}'}"
    if not is_clean:
        return {
            "sanitized": False,
            "final_decision": "BLOCKED",
            "logs": [log],
        }
    return {"sanitized": True, "logs": [log]}


def router_node(state: AgentState) -> dict:
    system_msg = _prompt_cfg["system"]
    user_msg = _prompt_cfg["user_template"].format(document=state["raw_text"][:3000])

    _MAX_LLM_RESPONSE_CHARS = 10_000
    response = _llm.invoke([SystemMessage(content=system_msg), HumanMessage(content=user_msg)])
    doc_type, confidence = _parse_router_response(response.content[:_MAX_LLM_RESPONSE_CHARS])

    log = f"[Router v{_VERSION}] Document classified as: {doc_type} (confidence: {confidence:.0%})"
    return {"doc_type": doc_type, "routing_confidence": confidence, "logs": [log]}
