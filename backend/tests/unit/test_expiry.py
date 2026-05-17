"""
Unit tests for agents/expiry_agent.py — contract expiry date extraction.

TDD spec: expiry_node() extracts ISO date or returns NOT_FOUND.
Run: pytest tests/unit/test_expiry.py -v
"""
import pytest
from unittest.mock import MagicMock
from tests.conftest import make_state


class TestExpiryNode:
    def test_extracts_iso_date_from_document(self, monkeypatch):
        from agents import expiry_agent
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="2027-03-15")
        monkeypatch.setattr(expiry_agent, "_llm", mock_llm)
        from agents.expiry_agent import expiry_node
        result = expiry_node(make_state(doc_type="EXPIRY_CLAUSE_SCAN"))
        assert result["expiry_date"] == "2027-03-15"

    def test_returns_not_found_when_no_date(self, monkeypatch):
        from agents import expiry_agent
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="NOT_FOUND")
        monkeypatch.setattr(expiry_agent, "_llm", mock_llm)
        from agents.expiry_agent import expiry_node
        result = expiry_node(make_state(doc_type="EXPIRY_CLAUSE_SCAN"))
        assert result["expiry_date"] == "NOT_FOUND"

    def test_expiry_date_in_state_keys(self, monkeypatch):
        from agents import expiry_agent
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="2028-06-30")
        monkeypatch.setattr(expiry_agent, "_llm", mock_llm)
        from agents.expiry_agent import expiry_node
        result = expiry_node(make_state(doc_type="EXPIRY_CLAUSE_SCAN"))
        assert "expiry_date" in result

    def test_expiry_log_appended(self, monkeypatch):
        from agents import expiry_agent
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="2026-12-31")
        monkeypatch.setattr(expiry_agent, "_llm", mock_llm)
        from agents.expiry_agent import expiry_node
        result = expiry_node(make_state(doc_type="EXPIRY_CLAUSE_SCAN"))
        assert len(result["logs"]) > 0
        assert "expiry" in result["logs"][0].lower() or "date" in result["logs"][0].lower()

    def test_sets_final_decision_approved(self, monkeypatch):
        from agents import expiry_agent
        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content="2029-01-01")
        monkeypatch.setattr(expiry_agent, "_llm", mock_llm)
        from agents.expiry_agent import expiry_node
        result = expiry_node(make_state(doc_type="EXPIRY_CLAUSE_SCAN"))
        assert result["final_decision"] == "APPROVED"


class TestGraphRoutingExpiry:
    def test_expiry_scan_routes_to_expiry_branch(self):
        from agents.graph import _route_after_router
        state = {"doc_type": "EXPIRY_CLAUSE_SCAN"}
        assert _route_after_router(state) == "expiry"

    def test_legal_contract_routes_to_compliance(self):
        from agents.graph import _route_after_router
        state = {"doc_type": "LEGAL_CONTRACT"}
        assert _route_after_router(state) == "compliance"

    def test_credit_agreement_routes_to_compliance(self):
        from agents.graph import _route_after_router
        state = {"doc_type": "CREDIT_AGREEMENT"}
        assert _route_after_router(state) == "compliance"
