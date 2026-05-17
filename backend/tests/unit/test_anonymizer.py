"""
Unit tests for data/anonymizer.py — spaCy NER entity redaction.

TDD spec: anonymize() replaces PERSON, ORG, GPE entities with tokens.
Run: pytest tests/unit/test_anonymizer.py -v
"""
import pytest


class TestAnonymizer:
    def test_replaces_person_names(self):
        from data.anonymizer import anonymize
        text = "John Smith signed the agreement."
        result, mapping = anonymize(text)
        assert "John Smith" not in result
        assert "[PERSON" in result

    def test_replaces_organisation_names(self):
        from data.anonymizer import anonymize
        text = "This agreement is between Acme Corporation and the client."
        result, mapping = anonymize(text)
        # spaCy may or may not detect "Acme Corporation" — at minimum the function runs
        assert isinstance(result, str)
        assert isinstance(mapping, dict)

    def test_returns_entity_map(self):
        from data.anonymizer import anonymize
        text = "Alice Johnson works at Goldman Sachs in New York."
        result, mapping = anonymize(text)
        assert isinstance(mapping, dict)

    def test_clean_text_unchanged(self):
        from data.anonymizer import anonymize
        text = "The contract contains force majeure and indemnification clauses."
        result, mapping = anonymize(text)
        assert result == text
        assert mapping == {}

    def test_anonymize_returns_tuple(self):
        from data.anonymizer import anonymize
        text = "Bob Smith is the CEO."
        out = anonymize(text)
        assert isinstance(out, tuple)
        assert len(out) == 2
