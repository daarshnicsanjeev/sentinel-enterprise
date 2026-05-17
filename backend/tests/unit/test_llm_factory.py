"""Unit tests for agents/llm_factory.py — TDD RED first."""
import os
import pytest


class TestLLMFactory:
    def test_creates_ollama_by_default(self, monkeypatch):
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
        from agents.llm_factory import create_llm
        llm = create_llm()
        assert llm.__class__.__name__ == "ChatOllama"

    def test_uses_configured_model(self, monkeypatch):
        monkeypatch.setenv("OLLAMA_MODEL", "gemma4:31b-cloud")
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        from agents.llm_factory import create_llm
        llm = create_llm()
        assert llm.model == "gemma4:31b-cloud"

    def test_uses_base_url_when_env_set(self, monkeypatch):
        monkeypatch.setenv("OLLAMA_BASE_URL", "http://cloud.ollama.ai:11434")
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        from agents import llm_factory
        import importlib
        importlib.reload(llm_factory)
        llm = llm_factory.create_llm()
        assert "cloud.ollama.ai" in str(llm.base_url)

    def test_raises_for_unknown_provider(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "unknown_provider")
        from agents import llm_factory
        import importlib
        importlib.reload(llm_factory)
        with pytest.raises(ValueError, match="Unknown LLM_PROVIDER"):
            llm_factory.create_llm()

    def test_create_llm_accepts_temperature(self, monkeypatch):
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        from agents.llm_factory import create_llm
        llm = create_llm(temperature=0.5)
        assert llm.temperature == 0.5

    def test_create_llm_accepts_format_kwarg(self, monkeypatch):
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        from agents.llm_factory import create_llm
        llm = create_llm(format="json")
        assert llm.format == "json"
