"""Language detection utility using langdetect."""


def detect_language(text: str) -> str:
    """Detect the language of text. Returns ISO 639-1 code or 'unknown'."""
    if not text or not text.strip():
        return "unknown"
    try:
        from langdetect import detect, LangDetectException
        return detect(text)
    except Exception:
        return "unknown"
