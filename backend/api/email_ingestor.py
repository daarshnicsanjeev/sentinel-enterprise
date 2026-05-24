"""
Email ingestion helpers for Project Sentinel.
"""
import html
import re

_TAG_RE = re.compile(r'<[^>]+>')
_WHITESPACE_RE = re.compile(r'\s+')


def strip_html(text: str) -> str:
    """Remove HTML tags and decode entities from a string."""
    if not text:
        return ""
    # Decode HTML entities first so &lt; becomes < before tag removal
    decoded = html.unescape(text)
    # Strip tags
    plain = _TAG_RE.sub(" ", decoded)
    # Collapse whitespace but preserve newlines roughly
    plain = _WHITESPACE_RE.sub(" ", plain).strip()
    return plain
