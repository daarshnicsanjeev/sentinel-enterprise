"""
TDD tests for Phase 8C2 — Clause Risk Scoring.

Every clause in regulatory_db now carries a risk_level (HIGH/MEDIUM/LOW).
Missing a HIGH-risk clause forces final_decision = ESCALATE.
Missing only MEDIUM/LOW clauses → REJECTED (existing behaviour).

Run: pytest tests/unit/test_clause_risk.py -v
"""
import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_clauses_with_risk():
    return [
        {"name": "governing law clause",       "risk_level": "HIGH"},
        {"name": "events of default clause",   "risk_level": "HIGH"},
        {"name": "indemnification clause",      "risk_level": "MEDIUM"},
        {"name": "representations and warranties", "risk_level": "LOW"},
    ]


# ---------------------------------------------------------------------------
# 1. regulatory_db.json schema
# ---------------------------------------------------------------------------

class TestRegulatoryDbSchema:
    def test_clauses_are_dicts_not_strings(self):
        """Every clause entry in regulatory_db.json must be a dict."""
        db_path = Path(__file__).parent.parent.parent / "data" / "regulatory_db.json"
        db = json.loads(db_path.read_text())
        for tenant, doc_types in db.items():
            for doc_type, clauses in doc_types.items():
                for clause in clauses:
                    assert isinstance(clause, dict), (
                        f"{tenant}/{doc_type}: clause {clause!r} is not a dict"
                    )

    def test_clauses_have_name_field(self):
        db_path = Path(__file__).parent.parent.parent / "data" / "regulatory_db.json"
        db = json.loads(db_path.read_text())
        for tenant, doc_types in db.items():
            for doc_type, clauses in doc_types.items():
                for clause in clauses:
                    assert "name" in clause, f"Missing 'name' in {tenant}/{doc_type}: {clause}"

    def test_clauses_have_risk_level_field(self):
        db_path = Path(__file__).parent.parent.parent / "data" / "regulatory_db.json"
        db = json.loads(db_path.read_text())
        for tenant, doc_types in db.items():
            for doc_type, clauses in doc_types.items():
                for clause in clauses:
                    assert "risk_level" in clause, (
                        f"Missing 'risk_level' in {tenant}/{doc_type}: {clause}"
                    )

    def test_risk_level_values_are_valid(self):
        db_path = Path(__file__).parent.parent.parent / "data" / "regulatory_db.json"
        db = json.loads(db_path.read_text())
        valid = {"HIGH", "MEDIUM", "LOW"}
        for tenant, doc_types in db.items():
            for doc_type, clauses in doc_types.items():
                for clause in clauses:
                    assert clause.get("risk_level") in valid, (
                        f"Invalid risk_level in {tenant}/{doc_type}: {clause}"
                    )

    def test_at_least_one_high_risk_clause_per_doc_type(self):
        """Each non-empty doc type must have at least one HIGH-risk clause."""
        db_path = Path(__file__).parent.parent.parent / "data" / "regulatory_db.json"
        db = json.loads(db_path.read_text())
        skip_empty = {"EXPIRY_CLAUSE_SCAN", "UNKNOWN"}
        for tenant, doc_types in db.items():
            for doc_type, clauses in doc_types.items():
                if doc_type in skip_empty or not clauses:
                    continue
                levels = {c["risk_level"] for c in clauses}
                assert "HIGH" in levels, (
                    f"{tenant}/{doc_type} has no HIGH-risk clause — add at least one"
                )


# ---------------------------------------------------------------------------
# 2. query_regulatory_db returns dicts
# ---------------------------------------------------------------------------

class TestQueryRegulatoryDb:
    def test_returns_list_of_dicts(self):
        from agents.compliance_agent import query_regulatory_db
        result = query_regulatory_db("CREDIT_AGREEMENT", "default")
        assert isinstance(result, list)
        assert len(result) > 0
        assert all(isinstance(c, dict) for c in result)

    def test_each_dict_has_name_and_risk_level(self):
        from agents.compliance_agent import query_regulatory_db
        result = query_regulatory_db("CREDIT_AGREEMENT", "default")
        for clause in result:
            assert "name" in clause
            assert "risk_level" in clause

    def test_unknown_doc_type_returns_empty(self):
        from agents.compliance_agent import query_regulatory_db
        assert query_regulatory_db("INVOICE", "default") == []


# ---------------------------------------------------------------------------
# 3. _parse_clause_results includes risk_level
# ---------------------------------------------------------------------------

class TestParseClauseResultsRiskLevel:
    def test_clause_results_have_risk_level(self, sample_clauses_with_risk):
        from agents.compliance_agent import _parse_clause_results
        output = "governing law clause: PRESENT\nevents of default clause: MISSING"
        results = _parse_clause_results(output, sample_clauses_with_risk)
        for r in results:
            assert "risk_level" in r, f"Missing risk_level in {r}"

    def test_risk_level_matches_db(self, sample_clauses_with_risk):
        from agents.compliance_agent import _parse_clause_results
        output = "governing law clause: PRESENT"
        results = _parse_clause_results(output, sample_clauses_with_risk)
        gov_law = next(r for r in results if r["clause"] == "governing law clause")
        assert gov_law["risk_level"] == "HIGH"

    def test_medium_risk_preserved(self, sample_clauses_with_risk):
        from agents.compliance_agent import _parse_clause_results
        output = ""
        results = _parse_clause_results(output, sample_clauses_with_risk)
        indemnity = next(r for r in results if r["clause"] == "indemnification clause")
        assert indemnity["risk_level"] == "MEDIUM"


# ---------------------------------------------------------------------------
# 4. Verdict escalation logic
# ---------------------------------------------------------------------------

class TestEscalationLogic:
    def _make_state(self, clause_results):
        """Minimal AgentState-like dict for compliance_node testing."""
        return {
            "doc_type": "CREDIT_AGREEMENT",
            "tenant_id": "default",
            "retry_count": 0,
            "raw_text": "governing law: English courts. Events of default defined herein.",
            "clause_results_history": [],
            "clause_results": clause_results,
        }

    @pytest.mark.asyncio
    async def test_missing_high_risk_clause_escalates(self):
        """If a HIGH-risk clause is MISSING, final_decision must be ESCALATE."""
        from agents import compliance_agent as ca

        fake_clauses = [
            {"name": "governing law clause",     "risk_level": "HIGH"},
            {"name": "indemnification clause",   "risk_level": "MEDIUM"},
        ]
        llm_output = "governing law clause: MISSING\nindemnification clause: PRESENT"

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content=llm_output)
        fake_index = MagicMock()
        with (
            patch.object(ca, "query_regulatory_db", return_value=fake_clauses),
            patch.object(ca, "_llm", mock_llm),
            patch("data.embeddings.build_index_async", AsyncMock(return_value=fake_index)),
            patch("data.embeddings.semantic_search", return_value=["some text chunk"]),
        ):
            result = await ca.compliance_node(self._make_state([]))

        assert result["final_decision"] == "ESCALATE"

    @pytest.mark.asyncio
    async def test_missing_only_medium_risk_rejects_not_escalates(self):
        """Missing a MEDIUM-risk clause → REJECTED, not ESCALATE."""
        from agents import compliance_agent as ca

        fake_clauses = [
            {"name": "governing law clause",     "risk_level": "HIGH"},
            {"name": "indemnification clause",   "risk_level": "MEDIUM"},
        ]
        llm_output = "governing law clause: PRESENT\nindemnification clause: MISSING"

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content=llm_output)
        fake_index = MagicMock()
        with (
            patch.object(ca, "query_regulatory_db", return_value=fake_clauses),
            patch.object(ca, "_llm", mock_llm),
            patch("data.embeddings.build_index_async", AsyncMock(return_value=fake_index)),
            patch("data.embeddings.semantic_search", return_value=["some text chunk"]),
        ):
            result = await ca.compliance_node(self._make_state([]))

        assert result["final_decision"] == "REJECTED"
        assert result["final_decision"] != "ESCALATE"

    @pytest.mark.asyncio
    async def test_all_clauses_present_approves(self):
        from agents import compliance_agent as ca

        fake_clauses = [
            {"name": "governing law clause",   "risk_level": "HIGH"},
            {"name": "indemnification clause", "risk_level": "MEDIUM"},
        ]
        llm_output = "governing law clause: PRESENT\nindemnification clause: PRESENT"

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content=llm_output)
        fake_index = MagicMock()
        with (
            patch.object(ca, "query_regulatory_db", return_value=fake_clauses),
            patch.object(ca, "_llm", mock_llm),
            patch("data.embeddings.build_index_async", AsyncMock(return_value=fake_index)),
            patch("data.embeddings.semantic_search", return_value=["some text chunk"]),
        ):
            result = await ca.compliance_node(self._make_state([]))

        assert result["final_decision"] == "APPROVED"

    @pytest.mark.asyncio
    async def test_missing_low_risk_clause_rejects(self):
        """Missing even a LOW-risk clause still triggers REJECTED (not silently passed)."""
        from agents import compliance_agent as ca

        fake_clauses = [
            {"name": "governing law clause",           "risk_level": "HIGH"},
            {"name": "representations and warranties", "risk_level": "LOW"},
        ]
        llm_output = "governing law clause: PRESENT\nrepresentations and warranties: MISSING"

        mock_llm = MagicMock()
        mock_llm.invoke.return_value = MagicMock(content=llm_output)
        fake_index = MagicMock()
        with (
            patch.object(ca, "query_regulatory_db", return_value=fake_clauses),
            patch.object(ca, "_llm", mock_llm),
            patch("data.embeddings.build_index_async", AsyncMock(return_value=fake_index)),
            patch("data.embeddings.semantic_search", return_value=["some text chunk"]),
        ):
            result = await ca.compliance_node(self._make_state([]))

        assert result["final_decision"] == "REJECTED"
