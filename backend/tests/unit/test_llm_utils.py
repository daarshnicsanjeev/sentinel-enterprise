"""
Unit tests for agents/llm_utils.py — invoke_with_retry helper.

TDD spec: retry wrapper must succeed on first attempt, retry on transient errors,
and re-raise after max attempts exhausted.
Run: pytest tests/unit/test_llm_utils.py -v
"""
import pytest
from unittest.mock import MagicMock, call


class TestInvokeWithRetry:
    def test_succeeds_on_first_attempt(self):
        from agents.llm_utils import invoke_with_retry
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="LEGAL_CONTRACT:85")
        messages = ["msg1"]
        result = invoke_with_retry(mock_llm, messages)
        assert result.content == "LEGAL_CONTRACT:85"
        mock_llm.invoke.assert_called_once_with(messages)

    def test_retries_on_exception_and_succeeds(self):
        from agents.llm_utils import invoke_with_retry
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = [
            ConnectionError("Ollama timeout"),
            MagicMock(content="CREDIT_AGREEMENT:90"),
        ]
        messages = ["msg1"]
        result = invoke_with_retry(mock_llm, messages)
        assert result.content == "CREDIT_AGREEMENT:90"
        assert mock_llm.invoke.call_count == 2

    def test_raises_after_max_retries_exhausted(self):
        from agents.llm_utils import invoke_with_retry
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = ConnectionError("Ollama unavailable")
        with pytest.raises(Exception):
            invoke_with_retry(mock_llm, ["msg"])
        assert mock_llm.invoke.call_count == 3

    def test_returns_llm_response_object(self):
        from agents.llm_utils import invoke_with_retry
        mock_llm = MagicMock()
        expected = MagicMock(content="REGULATORY_FILING:70")
        mock_llm.invoke.return_value = expected
        result = invoke_with_retry(mock_llm, ["msg"])
        assert result is expected
