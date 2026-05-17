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


def _parse_eval(raw: str) -> tuple[float, str, str]:
    """Extract faithfulness score, hallucination_risk, and rationale from LLM output."""
    match = _JSON_RE.search(raw)
    if match:
        try:
            data = json.loads(match.group())
            score = float(data.get("faithfulness", 0.5))
            risk = str(data.get("hallucination_risk", "medium"))
            rationale = str(data.get("rationale", ""))
            return score, risk, rationale
        except (json.JSONDecodeError, ValueError):
            pass
    return 0.5, "medium", "Could not parse evaluator response."


def eval_node(state: AgentState) -> dict:
    system_msg = _prompt_cfg["system"]
    rubric = _prompt_cfg["scoring_rubric"]
    user_msg = (
        f"Source Document:\n{state['raw_text'][:2000]}\n\n"
        f"Compliance Agent Report:\n{state.get('compliance_output', '')}\n\n"
        f"{rubric}"
    )

    response = _llm.invoke([SystemMessage(content=system_msg), HumanMessage(content=user_msg)])
    score, risk, rationale = _parse_eval(response.content)

    log = f"[Evaluator v{_VERSION}] Faithfulness: {score:.2f} | Hallucination Risk: {risk} | {rationale}"
    return {
        "evaluation_score": score,
        "hallucination_risk": risk,
        "logs": [log],
    }
