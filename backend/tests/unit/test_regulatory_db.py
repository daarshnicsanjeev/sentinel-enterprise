"""
Unit tests for agents/compliance_agent.py — query_regulatory_db()

TDD spec: the regulatory DB tool is the authoritative source for required clauses.
Any change to regulatory_db.json must break these tests first, forcing deliberate review.
Run first: pytest tests/unit/test_regulatory_db.py -v
"""
import pytest
from agents.compliance_agent import query_regulatory_db


class TestCreditAgreementClauses:
    def test_returns_four_clauses(self):
        clauses = query_regulatory_db("CREDIT_AGREEMENT")
        assert len(clauses) == 4

    def test_contains_governing_law(self):
        clauses = query_regulatory_db("CREDIT_AGREEMENT")
        assert "governing law clause" in clauses

    def test_contains_events_of_default(self):
        clauses = query_regulatory_db("CREDIT_AGREEMENT")
        assert "events of default clause" in clauses

    def test_contains_indemnification(self):
        clauses = query_regulatory_db("CREDIT_AGREEMENT")
        assert "indemnification clause" in clauses

    def test_contains_representations_and_warranties(self):
        clauses = query_regulatory_db("CREDIT_AGREEMENT")
        assert "representations and warranties" in clauses


class TestLegalContractClauses:
    def test_returns_three_clauses(self):
        clauses = query_regulatory_db("LEGAL_CONTRACT")
        assert len(clauses) == 3

    def test_contains_force_majeure(self):
        clauses = query_regulatory_db("LEGAL_CONTRACT")
        assert "force majeure clause" in clauses

    def test_contains_limitation_of_liability(self):
        clauses = query_regulatory_db("LEGAL_CONTRACT")
        assert "limitation of liability" in clauses

    def test_contains_dispute_resolution(self):
        clauses = query_regulatory_db("LEGAL_CONTRACT")
        assert "dispute resolution clause" in clauses


class TestRegulatoryFilingClauses:
    def test_returns_three_clauses(self):
        clauses = query_regulatory_db("REGULATORY_FILING")
        assert len(clauses) == 3

    def test_contains_material_disclosure(self):
        clauses = query_regulatory_db("REGULATORY_FILING")
        assert "material disclosure statement" in clauses

    def test_contains_risk_factor_disclosures(self):
        clauses = query_regulatory_db("REGULATORY_FILING")
        assert "risk factor disclosures" in clauses

    def test_contains_auditor_certification(self):
        clauses = query_regulatory_db("REGULATORY_FILING")
        assert "auditor certification" in clauses


class TestEdgeCases:
    def test_unknown_type_returns_empty_list(self):
        clauses = query_regulatory_db("UNKNOWN")
        assert clauses == []

    def test_nonexistent_type_returns_empty_list(self):
        clauses = query_regulatory_db("TOTALLY_MADE_UP_TYPE")
        assert clauses == []

    def test_empty_string_returns_empty_list(self):
        clauses = query_regulatory_db("")
        assert clauses == []

    def test_return_type_is_list(self):
        result = query_regulatory_db("CREDIT_AGREEMENT")
        assert isinstance(result, list)

    def test_all_clauses_are_strings(self):
        for doc_type in ["CREDIT_AGREEMENT", "LEGAL_CONTRACT", "REGULATORY_FILING"]:
            for clause in query_regulatory_db(doc_type):
                assert isinstance(clause, str), f"Clause '{clause}' in {doc_type} must be a string"

    def test_case_sensitive_lookup(self):
        # Lowercase should not match
        clauses = query_regulatory_db("credit_agreement")
        assert clauses == []


# ---------------------------------------------------------------------------
# C3: Multi-tenant regulatory profiles
# ---------------------------------------------------------------------------

class TestMultiTenant:
    def test_eu_tenant_has_credit_agreement_clauses(self):
        clauses = query_regulatory_db("CREDIT_AGREEMENT", tenant_id="EU")
        assert len(clauses) > 0

    def test_us_tenant_has_legal_contract_clauses(self):
        clauses = query_regulatory_db("LEGAL_CONTRACT", tenant_id="US")
        assert len(clauses) > 0

    def test_eu_tenant_has_gdpr_clause(self):
        clauses = query_regulatory_db("CREDIT_AGREEMENT", tenant_id="EU")
        assert any("gdpr" in c.lower() or "data protection" in c.lower() for c in clauses)

    def test_unknown_tenant_falls_back_to_default(self):
        default_clauses = query_regulatory_db("CREDIT_AGREEMENT")
        fallback_clauses = query_regulatory_db("CREDIT_AGREEMENT", tenant_id="NONEXISTENT")
        assert default_clauses == fallback_clauses

    def test_default_tenant_matches_no_arg_call(self):
        assert query_regulatory_db("LEGAL_CONTRACT") == query_regulatory_db("LEGAL_CONTRACT", tenant_id="default")
