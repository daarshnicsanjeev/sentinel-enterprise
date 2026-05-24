import re

# ── Injection detection (compiled regex, handles whitespace/comment bypasses) ──

_INJECTION_PATTERNS: list[tuple[re.Pattern, str]] = [
    # Prompt injection
    (re.compile(r"ignore\s+(?:all\s+)?previous\s+instructions", re.I), "prompt injection"),
    (re.compile(r"disregard\s+(?:your\s+)?(?:system\s+prompt|previous)", re.I), "prompt injection"),
    (re.compile(r"you\s+are\s+now\b", re.I), "prompt injection"),
    (re.compile(r"\bact\s+as\s+if\s+you\s+are\b", re.I), "prompt injection"),
    (re.compile(r"forget\s+your\s+instructions", re.I), "prompt injection"),
    (re.compile(r"\bnew\s+persona\b", re.I), "prompt injection"),
    (re.compile(r"\bjailbreak\b", re.I), "prompt injection"),
    (re.compile(r"bypass\s+your\s+filters", re.I), "prompt injection"),
    (re.compile(r"override\s+system", re.I), "prompt injection"),
    # SQL injection — handles whitespace, comment (/**/) and newline variants
    (re.compile(r"'[\s;]*(?:drop|exec|create|alter|truncate)\s+", re.I), "sql injection"),
    (re.compile(r"'\s*(?:or|and)\s+'?1'?\s*=\s*'?1", re.I), "sql injection"),
    # Unrolled-loop pattern prevents ReDoS: [^*]|\*(?!/) avoids catastrophic backtracking
    (re.compile(r"\bunion\s+(?:/\*(?:[^*]|\*(?!/))*\*/\s*)?select\b", re.I), "sql injection"),
    (re.compile(r"\b1\s*=\s*cast\s*\(", re.I), "sql injection"),
    (re.compile(r"\bxp_cmdshell\b", re.I), "sql injection"),
]

# Pre-processing strips SQL comments to prevent comment-based bypasses
_SQL_COMMENT_RE = re.compile(r"/\*.*?\*/|--[^\n]*", re.S)


# ── PII detection — flexible separators, common card formats ─────────────────

PII_PATTERNS = [
    r"\b\d{3}[-\s]\d{2}[-\s]\d{4}\b",                                    # SSN: 123-45-6789 or 123 45 6789
    r"\b(?:\d{4}[-\s]?){3}\d{4}\b",                                       # Credit card 16-digit (with/without separators)
    r"\b3[47]\d{2}[-\s]?\d{6}[-\s]?\d{5}\b",                             # Amex 15-digit
    r"\b[A-Z]{2}\d{6}[A-Z]\b",                                            # Passport (UK-style: AA123456A)
    r"(?i)passport\s+(?:number|no\.?)\s*:?\s*\d[\d\s]{5,}",              # Passport with label
    r"\bIBAN\s*:?\s*[A-Z]{2}\d{2}",                                       # IBAN with label: IBAN: DE89...
    r"\b[A-Z]{2}\d{2}\s[A-Z0-9]{4}\s\d{4}\s\d{4}",                      # IBAN with spaces: DE89 3704 0044 ...
    r"(?i)(?:swift|bic)\s*(?:/\s*(?:swift|bic))?\s*:?\s*[A-Z]{4}[A-Z0-9]{3,7}(?:[A-Z0-9]{3})?",  # SWIFT/BIC: 8 or 11 chars
]

_PII_COMPILED = [re.compile(p) for p in PII_PATTERNS]

# Public aliases used by tests and external callers
INJECTION_PATTERNS = [p.pattern for p, _ in _INJECTION_PATTERNS]


def sanitize(text: str) -> tuple[bool, str]:
    """
    Returns (is_clean, reason).
    is_clean=True means the text passed all checks.
    """
    # Strip SQL comments before injection checks (prevents comment-based bypass)
    normalized = _SQL_COMMENT_RE.sub(" ", text)

    for pattern, label in _INJECTION_PATTERNS:
        if pattern.search(normalized):
            return False, f"[Guardrail] BLOCKED — {label} detected matching pattern: {pattern.pattern}"

    for compiled in _PII_COMPILED:
        if compiled.search(text):
            return False, f"[Guardrail] BLOCKED — PII detected matching pattern: {compiled.pattern}"

    if len(text.strip()) < 20:
        return False, "Document text too short to process."

    return True, "OK"
