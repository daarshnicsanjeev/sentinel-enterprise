"""
Unit tests for agents/graph.py routing functions.

TDD spec: routing functions are pure — they must not call LLMs or I/O.
These tests verify the state machine's conditional logic in isolation.
Run first: pytest tests/unit/test_graph_routing.py -v
"""
import pytest
from agents.graph import _guardrail_route, _eval_route, _increment_retry, _SCORE_THRESHOLD, _MAX_RETRIES
from tests.conftest import make_state


class TestGuardrailRoute:
    def test_blocked_when_sanitized_is_false(self):
        state = make_state(sanitized=False)
        assert _guardrail_route(state) == "blocked"

    def test_continue_when_sanitized_is_true(self):
        state = make_state(sanitized=True)
        assert _guardrail_route(state) == "continue"

    def test_continue_when_sanitized_key_absent(self):
        # Default is True — missing key should continue
        state = {k: v for k, v in make_state().items() if k != "sanitized"}
        assert _guardrail_route(state) == "continue"

    def test_returns_string(self):
        result = _guardrail_route(make_state(sanitized=True))
        assert isinstance(result, str)


class TestEvalRoute:
    def test_retry_when_score_below_threshold_and_retries_available(self):
        state = make_state(evaluation_score=_SCORE_THRESHOLD - 0.01, retry_count=0)
        assert _eval_route(state) == "retry"

    def test_done_when_score_equals_threshold(self):
        # Score at exactly the threshold → done (not retry)
        state = make_state(evaluation_score=_SCORE_THRESHOLD, retry_count=0)
        assert _eval_route(state) == "done"

    def test_done_when_score_above_threshold(self):
        state = make_state(evaluation_score=0.9, retry_count=0)
        assert _eval_route(state) == "done"

    def test_done_when_retries_exhausted(self):
        state = make_state(evaluation_score=0.0, retry_count=_MAX_RETRIES)
        assert _eval_route(state) == "done"

    def test_retry_when_score_low_and_one_retry_used(self):
        state = make_state(evaluation_score=0.0, retry_count=1)
        assert _eval_route(state) == "retry"

    def test_done_when_retries_exceed_max(self):
        state = make_state(evaluation_score=0.0, retry_count=_MAX_RETRIES + 1)
        assert _eval_route(state) == "done"

    def test_missing_score_defaults_to_high_faith_done(self):
        # Missing evaluation_score defaults to 1.0 — should be done
        state = {k: v for k, v in make_state().items() if k != "evaluation_score"}
        assert _eval_route(state) == "done"

    def test_returns_string(self):
        result = _eval_route(make_state(evaluation_score=0.9, retry_count=0))
        assert isinstance(result, str)


class TestIncrementRetry:
    def test_increments_retry_count_from_zero(self):
        state = make_state(retry_count=0)
        result = _increment_retry(state)
        assert result["retry_count"] == 1

    def test_increments_retry_count_from_one(self):
        state = make_state(retry_count=1)
        result = _increment_retry(state)
        assert result["retry_count"] == 2

    def test_missing_retry_count_defaults_to_zero_then_increments(self):
        state = {k: v for k, v in make_state().items() if k != "retry_count"}
        result = _increment_retry(state)
        assert result["retry_count"] == 1

    def test_returns_partial_state_dict(self):
        result = _increment_retry(make_state(retry_count=0))
        assert isinstance(result, dict)
        assert "retry_count" in result

    def test_sets_re_route_as_final_decision(self):
        result = _increment_retry(make_state(retry_count=0))
        assert result.get("final_decision") == "RE-ROUTE"

    def test_does_not_modify_other_fields(self):
        result = _increment_retry(make_state(retry_count=0))
        assert set(result.keys()) == {"retry_count", "final_decision"}


class TestConstants:
    def test_score_threshold_is_float(self):
        assert isinstance(_SCORE_THRESHOLD, float)

    def test_score_threshold_is_between_0_and_1(self):
        assert 0.0 < _SCORE_THRESHOLD < 1.0

    def test_max_retries_is_positive_int(self):
        assert isinstance(_MAX_RETRIES, int)
        assert _MAX_RETRIES > 0


# ---------------------------------------------------------------------------
# A2: EVAL_THRESHOLD env var makes the routing threshold configurable
# ---------------------------------------------------------------------------

class TestEnvThreshold:
    def test_eval_threshold_exists_as_module_variable(self):
        import agents.graph as graph_module
        assert hasattr(graph_module, "_EVAL_THRESHOLD")

    def test_eval_threshold_is_float(self):
        import agents.graph as graph_module
        assert isinstance(graph_module._EVAL_THRESHOLD, float)

    def test_eval_route_retries_when_score_below_custom_threshold(self, monkeypatch):
        import agents.graph as graph_module
        monkeypatch.setattr(graph_module, "_EVAL_THRESHOLD", 0.9)
        # Score 0.8 < custom threshold 0.9 → should retry
        state = make_state(evaluation_score=0.8, retry_count=0)
        assert _eval_route(state) == "retry"

    def test_eval_route_done_when_score_above_custom_threshold(self, monkeypatch):
        import agents.graph as graph_module
        monkeypatch.setattr(graph_module, "_EVAL_THRESHOLD", 0.5)
        # Score 0.6 > custom threshold 0.5 → should be done
        state = make_state(evaluation_score=0.6, retry_count=0)
        assert _eval_route(state) == "done"


# ---------------------------------------------------------------------------
# A4: Async FAISS — compliance_node is an async coroutine function
# ---------------------------------------------------------------------------

class TestAsyncCompliance:
    def test_compliance_node_is_coroutine_function(self):
        import inspect
        from agents.compliance_agent import compliance_node
        assert inspect.iscoroutinefunction(compliance_node)

    def test_build_index_async_exists_in_embeddings(self):
        import inspect
        from data.embeddings import build_index_async
        assert inspect.iscoroutinefunction(build_index_async)
