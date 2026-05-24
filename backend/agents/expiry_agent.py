import json
import re
from pathlib import Path

import structlog
from langchain_core.messages import HumanMessage, SystemMessage

from .state import AgentState
from .llm_factory import create_llm

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "expiry_v1.0.0.json"
_prompt_cfg: dict = json.loads(_PROMPT_PATH.read_text())

_llm = create_llm(temperature=0)
_VERSION = _prompt_cfg.get("version", "1.0.0")
_log = structlog.get_logger("sentinel.expiry")

_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
_MIN_YEAR = 1990
_MAX_YEAR = 2100


def _validate_date(date_str: str) -> str:
    """Return date_str if the year is within the plausible range, else 'NOT_FOUND'."""
    m = re.match(r"(\d{4})-\d{2}-\d{2}", date_str)
    if not m:
        return date_str
    year = int(m.group(1))
    if year < _MIN_YEAR or year > _MAX_YEAR:
        _log.warning("expiry_date_out_of_range", date=date_str, year=year)
        return "NOT_FOUND"
    return date_str


def expiry_node(state: AgentState) -> dict:
    system_msg = _prompt_cfg["system"]
    user_msg = _prompt_cfg["user_template"].format(document=state["raw_text"][:3000])

    response = _llm.invoke([SystemMessage(content=system_msg), HumanMessage(content=user_msg)])
    raw = response.content.strip()

    if _DATE_RE.search(raw):
        expiry_date = _validate_date(_DATE_RE.search(raw).group())
    elif "NOT_FOUND" in raw.upper():
        expiry_date = "NOT_FOUND"
    else:
        expiry_date = raw[:20] if raw else "NOT_FOUND"

    log = f"[Expiry v{_VERSION}] Expiry date extracted: {expiry_date}"
    return {
        "expiry_date": expiry_date,
        "final_decision": "APPROVED",
        "logs": [log],
    }
