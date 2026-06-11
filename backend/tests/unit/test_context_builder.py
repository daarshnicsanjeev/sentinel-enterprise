"""
TDD tests for _build_context — per-clause context budgeting.

The old code joined all retrieved chunks then blindly cut at 6000 chars, so a
clause whose evidence lived late in a long document could be silently dropped
from the prompt and falsely reported MISSING.

Contract: every clause's top-ranked chunk is guaranteed a place in the context
(truncated to a fair share if necessary); remaining budget is filled with
lower-ranked chunks; duplicates appear once.

Run: pytest tests/unit/test_context_builder.py -v
"""
import pytest

from agents import compliance_agent
from agents.compliance_agent import _build_context


def _fake_search(mapping):
    """Return a semantic_search stand-in keyed by query string."""
    def search(index, query, k=3):
        return mapping.get(query, [])[:k]
    return search


class TestBuildContext:
    def test_every_clause_top_chunk_included_even_when_over_budget(self, monkeypatch):
        """Three clauses, each with a 3000-char top chunk, budget 6000:
        the old [:6000] cut would drop clause C entirely."""
        big = lambda tag: f"{tag} " + ("x" * 2995)
        mapping = {
            "clause A": [big("AAA")],
            "clause B": [big("BBB")],
            "clause C": [big("CCC")],
        }
        monkeypatch.setattr(compliance_agent, "semantic_search", _fake_search(mapping))
        ctx = _build_context(["clause A", "clause B", "clause C"], index=object(), budget=6000)
        assert "AAA" in ctx and "BBB" in ctx and "CCC" in ctx
        assert len(ctx) <= 6000

    def test_within_budget_includes_lower_ranked_chunks(self, monkeypatch):
        mapping = {
            "clause A": ["A-top", "A-second"],
            "clause B": ["B-top", "B-second"],
        }
        monkeypatch.setattr(compliance_agent, "semantic_search", _fake_search(mapping))
        ctx = _build_context(["clause A", "clause B"], index=object(), budget=6000)
        for piece in ("A-top", "B-top", "A-second", "B-second"):
            assert piece in ctx

    def test_duplicate_chunks_appear_once(self, monkeypatch):
        mapping = {
            "clause A": ["shared chunk"],
            "clause B": ["shared chunk"],
        }
        monkeypatch.setattr(compliance_agent, "semantic_search", _fake_search(mapping))
        ctx = _build_context(["clause A", "clause B"], index=object(), budget=6000)
        assert ctx.count("shared chunk") == 1

    def test_empty_results_give_empty_context(self, monkeypatch):
        monkeypatch.setattr(compliance_agent, "semantic_search", _fake_search({}))
        assert _build_context(["clause A"], index=object(), budget=6000) == ""

    def test_context_never_exceeds_budget(self, monkeypatch):
        mapping = {f"clause {i}": [f"chunk-{i} " + "y" * 1500] for i in range(10)}
        monkeypatch.setattr(compliance_agent, "semantic_search", _fake_search(mapping))
        ctx = _build_context(list(mapping.keys()), index=object(), budget=6000)
        assert len(ctx) <= 6000
