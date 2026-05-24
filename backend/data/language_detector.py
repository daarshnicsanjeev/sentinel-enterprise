"""Language detection utility using langdetect."""
import structlog

_log = structlog.get_logger("sentinel.language_detector")


def detect_language(text: str) -> str:
    """Detect the language of text. Returns ISO 639-1 code or 'unknown'."""
    if not text or not text.strip():
        return "unknown"
    try:
        from langdetect import detect, LangDetectException
        try:
            return detect(text)
        except LangDetectException as exc:
            _log.warning("language_detection_failed", reason=str(exc))
            return "unknown"
    except ImportError:
        _log.error("langdetect_not_installed")
        return "unknown"
    except Exception as exc:
        _log.error("language_detection_unexpected_error", error=str(exc))
        return "unknown"
