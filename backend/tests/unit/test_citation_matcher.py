"""
Unit tests pinning _find_citation edge cases — the deterministic check that
proves a cited passage really exists in the source document.

Run: pytest tests/unit/test_citation_matcher.py -v
"""
from agents.compliance_agent import _find_citation


class TestFindCitation:
    def test_exact_match_returns_offset(self):
        raw = "PREFIX the governing law clause applies SUFFIX"
        assert _find_citation("the governing law clause applies", raw) == raw.find("the")

    def test_regex_special_characters_in_evidence(self):
        """Legal text is full of regex metacharacters — they must be treated literally."""
        raw = "Fine of Rs 5000/- (five thousand) under section 133(1)(i) [as amended]."
        evidence = "Rs 5000/- (five thousand) under section 133(1)(i) [as amended]"
        assert _find_citation(evidence, raw) >= 0

    def test_whitespace_and_linebreak_differences(self):
        raw = "neither party\nshall   be\tliable for delays"
        assert _find_citation("neither party shall be liable for delays", raw) >= 0

    def test_mid_word_truncation_still_matches(self):
        """Evidence chunks are cut at 300 chars, possibly mid-word — the
        truncated final token must still match as a prefix inside the doc."""
        raw = "The borrower accepts the limitation of liability without reservation."
        evidence = "the limitation of liabil"  # cut mid-word
        assert _find_citation(evidence, raw) >= 0

    def test_repeated_evidence_returns_first_offset(self):
        raw = "indemnify the lender. Later text. indemnify the lender."
        offset = _find_citation("indemnify the lender", raw)
        assert offset == 0

    def test_case_insensitive(self):
        raw = "GOVERNING LAW CLAUSE: New York law applies."
        assert _find_citation("governing law clause", raw) == 0

    def test_fabricated_evidence_returns_minus_one(self):
        assert _find_citation("text that is not there", "completely different document") == -1

    def test_empty_evidence_returns_minus_one(self):
        assert _find_citation("", "some document") == -1

    def test_empty_document_returns_minus_one(self):
        assert _find_citation("some evidence", "") == -1

    def test_whitespace_only_evidence_returns_minus_one(self):
        assert _find_citation("   \n\t  ", "some document") == -1
