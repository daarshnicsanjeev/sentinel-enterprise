"""
Unit tests for agents/eval_judge.py — _parse_eval()

TDD spec: the JSON parser is the reliability boundary of the evaluation system.
It must degrade gracefully when the LLM produces non-JSON output.
Run first: pytest tests/unit/test_eval_parse.py -v
"""
import pytest
from agents.eval_judge import _parse_eval


class TestValidJSONParsing:
    def test_parses_bare_json(self):
        raw = '{"faithfulness": 0.9, "hallucination_risk": "low", "rationale": "All claims supported."}'
        score, risk, rationale = _parse_eval(raw)
        assert score == pytest.approx(0.9)
        assert risk == "low"
        assert "supported" in rationale

    def test_parses_json_wrapped_in_markdown_fence(self):
        raw = '```json\n{"faithfulness": 0.5, "hallucination_risk": "medium", "rationale": "Mixed results."}\n```'
        score, risk, _ = _parse_eval(raw)
        assert score == pytest.approx(0.5)
        assert risk == "medium"

    def test_parses_json_with_preamble_text(self):
        raw = 'Here is the evaluation result:\n{"faithfulness": 0.75, "hallucination_risk": "low", "rationale": "Good."}'
        score, risk, _ = _parse_eval(raw)
        assert score == pytest.approx(0.75)
        assert risk == "low"

    def test_returns_float_score(self):
        raw = '{"faithfulness": 1, "hallucination_risk": "low", "rationale": "Perfect."}'
        score, _, _ = _parse_eval(raw)
        assert isinstance(score, float)

    def test_zero_faithfulness(self):
        raw = '{"faithfulness": 0.0, "hallucination_risk": "high", "rationale": "Complete hallucination."}'
        score, risk, _ = _parse_eval(raw)
        assert score == pytest.approx(0.0)
        assert risk == "high"

    def test_full_faithfulness(self):
        raw = '{"faithfulness": 1.0, "hallucination_risk": "low", "rationale": "Accurate."}'
        score, _, _ = _parse_eval(raw)
        assert score == pytest.approx(1.0)

    def test_all_three_fields_returned(self):
        raw = '{"faithfulness": 0.8, "hallucination_risk": "medium", "rationale": "Mostly good."}'
        result = _parse_eval(raw)
        assert len(result) == 3
        score, risk, rationale = result
        assert isinstance(score, float)
        assert isinstance(risk, str)
        assert isinstance(rationale, str)


class TestMissingFields:
    def test_missing_faithfulness_defaults_to_0_5(self):
        raw = '{"hallucination_risk": "low", "rationale": "Test."}'
        score, _, _ = _parse_eval(raw)
        assert score == pytest.approx(0.5)

    def test_missing_risk_defaults_to_medium(self):
        raw = '{"faithfulness": 0.8, "rationale": "Test."}'
        _, risk, _ = _parse_eval(raw)
        assert risk == "medium"

    def test_missing_rationale_defaults_to_empty_string(self):
        raw = '{"faithfulness": 0.8, "hallucination_risk": "low"}'
        _, _, rationale = _parse_eval(raw)
        assert rationale == ""


class TestFallbackBehavior:
    def test_fallback_on_empty_string(self):
        score, risk, rationale = _parse_eval("")
        assert score == pytest.approx(0.5)
        assert risk == "medium"
        assert "Could not parse" in rationale

    def test_fallback_on_plain_text(self):
        score, risk, rationale = _parse_eval("I cannot evaluate this document at this time.")
        assert score == pytest.approx(0.5)
        assert "Could not parse" in rationale

    def test_fallback_on_malformed_json(self):
        score, risk, rationale = _parse_eval('{"faithfulness": "not-a-number"}')
        # float("not-a-number") raises ValueError → fallback
        assert score == pytest.approx(0.5)
        assert "Could not parse" in rationale

    def test_fallback_on_unclosed_brace(self):
        score, _, rationale = _parse_eval('{"faithfulness": 0.9')
        assert score == pytest.approx(0.5)
        assert "Could not parse" in rationale

    def test_fallback_risk_is_medium(self):
        _, risk, _ = _parse_eval("no json here at all")
        assert risk == "medium"
