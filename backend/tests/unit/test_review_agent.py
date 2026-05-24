"""
Unit tests for agents/review_agent.py (Phase G meta-agent).
TDD: all LLM calls are mocked — no Ollama required.
Run: pytest tests/unit/test_review_agent.py -v
"""
import asyncio
import json
import os
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_jsonl(tmp_path: Path, entries: list[dict]) -> Path:
    p = tmp_path / "correction_examples.jsonl"
    p.write_text("\n".join(json.dumps(e) for e in entries) + "\n")
    return p


def _mock_llm_response(content: str):
    mock = MagicMock()
    mock.content = content
    return mock


# ---------------------------------------------------------------------------
# _load_corrections
# ---------------------------------------------------------------------------

class TestLoadCorrections:
    def test_returns_empty_list_when_file_missing(self, tmp_path):
        from agents.review_agent import _load_corrections
        import agents.review_agent as ra
        original = ra._CORRECTION_JSONL_PATH
        ra._CORRECTION_JSONL_PATH = tmp_path / "nonexistent.jsonl"
        try:
            result = _load_corrections()
            assert result == []
        finally:
            ra._CORRECTION_JSONL_PATH = original

    def test_returns_parsed_entries(self, tmp_path):
        from agents.review_agent import _load_corrections
        import agents.review_agent as ra
        p = _make_jsonl(tmp_path, [
            {"doc_type": "NDA", "comment": "missed clause", "rating": "negative"},
            {"doc_type": "LEGAL_CONTRACT", "comment": "wrong type", "rating": "negative"},
        ])
        original = ra._CORRECTION_JSONL_PATH
        ra._CORRECTION_JSONL_PATH = p
        try:
            result = _load_corrections()
            assert len(result) == 2
            assert result[0]["doc_type"] == "NDA"
        finally:
            ra._CORRECTION_JSONL_PATH = original

    def test_skips_malformed_lines(self, tmp_path):
        from agents.review_agent import _load_corrections
        import agents.review_agent as ra
        p = tmp_path / "correction_examples.jsonl"
        p.write_text('{"doc_type":"NDA"}\nNOT_JSON\n{"doc_type":"LEGAL_CONTRACT"}\n')
        original = ra._CORRECTION_JSONL_PATH
        ra._CORRECTION_JSONL_PATH = p
        try:
            result = _load_corrections()
            assert len(result) == 2
        finally:
            ra._CORRECTION_JSONL_PATH = original


# ---------------------------------------------------------------------------
# _group_by_doc_type
# ---------------------------------------------------------------------------

class TestGroupByDocType:
    def test_groups_correctly(self):
        from agents.review_agent import _group_by_doc_type
        entries = [
            {"doc_type": "NDA", "comment": "a"},
            {"doc_type": "NDA", "comment": "b"},
            {"doc_type": "LEGAL_CONTRACT", "comment": "c"},
        ]
        grouped = _group_by_doc_type(entries)
        assert len(grouped["NDA"]) == 2
        assert len(grouped["LEGAL_CONTRACT"]) == 1

    def test_skips_empty_doc_type(self):
        from agents.review_agent import _group_by_doc_type
        entries = [
            {"doc_type": "", "comment": "a"},
            {"doc_type": "NDA", "comment": "b"},
        ]
        grouped = _group_by_doc_type(entries)
        assert "" not in grouped
        assert "NDA" in grouped


# ---------------------------------------------------------------------------
# run_review — SSE output + logic
# ---------------------------------------------------------------------------

class TestRunReview:
    def _collect(self, gen) -> list[str]:
        """Drain an async generator into a list of strings."""
        async def _drain():
            lines = []
            async for chunk in gen:
                lines.append(chunk)
            return lines
        return asyncio.run(_drain())

    def test_yields_sse_lines_when_no_corrections(self, tmp_path):
        import agents.review_agent as ra
        original = ra._CORRECTION_JSONL_PATH
        ra._CORRECTION_JSONL_PATH = tmp_path / "missing.jsonl"
        try:
            lines = self._collect(ra.run_review(min_evidence=1))
            full = "".join(lines)
            assert "data:" in full
            assert "No correction examples" in full
        finally:
            ra._CORRECTION_JSONL_PATH = original

    def test_skips_doc_type_below_min_evidence(self, tmp_path):
        import agents.review_agent as ra
        p = _make_jsonl(tmp_path, [
            {"doc_type": "NDA", "comment": "missed clause", "rating": "negative"},
        ])
        original = ra._CORRECTION_JSONL_PATH
        ra._CORRECTION_JSONL_PATH = p
        try:
            with patch("agents.review_agent.create_llm") as mock_llm_factory:
                lines = self._collect(ra.run_review(min_evidence=5))
            full = "".join(lines)
            assert "Skipping NDA" in full
            # LLM should NOT have been called
            mock_llm_factory.assert_not_called()
        finally:
            ra._CORRECTION_JSONL_PATH = original

    def test_skips_blacklisted_proposed(self, tmp_path):
        import agents.review_agent as ra
        import data.history_store as hs
        p = _make_jsonl(tmp_path, [
            {"doc_type": "NDA", "comment": "missed indemnity", "rating": "negative"},
        ])
        original = ra._CORRECTION_JSONL_PATH
        ra._CORRECTION_JSONL_PATH = p

        llm_json = json.dumps({"recommendations": [
            {"rec_type": "missing_rule", "proposed": "indemnity clause",
             "evidence_count": 1, "confidence": "high", "rationale": "test"}
        ]})
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=_mock_llm_response(llm_json))

        try:
            with patch("agents.review_agent.create_llm", return_value=mock_llm), \
                 patch.object(hs, "is_blacklisted", AsyncMock(return_value=True)), \
                 patch.object(hs, "has_pending_recommendation", AsyncMock(return_value=False)), \
                 patch.object(hs, "create_recommendation", AsyncMock()):
                lines = self._collect(ra.run_review(min_evidence=1))
            full = "".join(lines)
            assert "previously rejected" in full or "Skipping" in full
        finally:
            ra._CORRECTION_JSONL_PATH = original

    def test_skips_already_pending_recommendation(self, tmp_path):
        import agents.review_agent as ra
        import data.history_store as hs
        p = _make_jsonl(tmp_path, [
            {"doc_type": "NDA", "comment": "missed clause", "rating": "negative"},
        ])
        original = ra._CORRECTION_JSONL_PATH
        ra._CORRECTION_JSONL_PATH = p

        llm_json = json.dumps({"recommendations": [
            {"rec_type": "missing_rule", "proposed": "indemnity clause",
             "evidence_count": 1, "confidence": "high", "rationale": "test"}
        ]})
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=_mock_llm_response(llm_json))

        try:
            with patch("agents.review_agent.create_llm", return_value=mock_llm), \
                 patch.object(hs, "is_blacklisted", AsyncMock(return_value=False)), \
                 patch.object(hs, "has_pending_recommendation", AsyncMock(return_value=True)), \
                 patch.object(hs, "create_recommendation", AsyncMock()) as mock_create:
                lines = self._collect(ra.run_review(min_evidence=1))
            mock_create.assert_not_called()
        finally:
            ra._CORRECTION_JSONL_PATH = original

    def test_writes_recommendation_to_db(self, tmp_path):
        import agents.review_agent as ra
        import data.history_store as hs
        p = _make_jsonl(tmp_path, [
            {"doc_type": "NDA", "comment": "missed indemnity", "rating": "negative"},
        ])
        original = ra._CORRECTION_JSONL_PATH
        ra._CORRECTION_JSONL_PATH = p

        llm_json = json.dumps({"recommendations": [
            {"rec_type": "missing_rule", "proposed": "indemnity clause",
             "evidence_count": 1, "confidence": "high", "rationale": "Users flagged it"}
        ]})
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=_mock_llm_response(llm_json))

        try:
            with patch("agents.review_agent.create_llm", return_value=mock_llm), \
                 patch.object(hs, "is_blacklisted", AsyncMock(return_value=False)), \
                 patch.object(hs, "has_pending_recommendation", AsyncMock(return_value=False)), \
                 patch.object(hs, "create_recommendation", AsyncMock()) as mock_create:
                self._collect(ra.run_review(min_evidence=1))
            mock_create.assert_called_once()
            call_arg = mock_create.call_args[0][0]
            assert call_arg["doc_type"] == "NDA"
            assert call_arg["rec_type"] == "missing_rule"
            assert call_arg["proposed"] == "indemnity clause"
        finally:
            ra._CORRECTION_JSONL_PATH = original

    def test_done_event_in_output(self, tmp_path):
        import agents.review_agent as ra
        ra_path_orig = ra._CORRECTION_JSONL_PATH
        ra._CORRECTION_JSONL_PATH = tmp_path / "missing.jsonl"
        try:
            lines = self._collect(ra.run_review(min_evidence=1))
            full = "".join(lines)
            assert '"done"' in full
        finally:
            ra._CORRECTION_JSONL_PATH = ra_path_orig

    def test_handles_llm_json_parse_failure_gracefully(self, tmp_path):
        import agents.review_agent as ra
        import data.history_store as hs
        p = _make_jsonl(tmp_path, [
            {"doc_type": "NDA", "comment": "test", "rating": "negative"},
        ])
        original = ra._CORRECTION_JSONL_PATH
        ra._CORRECTION_JSONL_PATH = p

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(return_value=_mock_llm_response("NOT VALID JSON"))

        try:
            with patch("agents.review_agent.create_llm", return_value=mock_llm), \
                 patch.object(hs, "is_blacklisted", AsyncMock(return_value=False)), \
                 patch.object(hs, "has_pending_recommendation", AsyncMock(return_value=False)), \
                 patch.object(hs, "create_recommendation", AsyncMock()):
                # Should not raise
                lines = self._collect(ra.run_review(min_evidence=1))
            full = "".join(lines)
            assert "data:" in full  # still yielded SSE lines
        finally:
            ra._CORRECTION_JSONL_PATH = original
