"""Central LLM factory — reads config from environment variables.

Local dev:   OLLAMA_BASE_URL unset  → http://127.0.0.1:11434
Production:  OLLAMA_BASE_URL=https://your-ollama-cloud-url
"""
import os

from langchain_ollama import ChatOllama

_DEFAULT_MODEL = "gemma4:31b-cloud"
_DEFAULT_BASE_URL = "http://127.0.0.1:11434"


def create_llm(temperature: float = 0.0, **kwargs):
    """Return a configured LLM instance.

    Env vars:
      LLM_PROVIDER   — only "ollama" supported (default)
      OLLAMA_MODEL   — model tag (default: gemma4:31b-cloud)
      OLLAMA_BASE_URL — Ollama server URL (default: localhost:11434)
    """
    provider = os.getenv("LLM_PROVIDER", "ollama")
    if provider != "ollama":
        raise ValueError(f"Unknown LLM_PROVIDER: {provider!r}. Only 'ollama' is supported.")

    model = os.getenv("OLLAMA_MODEL", _DEFAULT_MODEL)
    base_url = os.getenv("OLLAMA_BASE_URL", _DEFAULT_BASE_URL)

    return ChatOllama(model=model, temperature=temperature, base_url=base_url, **kwargs)
